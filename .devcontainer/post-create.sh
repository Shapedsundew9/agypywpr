#!/usr/bin/env bash

set -euo pipefail

npm install --global markdownlint-cli2@latest
markdownlint-cli2 --version

echo "Creating virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
else
    python3 -m venv --upgrade-deps .venv
    .venv/bin/pip install --upgrade pip
fi

if [[ -f requirements.txt ]]; then
    .venv/bin/python -m pip install -r requirements.txt
fi

if [[ -f pyproject.toml ]]; then
    .venv/bin/python -m pip install --editable .
fi

if ! command -v agy >/dev/null 2>&1 && ! command -v antigravity >/dev/null 2>&1; then
    curl --proto '=https' --tlsv1.2 -fsSL https://antigravity.google/cli/install.sh | bash
fi
