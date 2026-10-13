#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  echo 'Run ./scripts/setup.sh first.' >&2
  exit 1
fi
if [ ! -f frontend/dist/index.html ]; then
  (cd frontend && npm ci && npm run build)
fi
export YOLO_CONFIG_DIR="${YOLO_CONFIG_DIR:-$PWD/data/yolo}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-$PWD/data/matplotlib}"
echo "Roadwatch: http://127.0.0.1:${PORT:-8011}"
exec .venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port "${PORT:-8011}"
