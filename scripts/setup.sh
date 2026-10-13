#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then
  if command -v uv >/dev/null; then uv venv --python 3.12 .venv
  else "${PYTHON:-python3}" -m venv .venv
  fi
fi
if command -v uv >/dev/null; then uv pip install --python .venv/bin/python -r requirements.txt
else .venv/bin/python -m pip install -r requirements.txt
fi
.venv/bin/python scripts/download_model.py
(cd frontend && npm ci && npm run build)
echo 'Ready. Start with ./scripts/start.sh'
