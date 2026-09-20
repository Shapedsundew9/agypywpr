#!/bin/bash

# This script runs after the container is created.
# The 'set -e' command ensures that the script will exit immediately if a command fails.
set -e

# Activating the virtual environment
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
