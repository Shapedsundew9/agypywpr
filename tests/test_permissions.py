import json
import tempfile
import unittest
from pathlib import Path

from tools.permissions import PermissionConfigError, augment_permissions, parse_permission_document
from tools.settings import SettingsTransaction


class PermissionTests(unittest.TestCase):
    def test_parse_and_merge_preserves_existing_rules(self) -> None:
        additions = parse_permission_document(
            {"permissions": {"allow": ["command(git)", "command(git)"], "deny": ["command(sudo)"]}}
        )
        settings = {"colorScheme": "terminal", "permissions": {"allow": ["command(make)"]}}
        merged = augment_permissions(settings, additions)
        self.assertEqual(merged["permissions"]["allow"], ["command(make)", "command(git)"])
        self.assertEqual(merged["permissions"]["deny"], ["command(sudo)"])
        self.assertEqual(settings["colorScheme"], "terminal")

    def test_rejects_unknown_category(self) -> None:
        with self.assertRaises(PermissionConfigError):
            parse_permission_document({"permissions": {"read": []}})

    def test_transaction_restores_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            original = b'{"permissions":{"allow":[]},"custom":true}\n'
            path.write_bytes(original)
            with SettingsTransaction(path, {"allow": ["command(git)"], "deny": [], "ask": []}):
                self.assertEqual(json.loads(path.read_text())["permissions"]["allow"], ["command(git)"])
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()