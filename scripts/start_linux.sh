#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
: "${ASTERION_API_TOKEN:?Set a 32+ character ASTERION_API_TOKEN first}"
export ASTERION_REMOTE_ROOT="${ASTERION_REMOTE_ROOT:-$HOME}"
uvicorn asterion_remote.app:app --host 127.0.0.1 --port 8911
