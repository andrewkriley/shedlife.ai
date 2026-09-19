#!/bin/sh
set -eu
cd /app/backend
# uv sync installs the project into .venv
# shellcheck disable=SC1091
. .venv/bin/activate
alembic upgrade head
exec uvicorn theshed.main:app --host 0.0.0.0 --port 8080
