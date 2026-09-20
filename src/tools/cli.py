"""Command-line entry point for agypywpr."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .permissions import PermissionConfigError, parse_permission_document
from .runner import RunnerError, run_agy
from .settings import SettingsError, SettingsTransaction, restore_from_journal

DEFAULT_SETTINGS = Path.home() / ".gemini" / "antigravity-cli" / "settings.json"


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(prog="agypywpr")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="run one Antigravity prompt")
    run_parser.add_argument(
        "prompt_file",
        type=Path,
        nargs="?",
        default=None,
        help="path to prompt file",
    )
    run_parser.add_argument(
        "--prompt-file",
        dest="prompt_file_opt",
        type=Path,
        help=argparse.SUPPRESS,
    )
    run_parser.add_argument("--permissions-file", type=Path)
    run_parser.add_argument("--timeout", type=float, default=1800)
    restore_parser = subparsers.add_parser(
        "restore", help="restore a pending settings transaction"
    )
    restore_parser.add_argument("--settings-path", type=Path, default=DEFAULT_SETTINGS)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface."""
    raw_args = list(sys.argv[1:] if argv is None else argv)
    agy_arguments: list[str] = []
    if "--" in raw_args:
        index = raw_args.index("--")
        agy_arguments = raw_args[index + 1 :]
        raw_args = raw_args[:index]
    try:
        args = build_parser().parse_args(raw_args)
        args.agy_arguments = agy_arguments
        if args.command == "restore":
            restore_from_journal(args.settings_path.expanduser())
            return 0
        return _run(args)
    except (
        OSError,
        ValueError,
        PermissionConfigError,
        SettingsError,
        RunnerError,
    ) as error:
        print(f"agypywpr: {error}", file=sys.stderr)
        return 2


def _run(args: argparse.Namespace) -> int:
    """Run an Antigravity prompt with optional temporary permissions."""
    prompt_file = args.prompt_file or getattr(args, "prompt_file_opt", None)
    if prompt_file is None:
        raise ValueError("a prompt file is required for the run command")
    prompt = prompt_file.read_text(encoding="utf-8")
    additions = {"allow": [], "deny": [], "ask": []}
    if args.permissions_file is not None:
        additions = parse_permission_document(
            json.loads(args.permissions_file.read_text(encoding="utf-8"))
        )
    settings_path = DEFAULT_SETTINGS
    arguments = args.agy_arguments or []
    if any(additions.values()):
        with SettingsTransaction(settings_path, additions):
            result = run_agy(prompt, arguments, timeout=args.timeout)
    else:
        result = run_agy(prompt, arguments, timeout=args.timeout)
    if result.timed_out:
        return 124
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
