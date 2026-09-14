#!/usr/bin/env bash
# Idempotent Cloud Agent setup for py-autovod.
# Installs system media tooling, the uv package manager, and the project
# (with dev + lint dependencies) into a project-local virtual environment.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[install] Installing system dependencies (ffmpeg, streamlink)..."
sudo apt-get update -qq
sudo apt-get install -y -qq --no-install-recommends ffmpeg streamlink

echo "[install] Ensuring uv is available..."
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
uv --version

echo "[install] Creating virtual environment (.venv)..."
if [ ! -x .venv/bin/python ]; then
  uv venv --python 3.12 .venv
else
  echo "[install] .venv already exists, reusing it."
fi

echo "[install] Installing project with dev and lint dependencies..."
# flake8 is used by the lint CI workflow but is not declared in pyproject extras.
uv pip install --python .venv/bin/python -e ".[dev]" flake8

echo "[install] Done. Activate with: source .venv/bin/activate"
