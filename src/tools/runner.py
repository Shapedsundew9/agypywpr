"""Subprocess supervision for the Antigravity CLI."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from typing import Sequence


class RunnerError(RuntimeError):
    """Raised when the Antigravity process cannot be started or completed."""


class RunResult:
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
    """Run one prompt while keeping stdin open until the child exits."""
    command = [executable, "-p", prompt, *arguments]
    process_group = os.setsid if os.name != "nt" else None
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=None,
            stderr=None,
            start_new_session=process_group is not None,
            text=True,
        )
    except OSError as error:
        raise RunnerError(f"could not start {executable}: {error}") from error

    deadline = time.monotonic() + timeout
    try:
        while process.poll() is None:
            if time.monotonic() >= deadline:
                _stop_process(process)
                return RunResult(process.wait(), timed_out=True)
            time.sleep(0.1)
        return RunResult(process.returncode or 0)
    except KeyboardInterrupt:
        _stop_process(process)
        raise
    finally:
        if process.stdin is not None:
            process.stdin.close()


def _stop_process(process: subprocess.Popen[str]) -> None:
    """Gracefully stop a child process group, then force it if necessary."""
    try:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGINT)
        else:
            process.send_signal(getattr(signal, "CTRL_BREAK_EVENT", signal.SIGINT))
        process.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if process.poll() is None:
            process.kill()
            process.wait()
