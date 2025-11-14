#!/usr/bin/env bash
set -euo pipefail
. .venv/bin/activate
uvicorn backend.app:app --host 0.0.0.0 --port 8000
