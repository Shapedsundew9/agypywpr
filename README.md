# Python Template

A lightweight Python project template for building small CLI-based applications and package-friendly code.

## Overview

This repository provides a minimal starting point with:

- a Python package layout under `src/`
- a simple CLI entry point in `src/cli.py`
- project metadata in `pyproject.toml`
- a docs folder for project notes and guidance

## Project Structure

```text
.
├── .devcontainer/
├── .github/
├── docs/
├── src/
│   └── cli.py
├── .gitignore
├── .markdownlint-cli2.jsonc
├── GEMINI.md
├── LICENSE
├── pyproject.toml
├── README.md
└── .venv/
```

## Getting Started

1. Create or activate the project virtual environment.
2. Install the project in editable mode:

```bash
python -m pip install -e .
```

1. Run the CLI:

```bash
protoproject
```

This currently prints:

```text
Hello World!
```

## Development

You can extend the template by adding modules under `src/` and updating the package configuration in `pyproject.toml`.

### Example

```python
from cli import main
```

## Scripts and Tools

The project is configured with a console script entry point:

- `protoproject` -> `cli:main`

This makes it easy to expose a CLI command without adding custom boilerplate.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Notes

This is intentionally a simple starter repository. It is designed to be easy to customize for your own Python tools, scripts, or command-line apps.
