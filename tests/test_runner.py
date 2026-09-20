"""Tests for Antigravity subprocess supervision."""

import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import runner
from tools.runner import run_agy


class RunnerTests(unittest.TestCase):
    """Verify streaming subprocess handling, fullyIdle waiting, and timeouts."""

    def _script(self, directory: str, body: str) -> Path:
        path = Path(directory) / "fake-agy"
        path.write_text(f"#!{sys.executable}\n{body}\n", encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def test_sends_streaming_user_event_and_closes_after_grace_period(self) -> None:
        """Without an active Stop hook, close stdin shortly after the result."""
        with tempfile.TemporaryDirectory() as directory:
            executable = self._script(
                directory,
                """import json
import sys
message = json.loads(sys.stdin.readline())
assert message["message"]["content"] == "prompt"
sys.stdout.write(json.dumps({"event": "init", "conversation_id": "c1"}) + "\\n")
sys.stdout.write(
    json.dumps({"event": "result", "result": {"response": "done"}}) + "\\n"
)
sys.stdout.flush()
sys.stdin.read()
""",
            )
            with patch.object(runner, "FULLY_IDLE_GRACE_SECONDS", 0.2):
                result = run_agy("prompt", [], executable=str(executable), timeout=5)
            self.assertEqual(result.returncode, 0)
            self.assertFalse(result.timed_out)

    def test_waits_for_fully_idle_before_closing_stdin(self) -> None:
        """Keep stdin open past the result until the Stop hook reports fullyIdle."""
        with tempfile.TemporaryDirectory() as directory:
            executable = self._script(
                directory,
                """import json
import os
import sys
import time
sys.stdin.readline()
sys.stdout.write(json.dumps({"event": "init", "conversation_id": "c1"}) + "\\n")
sys.stdout.write(
    json.dumps({"event": "result", "result": {"response": "done"}}) + "\\n"
)
sys.stdout.flush()
target = os.environ["AGYPYWPR_STOP_SIGNAL_FILE"]
with open(target, "a", encoding="utf-8") as handle:
    handle.write(json.dumps({"conversationId": "c1", "fullyIdle": False}) + "\\n")
time.sleep(0.4)
with open(target, "a", encoding="utf-8") as handle:
    handle.write(json.dumps({"conversationId": "c1", "fullyIdle": True}) + "\\n")
sys.stdin.read()
""",
            )
            with patch.object(runner, "FULLY_IDLE_GRACE_SECONDS", 0.05):
                started = time.monotonic()
                result = run_agy("prompt", [], executable=str(executable), timeout=5)
                elapsed = time.monotonic() - started
            self.assertEqual(result.returncode, 0)
            self.assertFalse(result.timed_out)
            self.assertGreaterEqual(elapsed, 0.4)

    def test_timeout_stops_child(self) -> None:
        """Stop the child process after the configured timeout."""
        with tempfile.TemporaryDirectory() as directory:
            executable = self._script(directory, "import time\ntime.sleep(30)\n")
            result = run_agy("prompt", [], executable=str(executable), timeout=0.2)
            self.assertTrue(result.timed_out)


if __name__ == "__main__":
    unittest.main()
