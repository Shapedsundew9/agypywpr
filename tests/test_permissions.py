"""Tests for permission validation and temporary settings updates."""

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.cli import _run
from tools.permissions import (
    PermissionConfigError,
    augment_permissions,
    parse_permission_document,
)
from tools.runner import RunResult
from tools.settings import SettingsTransaction


class PermissionTests(unittest.TestCase):
    """Verify permission and settings transaction behavior."""

    def test_parse_and_merge_preserves_existing_rules(self) -> None:
        """Merge new rules without modifying existing settings."""
        additions = parse_permission_document(
            {
                "permissions": {
                    "allow": ["command(git)", "command(git)"],
                    "deny": ["command(sudo)"],
                }
            }
        )
        settings = {
            "colorScheme": "terminal",
            "permissions": {"allow": ["command(make)"]},
        }
        merged = augment_permissions(settings, additions)
        self.assertEqual(
            merged["permissions"]["allow"], ["command(make)", "command(git)"]
        )
        self.assertEqual(merged["permissions"]["deny"], ["command(sudo)"])
        self.assertEqual(settings["colorScheme"], "terminal")

    def test_rejects_unknown_category(self) -> None:
        """Reject unsupported permission categories."""
        with self.assertRaises(PermissionConfigError):
            parse_permission_document({"permissions": {"read": []}})

    def test_transaction_restores_exact_bytes(self) -> None:
        """Restore the original settings byte-for-byte."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            original = b'{"permissions":{"allow":[]},"custom":true}\n'
            path.write_bytes(original)
            with SettingsTransaction(
                path, {"allow": ["command(git)"], "deny": [], "ask": []}
            ):
                self.assertEqual(
                    json.loads(path.read_text())["permissions"]["allow"],
                    ["command(git)"],
                )
            self.assertEqual(path.read_bytes(), original)

    def test_transaction_accepts_settings_already_restored_by_child(self) -> None:
        """Accept cleanup when a child restored the original settings."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            original = b'{"permissions":{"allow":[]},"custom":true}\n'
            path.write_bytes(original)
            with SettingsTransaction(
                path, {"allow": ["command(git)"], "deny": [], "ask": []}
            ):
                path.write_bytes(original)
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(path.with_name(".settings.json.agypywpr-journal").exists())

    def test_run_without_permissions_does_not_open_settings_transaction(self) -> None:
        """Run directly when no temporary permissions were requested."""
        with tempfile.TemporaryDirectory() as directory:
            prompt_file = Path(directory) / "prompt.txt"
            prompt_file.write_text("prompt", encoding="utf-8")
            arguments = argparse.Namespace(
                prompt_file=prompt_file,
                permissions_file=None,
                timeout=5,
                agy_arguments=[],
            )
            with (
                patch("tools.cli.run_agy", return_value=RunResult(0)) as run_agy,
                patch("tools.cli.SettingsTransaction") as transaction,
            ):
                self.assertEqual(_run(arguments), 0)
            run_agy.assert_called_once_with("prompt", [], timeout=5)
            transaction.assert_not_called()


if __name__ == "__main__":
    unittest.main()
