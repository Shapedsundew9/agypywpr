"""Tests for agypywpr command-line interface."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.cli import build_parser, main
from tools.runner import RunResult


class CliTests(unittest.TestCase):
    """Verify command-line argument parsing and execution flow."""

    def test_run_positional_prompt_file(self) -> None:
        """Run an Antigravity prompt provided as a positional argument."""
        with tempfile.TemporaryDirectory() as directory:
            prompt_file = Path(directory) / "prompt.txt"
            prompt_file.write_text("hello from file", encoding="utf-8")
            with patch("tools.cli.run_agy", return_value=RunResult(0)) as mock_run:
                exit_code = main(["run", str(prompt_file)])
            self.assertEqual(exit_code, 0)
            mock_run.assert_called_once_with("hello from file", [], timeout=1800.0)

    def test_run_flag_prompt_file_backward_compatibility(self) -> None:
        """Accept --prompt-file for backward compatibility."""
        with tempfile.TemporaryDirectory() as directory:
            prompt_file = Path(directory) / "prompt.txt"
            prompt_file.write_text("hello backward compat", encoding="utf-8")
            with patch("tools.cli.run_agy", return_value=RunResult(0)) as mock_run:
                exit_code = main(["run", "--prompt-file", str(prompt_file)])
            self.assertEqual(exit_code, 0)
            mock_run.assert_called_once_with(
                "hello backward compat", [], timeout=1800.0
            )

    def test_run_missing_prompt_file_fails(self) -> None:
        """Error cleanly when no prompt file argument is provided."""
        with patch("sys.stderr.write"):
            exit_code = main(["run"])
        self.assertEqual(exit_code, 2)

    def test_run_with_permissions_and_timeout(self) -> None:
        """Pass permissions document and custom timeout to runner."""
        with tempfile.TemporaryDirectory() as directory:
            prompt_file = Path(directory) / "prompt.txt"
            prompt_file.write_text("prompt content", encoding="utf-8")
            perms_file = Path(directory) / "perms.json"
            perms_file.write_text(
                json.dumps({"permissions": {"allow": ["command(ls)"]}}),
                encoding="utf-8",
            )
            with (
                patch("tools.cli.SettingsTransaction") as mock_transaction,
                patch("tools.cli.run_agy", return_value=RunResult(0)) as mock_run,
            ):
                mock_transaction.return_value.__enter__.return_value = None
                exit_code = main(
                    [
                        "run",
                        str(prompt_file),
                        "--permissions-file",
                        str(perms_file),
                        "--timeout",
                        "60",
                    ]
                )
            self.assertEqual(exit_code, 0)
            mock_run.assert_called_once_with("prompt content", [], timeout=60.0)

    def test_run_forwards_passthrough_arguments(self) -> None:
        """Forward arguments after -- directly to agy."""
        with tempfile.TemporaryDirectory() as directory:
            prompt_file = Path(directory) / "prompt.txt"
            prompt_file.write_text("run prompt", encoding="utf-8")
            with patch("tools.cli.run_agy", return_value=RunResult(0)) as mock_run:
                exit_code = main(
                    [
                        "run",
                        str(prompt_file),
                        "--",
                        "--model",
                        "gemini",
                        "--effort",
                        "high",
                    ]
                )
            self.assertEqual(exit_code, 0)
            mock_run.assert_called_once_with(
                "run prompt",
                ["--model", "gemini", "--effort", "high"],
                timeout=1800.0,
            )

    def test_restore_invokes_recovery(self) -> None:
        """Invoke restore_from_journal on restore command."""
        with patch("tools.cli.restore_from_journal") as mock_restore:
            exit_code = main(["restore"])
        self.assertEqual(exit_code, 0)
        mock_restore.assert_called_once()

    def test_build_parser_structure(self) -> None:
        """Verify parser defines run and restore subcommands."""
        parser = build_parser()
        self.assertEqual(parser.prog, "agypywpr")


if __name__ == "__main__":
    unittest.main()
