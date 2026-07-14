#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"

if [[ -n "${PYTHON_BIN:-}" ]]; then
  BOOTSTRAP_PYTHON="$PYTHON_BIN"
elif command -v python3 >/dev/null 2>&1; then
  BOOTSTRAP_PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
  BOOTSTRAP_PYTHON="python"
else
  echo "Python 3.13 is required." >&2
  exit 1
fi

if command -v pnpm >/dev/null 2>&1; then
  PNPM="pnpm"
elif command -v pnpm.cmd >/dev/null 2>&1; then
  PNPM="pnpm.cmd"
else
  echo "pnpm 11 is required." >&2
  exit 1
fi

if [[ ! -d "$ROOT/.venv" ]]; then
  "$BOOTSTRAP_PYTHON" -m venv "$ROOT/.venv"
fi

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  VENV_PYTHON="$ROOT/.venv/bin/python"
elif [[ -x "$ROOT/.venv/Scripts/python.exe" ]]; then
  VENV_PYTHON="$ROOT/.venv/Scripts/python.exe"
else
  echo "The virtual environment does not contain a Python executable." >&2
  exit 1
fi

"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install \
  -r "$ROOT/backend/requirements.txt" \
  -r "$ROOT/backend/requirements-dev.txt"

(
  cd "$ROOT/frontend"
  CI=true "$PNPM" install
)

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
fi

(
  cd "$ROOT/backend"
  "$VENV_PYTHON" -m alembic upgrade head
  "$VENV_PYTHON" -m app.cli seed
  "$VENV_PYTHON" -m app.cli diagnose --algorithm rule
  "$VENV_PYTHON" -m app.cli diagnose --algorithm bkt
)

echo "Dependencies and demo data are ready."
