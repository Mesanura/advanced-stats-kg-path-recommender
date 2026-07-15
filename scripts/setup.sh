#!/usr/bin/env bash

set -euo pipefail

export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
if [[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]]; then
  SCRIPT_DIR="."
fi
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"

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

PIP_NETWORK_ARGS=(--disable-pip-version-check --timeout 30 --retries 2)

"$VENV_PYTHON" -m pip --version
if ! "$VENV_PYTHON" -m pip install --no-index \
  -r "$ROOT/backend/requirements.txt" \
  -r "$ROOT/backend/requirements-dev.txt" >/dev/null 2>&1; then
  "$VENV_PYTHON" -m pip install "${PIP_NETWORK_ARGS[@]}" \
    -r "$ROOT/backend/requirements.txt" \
    -r "$ROOT/backend/requirements-dev.txt"
fi

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
