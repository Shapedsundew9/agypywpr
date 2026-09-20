"""Tests for Antigravity subprocess supervision."""

import stat
import tempfile
import unittest
from pathlib import Path

from tools.runner import run_agy


class RunnerTests(unittest.TestCase):
    """Verify subprocess handling and timeout behavior."""

    def _script(self, directory: str, body: str) -> Path:
        path = Path(directory) / "fake-agy"
        path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def test_keeps_stdin_open_until_child_exits(self) -> None:
        """Preserve standard input while the child process runs."""
        with tempfile.TemporaryDirectory() as directory:
            executable = self._script(
                directory,
                """[ "$1" = "-p" ] && [ "$2" = "prompt" ]
                [ "$3" = "--model" ] && [ "$4" = "test" ]
                exit 7""",
            )
            result = run_agy(
                "prompt", ["--model", "test"], executable=str(executable), timeout=2
            )
            self.assertEqual(result.returncode, 7)
            self.assertFalse(result.timed_out)

    def test_timeout_stops_child(self) -> None:
        """Stop the child process after the configured timeout."""
        with tempfile.TemporaryDirectory() as directory:
            executable = self._script(directory, "sleep 30")
            result = run_agy("prompt", [], executable=str(executable), timeout=0.1)
            self.assertTrue(result.timed_out)
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
