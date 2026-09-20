"""Offline checks for the Stop-hook fullyIdle observer script."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "agy_stop_signal_hook",
    Path(__file__).resolve().parents[1] / "scripts" / "agy_stop_signal_hook.py",
)
assert SPEC is not None and SPEC.loader is not None
hook = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hook)

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "agy_stop_signal_hook.py"
)


class StopSignalHookTests(unittest.TestCase):
    """Exercise the hook as a subprocess, matching how Antigravity invokes it."""

    def run_hook(self, payload: object, env_file: str | None) -> tuple[str, str]:
        """Invoke the hook script and return (stdout, file contents or '')."""
        env = {}
        if env_file is not None:
            env["AGYPYWPR_STOP_SIGNAL_FILE"] = env_file
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        contents = Path(env_file).read_text(encoding="utf-8") if env_file else ""
        return result.stdout, contents

    def test_records_fully_idle_true(self) -> None:
        """A completed conversation with no pending background work is recorded."""
        with tempfile.TemporaryDirectory() as directory:
            target = str(Path(directory) / "signals.jsonl")
            stdout, contents = self.run_hook(
                {
                    "conversationId": "conv-1",
                    "executionNum": 2,
                    "terminationReason": "model_stop",
                    "error": "",
                    "fullyIdle": True,
                },
                target,
            )
            self.assertEqual(stdout, "{}")
            record = json.loads(contents.splitlines()[0])
            self.assertEqual(record["conversationId"], "conv-1")
            self.assertTrue(record["fullyIdle"])

    def test_records_fully_idle_false(self) -> None:
        """A stop while background subagents remain active is recorded as such."""
        with tempfile.TemporaryDirectory() as directory:
            target = str(Path(directory) / "signals.jsonl")
            _, contents = self.run_hook(
                {"conversationId": "conv-1", "executionNum": 1, "fullyIdle": False},
                target,
            )
            record = json.loads(contents.splitlines()[0])
            self.assertFalse(record["fullyIdle"])

    def test_appends_multiple_records(self) -> None:
        """Successive stop events accumulate rather than overwrite the file."""
        with tempfile.TemporaryDirectory() as directory:
            target = str(Path(directory) / "signals.jsonl")
            self.run_hook({"conversationId": "conv-1", "fullyIdle": False}, target)
            self.run_hook({"conversationId": "conv-1", "fullyIdle": True}, target)
            lines = Path(target).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)

    def test_noop_without_target_env_var(self) -> None:
        """Without the env var, the hook is a safe no-op with an empty decision."""
        stdout, _ = self.run_hook({"conversationId": "conv-1", "fullyIdle": True}, None)
        self.assertEqual(stdout, "{}")

    def test_malformed_input_still_emits_decision(self) -> None:
        """Invalid JSON on stdin must not break the hook chain."""
        with tempfile.TemporaryDirectory() as directory:
            target = str(Path(directory) / "signals.jsonl")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH)],
                input="not json",
                capture_output=True,
                text=True,
                env={"AGYPYWPR_STOP_SIGNAL_FILE": target},
                check=True,
            )
            self.assertEqual(result.stdout, "{}")
            record = json.loads(
                Path(target).read_text(encoding="utf-8").splitlines()[0]
            )
            self.assertIsNone(record["conversationId"])


if __name__ == "__main__":
    unittest.main()
