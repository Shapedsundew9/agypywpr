# agypywpr

`agypywpr` runs a one-shot Google Antigravity CLI task with temporary permission
rules. It backs up `~/.gemini/antigravity-cli/settings.json`, augments the
permission lists, runs `agy`, and restores the original settings afterward.

## Installation

Antigravity CLI must already be installed and authenticated as `agy`.

```bash
python3 -m pip install agypywpr
```

Run a prompt from a UTF-8 file:

```bash
agypywpr run --prompt-file prompt.txt --permissions-file permissions.json
```

Arguments after `--` are passed to `agy`:

```bash
agypywpr run --prompt-file prompt.txt -- --model gemini
```

The default timeout is 30 minutes. Use `--timeout SECONDS` to override it.

## Permission file

The permission file contains an additive fragment. Existing settings are not
replaced.

```json
{
  "permissions": {
    "allow": ["command(git)", "write_file(src/)"],
    "deny": ["command(sudo)"],
    "ask": ["command(*)"]
  }
}
```

Rules are deduplicated within each list. Antigravity evaluates conflicting
rules using its documented precedence: deny, then ask, then allow.

## Recovery

The wrapper uses a lock, a mode-`0600` recovery journal, and atomic settings
writes. If the process is forcibly killed, inspect the settings and run:

```bash
agypywpr restore
```

The current release targets Linux and macOS. The completion behavior for
background Antigravity subagents is under compatibility testing because AGY's
headless completion protocol is not documented.

## Development

```bash
.venv/bin/python -m pip install --editable '.[dev]'
.venv/bin/python -m unittest discover -s tests -v
```

Build the wheel and source distribution from the repository root:

```bash
.venv/bin/python -m build
```

## Publishing

Releases are published from GitHub through PyPI Trusted Publishing (OIDC).
Configure a protected `pypi` GitHub Environment and register the repository's
pending Trusted Publisher on PyPI before creating a release tag.
