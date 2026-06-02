#!/usr/bin/env bash
# One-command launcher: sets up the venv, installs deps, and runs the server.
# Reads keys from backend/.env automatically (copy .env.example to .env first).
#
#   cd backend && ./start.sh
#
set -e
cd "$(dirname "$0")"

# Create the virtualenv on first run, then activate it.
if [ ! -d ".venv" ]; then
  echo "Creating virtualenv (.venv)..."
  python3 -m venv .venv
fi
source .venv/bin/activate

# Install/refresh dependencies (quiet, only does work when something changed).
pip install -q -r requirements.txt

# Pick the port (default 8000) and run.
PORT="${PORT:-8000}"
echo "Starting Innovator Awards Photobooth on http://localhost:${PORT}"
exec uvicorn app:app --host 0.0.0.0 --port "${PORT}"
