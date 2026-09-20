"""Subprocess supervision for the Antigravity CLI."""

from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from typing import Sequence

STOP_SIGNAL_ENV = "AGYPYWPR_STOP_SIGNAL_FILE"
FULLY_IDLE_GRACE_SECONDS = 5.0


class RunnerError(RuntimeError):
    """Raised when the Antigravity process cannot be started or completed."""


class RunResult:  # pylint: disable=too-few-public-methods
    """Result of an Antigravity process."""

    def __init__(self, returncode: int, timed_out: bool = False) -> None:
        self.returncode = returncode
        self.timed_out = timed_out


def run_agy(
    prompt: str,
    arguments: Sequence[str],
    *,
    executable: str = "agy",
    timeout: float = 1800,
) -> RunResult:
    """Run one prompt over the streaming protocol and await fullyIdle completion.

    Uses ``--input-format stream-json``/``--output-format stream-json`` instead
    of ``-p`` so the child process stays alive for exactly one turn instead of
    exiting as soon as it emits a response. If the ``agypywpr-stop-signal``
    Stop hook (see scripts/agy_stop_signal_hook.py) is installed, stdin is kept
    open past the turn's ``result`` event until that hook reports
    ``fullyIdle``, so background subagents are not abandoned mid-flight.
    Without the hook, this falls back to closing stdin shortly after the
    result, matching prior behavior.
    """
    # pylint: disable-next=duplicate-code
    command = [
        executable,
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--print-timeout",
        "0",
        *arguments,
    ]
    env = dict(os.environ)
    try:
        with tempfile.TemporaryDirectory(prefix="agypywpr-stop-signal-") as directory:
            stop_signal_path = os.path.join(directory, "signals.jsonl")
            env[STOP_SIGNAL_ENV] = stop_signal_path
            with subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=None,
                start_new_session=os.name != "nt",
                env=env,
            ) as process:
                return _supervise(process, prompt, timeout, stop_signal_path)
    except OSError as error:
        raise RunnerError(f"could not start {executable}: {error}") from error


def _supervise(
    process: subprocess.Popen[bytes],
    prompt: str,
    timeout: float,
    stop_signal_path: str,
) -> RunResult:
    """Send the prompt, await a fully-idle turn, then close stdin and wait."""
    deadline = time.monotonic() + timeout
    try:
        completed = _run_turn(process, prompt, deadline, stop_signal_path)
    except KeyboardInterrupt:
        _stop_process(process)
        raise
    _close_stdin(process)
    if not completed:
        _stop_process(process)
        return RunResult(process.wait(), timed_out=True)
    if process.poll() is None:
        process.wait(timeout=5)
    return RunResult(process.returncode or 0)


def _run_turn(
    process: subprocess.Popen[bytes],
    prompt: str,
    deadline: float,
    stop_signal_path: str,
) -> bool:
    """Return True once the turn's result is safe to treat as complete."""
    try:
        assert process.stdin is not None
        process.stdin.write(
            (
                json.dumps({"event": "user", "message": {"content": prompt}}) + "\n"
            ).encode()
        )
        process.stdin.flush()
    except BrokenPipeError:
        return True
    conversation_id = None
    grace_deadline = None
    buffer = bytearray()
    with selectors.DefaultSelector() as selector:
        assert process.stdout is not None
        selector.register(process.stdout, selectors.EVENT_READ)
        while True:
            if time.monotonic() >= deadline:
                return False
            if grace_deadline is not None and _fully_idle_or_ungoverned(
                stop_signal_path, conversation_id, grace_deadline
            ):
                return True
            remaining = max(0.0, min(0.2, deadline - time.monotonic()))
            if not selector.select(remaining):
                continue
            data = os.read(process.stdout.fileno(), 65536)
            if not data:
                return True
            buffer.extend(data)
            conversation_id, grace_deadline = _consume_lines(
                buffer, conversation_id, grace_deadline
            )


def _consume_lines(
    buffer: bytearray, conversation_id: str | None, grace_deadline: float | None
) -> tuple[str | None, float | None]:
    """Parse complete NDJSON lines, tracking the conversation id and result arrival."""
    while b"\n" in buffer:
        line, _, rest = buffer.partition(b"\n")
        buffer[:] = rest
        try:
            event = json.loads(line)
        except json.JSONDecodeError, UnicodeDecodeError:
            continue
        if event.get("event") == "init":
            conversation_id = event.get("conversation_id")
        elif event.get("event") == "result" and grace_deadline is None:
            sys.stdout.write(event.get("result", {}).get("response", ""))
            sys.stdout.flush()
            grace_deadline = time.monotonic() + FULLY_IDLE_GRACE_SECONDS
    return conversation_id, grace_deadline


def _fully_idle_or_ungoverned(
    stop_signal_path: str, conversation_id: str | None, grace_deadline: float
) -> bool:
    """True once fullyIdle is confirmed, or the Stop hook appears inactive."""
    matching = [
        record
        for record in _read_stop_signal_records(stop_signal_path)
        if record.get("conversationId") == conversation_id
    ]
    if any(record.get("fullyIdle") for record in matching):
        return True
    if matching:
        return False
    return time.monotonic() >= grace_deadline


def _read_stop_signal_records(path: str) -> list[dict]:
    """Read whatever fullyIdle observations the Stop hook has appended so far."""
    if not os.path.exists(path):
        return []
    records = []
    with open(path, "r", encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _close_stdin(process: subprocess.Popen[bytes]) -> None:
    """Close stdin, tolerating a child that already exited."""
    try:
        assert process.stdin is not None
        process.stdin.close()
    except BrokenPipeError:
        pass


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    """Gracefully stop a child process group, then force it if necessary."""
    try:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGINT)
        else:
            process.send_signal(getattr(signal, "CTRL_BREAK_EVENT", signal.SIGINT))
        process.wait(timeout=5)
    except ProcessLookupError, subprocess.TimeoutExpired:
        if process.poll() is None:
            process.kill()
            process.wait()
