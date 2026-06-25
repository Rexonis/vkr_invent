#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export DJANGO_HTTPS=1
"$ROOT/.venv/Scripts/python.exe" -m uvicorn config.asgi:application \
  --app-dir "$ROOT/backend" \
  --host 0.0.0.0 \
  --port 5500 \
  --ssl-certfile "$ROOT/.certs/vkr-dev.crt" \
  --ssl-keyfile "$ROOT/.certs/vkr-dev.key"
