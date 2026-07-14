#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  VENV_PYTHON="$ROOT/.venv/bin/python"
elif [[ -x "$ROOT/.venv/Scripts/python.exe" ]]; then
  VENV_PYTHON="$ROOT/.venv/Scripts/python.exe"
else
  echo "Run scripts/setup.sh before running the test suite." >&2
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

(
  cd "$ROOT/backend"
  "$VENV_PYTHON" -m pytest --cov=app --cov-report=term-missing
)

(
  cd "$ROOT/frontend"
  CI=true "$PNPM" test:coverage
  "$PNPM" build
)
