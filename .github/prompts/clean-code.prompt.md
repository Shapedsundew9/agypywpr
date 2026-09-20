# Clean Code

Execute these steps to maintain clean and readable code:

- For Python code changes, run the same analysis stack used by VS Code before finishing:
  inspect Pylance diagnostics in the editor and run `.venv/bin/python -m pylint src tests`.
- Ensure all issues reported by the analysis stack are addressed.
- Always run `markdownlint-cli2 --fix "**/*.md"` followed by `markdownlint-cli2 "**/*.md"` after Markdown changes.
- Do not suppress any warnings. If you think the code or documentation would be better with a suppression ask the user first.
