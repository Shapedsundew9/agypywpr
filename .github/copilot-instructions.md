# Project Guidelines

## Repository Layout

- This is a Python-only package repository.
- The package project is configured by the repository-root `pyproject.toml`.
- Use the `src` layout: reusable package code belongs in `src/tools/`.
- Tests belong in `tests/` and should import the installed package as `tools`.
- Put one-off developer utilities in `scripts/`.
- Keep build artifacts such as `dist/`, `build/`, and `*.egg-info/` out of commits unless the repository explicitly tracks them.
- Be explicitly aware that GEMINI.md is a symbolic link to .github/copilot-instructions.md

## Python Development

- Use the repository virtual environment at `.venv/` and its interpreter, `.venv/bin/python`.
- Install the project and development dependencies from the repository root with:
  `.venv/bin/python -m pip install --editable '.[dev]'`.
- Declare runtime and development dependencies in `pyproject.toml`; do not add ad hoc requirements files.
- Keep the supported Python version and package metadata in `pyproject.toml` accurate.
- Follow existing code style and public APIs. Avoid unrelated refactors.
- Never hard-code, print, or commit credentials, API keys, tokens, or other secrets.

## Validation

- Run Python tests with `.venv/bin/python -m unittest discover -s tests -v`.
- When changing packaging metadata, build the distribution from the repository root with:
  `.venv/bin/python -m build`.
- Inspect the generated wheel and source archive when packaging changes affect included files or entry points.
- Run focused checks for the files and behavior changed before running broader validation.
- Keep intentional Markdown exceptions narrow and document them with targeted configuration or inline suppression.

## PyPI Publishing

- Build distributions from the repository root; never publish directly from a working tree.
- Verify package metadata and archives before release. Use `twine check` when Twine is available.
- Publish through the repository's configured CI release workflow and PyPI Trusted Publishing where possible.
- Never place PyPI credentials in source files, configuration committed to the repository, command history, or logs.
- Do not change the package name, version, supported Python range, or console entry points without checking the release impact.

## Dependencies

- Prefer well-established, maintained packages when a dependency is genuinely needed.
- Add every new dependency to the appropriate section of `pyproject.toml` and install it in `.venv` before validating.
- Avoid introducing a dependency for functionality that is small and clear to implement with the standard library.

## Documentation

- Keep `README.md` aligned with the install, usage, development, and publishing workflows.
