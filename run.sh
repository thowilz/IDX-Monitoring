#!/usr/bin/env bash
# One-command runner for macOS / Linux.
#   ./run.sh             # refresh data + build dashboard, then open it
#   ./run.sh --review    # also run the watchdog methodology review
#   ./run.sh --module coal
# Any extra args are passed straight to scripts/run_refresh.py.
#
# It is idempotent: creates the venv + installs deps only the first time,
# loads .env if present, then runs and opens render/index.html.
set -euo pipefail

cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

# 1. venv (created once)
if [ ! -d ".venv" ]; then
  echo "==> creating virtualenv (.venv)"
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# 2. deps (install/upgrade only if requirements changed)
if [ ! -f ".venv/.deps_ok" ] || [ requirements.txt -nt ".venv/.deps_ok" ]; then
  echo "==> installing deps from requirements.txt"
  pip install --quiet --upgrade pip
  pip install --quiet -r requirements.txt
  touch .venv/.deps_ok
fi

# 3. load secrets if present (FRED_API_KEY etc.)
if [ -f ".env" ]; then
  set -a; # shellcheck disable=SC1091
  source .env; set +a
else
  echo "==> note: no .env found. sbn10y/reserves will be STALE without FRED_API_KEY."
  echo "         cp .env.example .env  and add a free key from"
  echo "         https://fred.stlouisfed.org/docs/api/api_key.html"
fi

# 4. run
python scripts/run_refresh.py "$@"

# 5. open the dashboard (macOS: open, Linux: xdg-open)
if [ -f "render/index.html" ]; then
  if command -v open >/dev/null 2>&1; then
    open render/index.html
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open render/index.html
  else
    echo "==> dashboard ready: render/index.html"
  fi
fi
