#!/bin/sh
set -eu

cd /app

if [ "${KEYNETRA_RUN_MIGRATIONS:-1}" = "1" ]; then
  alembic -c /app/alembic.ini upgrade head
fi

# Docker uses uvicorn directly, so render the startup dashboard explicitly.
if [ "${KEYNETRA_STARTUP_SCREEN:-1}" = "1" ]; then
  python - <<'PY'
import os
from keynetra.cli import _render_startup_screen
from keynetra.config.settings import get_settings

host = os.getenv("KEYNETRA_HOST", "0.0.0.0")
port = int(os.getenv("KEYNETRA_PORT", "8000"))
settings = get_settings()
_render_startup_screen(
    host=host,
    port=port,
    reload=False,
    settings=settings,
    config_path=os.getenv("KEYNETRA_CONFIG"),
)
PY
fi

export KEYNETRA_LOG_FORMAT="${KEYNETRA_LOG_FORMAT:-rich}"
export KEYNETRA_FORCE_COLOR="${KEYNETRA_FORCE_COLOR:-1}"

exec uvicorn keynetra.api.main:app \
  --host "${KEYNETRA_HOST:-0.0.0.0}" \
  --port "${KEYNETRA_PORT:-8000}" \
  --proxy-headers \
  --forwarded-allow-ips "*" \
  --workers "${KEYNETRA_UVICORN_WORKERS:-2}"
