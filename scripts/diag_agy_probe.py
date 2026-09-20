#!/usr/bin/env python3
"""Observe AGY streaming lifecycle without changing the production wrapper.

Logs omit tool arguments, tool outputs, and stderr text. Response text is
retained and may be sensitive; use only a non-sensitive diagnostic prompt.
An observation timeout is not evidence of task completion.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import selectors
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path


def event_details(value: object) -> dict:
    """Keep lifecycle metadata and response text, excluding arbitrary tool data."""
    if not isinstance(value, dict):
        return {"event": "unrecognized_json"}
    details = {"event": value.get("event")}
    for section in ("step_update", "result"):
        payload = value.get(section)
        if not isinstance(payload, dict):
            continue
        details[section] = {
            key: payload[key]
            for key in (
                "conversation_id",
                "step_index",
                "state",
                "step_type",
                "tool_name",
                "text_delta",
                "status",
                "response",
                "duration_seconds",
                "num_turns",
            )
            if key in payload
        }
        subagents = payload.get("subagent_info", {}).get("subagents", [])
        if subagents:
            details[section]["subagent_ids"] = [
                item.get("conversation_id") for item in subagents
            ]
    if "conversation_id" in value:
        details["conversation_id"] = value["conversation_id"]
    return details


class Capture:
    """Drain binary pipes without buffered-reader delays or partial-line blocking."""

    def __init__(
        self, process, output, selector, stop_signal_path: str | None = None
    ) -> None:
        self.process = process
        self.output = output
        self.selector = selector
        self.started = time.monotonic()
        self.buffers = {}
        for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            self.buffers[stream.fileno()] = bytearray()
            selector.register(stream, selectors.EVENT_READ, name)
        self.stop_signal_path = stop_signal_path
        self.stop_signal_offset = 0

    def record(self, event: str, **details) -> None:
        """Persist each observation immediately with elapsed monotonic time."""
        self.output.write(
            json.dumps(
                {
                    "elapsed": time.monotonic() - self.started,
                    "event": event,
                    **details,
                }
            )
            + "\n"
        )
        self.output.flush()

    def line(self, name: str, data: bytes) -> None:
        """Record structured stdout while omitting unstructured or diagnostic text."""
        if name == "stderr":
            self.record("stderr", byte_count=len(data))
            return
        try:
            self.record("stdout", message=event_details(json.loads(data)))
        except json.JSONDecodeError, UnicodeDecodeError:
            self.record("unparsed_stdout", byte_count=len(data))

    def poll_stop_signal(self) -> None:
        """Record any new Stop-hook fullyIdle observations written by the hook."""
        if self.stop_signal_path is None or not os.path.exists(self.stop_signal_path):
            return
        with open(self.stop_signal_path, "r", encoding="utf-8") as stream:
            stream.seek(self.stop_signal_offset)
            new_text = stream.read()
            self.stop_signal_offset = stream.tell()
        for line in new_text.splitlines():
            if not line.strip():
                continue
            try:
                self.record("stop_signal", **json.loads(line))
            except json.JSONDecodeError:
                self.record("unparsed_stop_signal", byte_count=len(line))

    def observe(self, duration: float) -> None:
        """Read until the deadline, or until the process and both pipes have ended."""
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            self.poll_stop_signal()
            if self.process.poll() is not None and not self.selector.get_map():
                return
            remaining = max(0, min(0.1, deadline - time.monotonic()))
            for key, _ in self.selector.select(remaining):
                data = os.read(key.fd, 65536)
                buffer = self.buffers[key.fd]
                buffer.extend(data)
                while b"\n" in buffer:
                    line, _, rest = buffer.partition(b"\n")
                    buffer[:] = rest
                    self.line(key.data, bytes(line))
                if not data:
                    if buffer:
                        self.line(key.data, bytes(buffer))
                    self.selector.unregister(key.fileobj)


def stop_group(process, sig: int) -> None:
    """Signal only the process group created by this probe (Linux/macOS)."""
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        pass


def prepare_stop_signal_env(
    observe_stop_signal: bool, directory: str
) -> tuple[dict, str | None]:
    """Build the child environment and, if requested, a fullyIdle observation file."""
    env = dict(os.environ)
    if not observe_stop_signal:
        return env, None
    descriptor, path = tempfile.mkstemp(
        prefix="agy-stop-signal-", suffix=".jsonl", dir=directory
    )
    os.close(descriptor)
    env["AGYPYWPR_STOP_SIGNAL_FILE"] = path
    return env, path


def shutdown(process, capture: Capture) -> None:
    """Close stdin, then escalate from EOF to SIGINT and SIGKILL with bounded waits."""
    try:
        process.stdin.close()
    except BrokenPipeError:
        pass
    capture.record("stdin_closed")
    try:
        capture.observe(5)
        if process.poll() is None:
            capture.record("interrupt_sent")
            stop_group(process, signal.SIGINT)
            capture.observe(2)
    finally:
        if process.poll() is None or capture.selector.get_map():
            capture.record("kill_sent")
            stop_group(process, signal.SIGKILL)
        process.wait(timeout=5)
    capture.poll_stop_signal()
    capture.record("exit", returncode=process.returncode)


def run_probe(
    timeout: float = 150.0,
    output_path: str | None = None,
    prompt_file: str = "tests/test_prompt.txt",
    observe_stop_signal: bool = False,
) -> int:
    """Run one bounded observation; exit zero is not proof of task success."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive and finite")
    executable = shutil.which("agy")
    if executable is None:
        raise FileNotFoundError("agy is not on PATH")
    prompt = Path(prompt_file).read_text(encoding="utf-8")
    if output_path is None:
        descriptor, output_path = tempfile.mkstemp(prefix="agy-probe-", suffix=".jsonl")
    else:
        descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    env, stop_signal_path = prepare_stop_signal_env(
        observe_stop_signal, str(Path(output_path).parent)
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        with (
            subprocess.Popen(
                [  # pylint: disable=duplicate-code
                    executable,
                    "--input-format",
                    "stream-json",
                    "--output-format",
                    "stream-json",
                    "--print-timeout",
                    "0",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                cwd=str(Path(__file__).resolve().parents[1]),
                env=env,
            ) as process,
            selectors.DefaultSelector() as selector,
        ):
            capture = Capture(process, output, selector, stop_signal_path)
            interrupted = False
            try:
                capture.record("spawn", pid=process.pid)
                process.stdin.write(
                    (
                        json.dumps({"event": "user", "message": {"content": prompt}})
                        + "\n"
                    ).encode()
                )
                process.stdin.flush()
                capture.record("sent_user_event")
                capture.observe(timeout)
                capture.record("observation_end", process_alive=process.poll() is None)
            except BrokenPipeError:
                capture.record("broken_pipe")
            except KeyboardInterrupt:
                interrupted = True
                capture.record("interrupted")
            finally:
                shutdown(process, capture)
    print(f"Observation log: {output_path}")
    if stop_signal_path is not None:
        print(f"Stop-signal log: {stop_signal_path}")
    return 130 if interrupted else process.returncode


def main() -> int:
    """Parse diagnostic options without modifying AGY settings or permissions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=150.0)
    parser.add_argument("--output")
    parser.add_argument("--prompt-file", default="tests/test_prompt.txt")
    parser.add_argument(
        "--observe-stop-signal",
        action="store_true",
        help="record Stop-hook fullyIdle observations via .agents/hooks.json",
    )
    args = parser.parse_args()
    return run_probe(
        args.timeout, args.output, args.prompt_file, args.observe_stop_signal
    )


if __name__ == "__main__":
    raise SystemExit(main())
