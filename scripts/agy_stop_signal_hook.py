#!/usr/bin/env python3
"""Antigravity Stop hook: record fullyIdle so callers can await it externally.

Reads the Stop hook payload on stdin and appends one JSON line describing
`fullyIdle` (and identifying fields) to the file named by the
`AGYPYWPR_STOP_SIGNAL_FILE` environment variable. It never returns
`"decision": "continue"`, so it does not alter Antigravity's own stop
behavior or trigger additional model turns; it only exposes the signal.

If the environment variable is unset, or the payload cannot be parsed, this
is a no-op that still emits a valid empty decision so the hook chain is
never broken by this observer.
"""

from __future__ import annotations

import json
import os
import sys


def main() -> int:
    """Append one observation record, then always emit an empty decision."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}
    target = os.environ.get("AGYPYWPR_STOP_SIGNAL_FILE")
    if target and isinstance(payload, dict):
        record = {
            key: payload.get(key)
            for key in (
                "conversationId",
                "executionNum",
                "terminationReason",
                "error",
                "fullyIdle",
            )
        }
        with open(target, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
            stream.flush()
    sys.stdout.write("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
