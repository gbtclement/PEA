#!/bin/sh
set -e
alembic upgrade head
python -m app.cli bootstrap-admin
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
