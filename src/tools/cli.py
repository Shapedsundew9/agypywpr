"""Command-line entry point for agypywpr."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .permissions import PermissionConfigError, parse_permission_document
from .runner import RunnerError, run_agy
from .settings import SettingsError, SettingsTransaction, restore_from_journal

DEFAULT_SETTINGS = Path.home() / ".gemini" / "antigravity-cli" / "settings.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agypywpr")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="run one Antigravity prompt")
    run_parser.add_argument("--prompt-file", type=Path, required=True)
    run_parser.add_argument("--permissions-file", type=Path)
    run_parser.add_argument("--timeout", type=float, default=1800)
    run_parser.add_argument("--", dest="agy_arguments", nargs=argparse.REMAINDER)
    restore_parser = subparsers.add_parser("restore", help="restore a pending settings transaction")
    restore_parser.add_argument("--settings-path", type=Path, default=DEFAULT_SETTINGS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "restore":
            restore_from_journal(args.settings_path.expanduser())
            return 0
        return _run(args)
    except (OSError, ValueError, PermissionConfigError, SettingsError, RunnerError) as error:
        print(f"agypywpr: {error}", file=os.sys.stderr)
        return 2


def _run(args: argparse.Namespace) -> int:
    prompt = args.prompt_file.read_text(encoding="utf-8")
    additions = {"allow": [], "deny": [], "ask": []}
    if args.permissions_file is not None:
        additions = parse_permission_document(
            json.loads(args.permissions_file.read_text(encoding="utf-8"))
        )
    settings_path = DEFAULT_SETTINGS
    arguments = args.agy_arguments or []
    with SettingsTransaction(settings_path, additions):
        result = run_agy(prompt, arguments, timeout=args.timeout)
    if result.timed_out:
        return 124
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
