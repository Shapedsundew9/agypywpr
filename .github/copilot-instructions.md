# Project Guidelines

## Layout

- This is a mixed Rust and Python workspace.
- Put reusable Python code in `python/src/tools/`.
- Put Python tests in `python/tests/`.
- Put one-off Python programs in `python/scripts/`.
- Do not mix Python files into the Rust `src/` or `tests/` directories.

## Python

- Use `.venv/bin/python`; the devcontainer installs `python/` as an editable package.
- Import reusable code as `tools`.
- Declare Python package dependencies in `python/pyproject.toml`.

## Services And Secrets

- PostgreSQL and Neo4j are available through Docker Compose but are not started by default.
- Read credentials and tokens from the existing environment variables.
- The environment variables may direct to a remote service. Do not assume a docker or local service is running.
- Never hard-code, print, or commit secret values.
- Relevant variables include `DATABASE_URL`, `NEO4J_URI`,
  `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`,
  `GEMINI_API_KEY`, `ARC_AGI_API`, and `HF_READ_TOKEN`.

## Validation

- Run `cargo fmt --check`, `cargo clippy`, and `cargo test` for Rust changes.
- Run `.venv/bin/python -m unittest discover -s python/tests -v` for Python changes.
- Keep intentional Markdown exceptions narrow and document them with a targeted configuration or inline suppression.
- Validate only the services and language surfaces affected by an experiment.

## 3rd Party Packages

- Agents are explicitly authorized to install any pip packages or Rust crates needed to implement functionality efficiently that meet the criteria below.
  - Well-established, high-quality, maintained packages (e.g., `numpy`, `scipy`, `rand`, `serde`) that are fully supported.
  - Always declare added dependencies in the appropriate project file:
    - Python: declare in `python/pyproject.toml` and install into `.venv` (`.venv/bin/pip install <pkg>`).
    - Rust: declare in `Cargo.toml` or add via `cargo add <crate>`.
- Do not pull in obscure, single-maintainer, or redundant packages if the task is trivial in-house.

## Finally

- Always run `markdownlint-cli2 --fix "**/*.md"` followed by `markdownlint-cli2 "**/*.md"` to ensure there are no remaining formatting issues.