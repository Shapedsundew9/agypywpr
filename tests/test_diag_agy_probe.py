"""Offline checks for the diagnostic probe; never invoke the real AGY."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "diag_agy_probe",
    Path(__file__).resolve().parents[1] / "scripts" / "diag_agy_probe.py",
)
assert SPEC is not None and SPEC.loader is not None
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class DiagProbeTests(unittest.TestCase):
    """Exercise streaming capture with isolated fake executables and prompts."""

    def run_fake(
        self, body: str, observe_stop_signal: bool = False
    ) -> tuple[int, list[dict]]:
        """Run an isolated executable without touching repository fixtures."""
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "agy"
            executable.write_text(f"#!{sys.executable}\n{body}\n", encoding="utf-8")
            executable.chmod(0o700)
            prompt = Path(directory) / "prompt.txt"
            prompt.write_text("diagnostic", encoding="utf-8")
            output = Path(directory) / "output.jsonl"
            with patch.object(probe.shutil, "which", return_value=str(executable)):
                result = probe.run_probe(
                    0.3, str(output), str(prompt), observe_stop_signal
                )
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            return result, [
                json.loads(line) for line in output.read_text().splitlines()
            ]

    def test_stdin_lifecycle_and_partial_line(self) -> None:
        """Keep stdin open after a result and drain output emitted after EOF."""
        result, records = self.run_fake("""import os
import sys
import json
message = json.loads(sys.stdin.readline())
assert message["message"]["content"] == "diagnostic"
os.write(1, b'{"event":"result","result":{"status":"SUCCESS"}}\\n{"event":')
sys.stdin.read()
os.write(1, b'"after_eof"}\\n')
""")
        self.assertEqual(result, 0)
        events = [record["event"] for record in records]
        output = [record for record in records if record["event"] == "stdout"]
        self.assertEqual(output[0]["message"]["result"]["status"], "SUCCESS")
        self.assertLess(events.index("stdout"), events.index("stdin_closed"))
        self.assertEqual(output[1]["message"]["event"], "after_eof")
        self.assertTrue(
            next(item for item in records if item["event"] == "observation_end")[
                "process_alive"
            ]
        )
        self.assertEqual(records[-1]["returncode"], 0)

    def test_early_exit(self) -> None:
        """Preserve a child failure rather than reporting diagnostic success."""
        result, records = self.run_fake("raise SystemExit(7)")
        self.assertEqual(result, 7)
        self.assertEqual(records[-1]["returncode"], 7)

    def test_observes_stop_signal_transitions(self) -> None:
        """A fake Stop hook writing fullyIdle updates is captured in order."""
        result, records = self.run_fake(
            """import os
import sys
import json
sys.stdin.readline()
target = os.environ["AGYPYWPR_STOP_SIGNAL_FILE"]
with open(target, "a", encoding="utf-8") as handle:
    handle.write(json.dumps({"conversationId": "c1", "fullyIdle": False}) + "\\n")
os.write(1, b'{"event":"result","result":{"status":"SUCCESS"}}\\n')
with open(target, "a", encoding="utf-8") as handle:
    handle.write(json.dumps({"conversationId": "c1", "fullyIdle": True}) + "\\n")
""",
            observe_stop_signal=True,
        )
        self.assertEqual(result, 0)
        stop_signals = [
            record for record in records if record["event"] == "stop_signal"
        ]
        self.assertEqual([item["fullyIdle"] for item in stop_signals], [False, True])

    def test_event_filter(self) -> None:
        """Omit arbitrary tool data but retain spawn and completion metadata."""
        filtered = probe.event_details(
            {
                "event": "step_update",
                "step_update": {
                    "tool_info": {"output": "private"},
                    "subagent_info": {"subagents": [{"conversation_id": "child"}]},
                },
            }
        )
        self.assertEqual(filtered["step_update"], {"subagent_ids": ["child"]})


if __name__ == "__main__":
    unittest.main()
