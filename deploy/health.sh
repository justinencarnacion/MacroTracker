#!/usr/bin/env bash
# Health and usage report for MacroTracker, run from your Mac.
#
#   ./deploy/health.sh
#
# Connects to the Pi (home network first, then the remote address), gathers
# system, bot, and usage data, prints a report with warnings, and appends a
# summary row to data/health_history.csv. Exits 1 if anything is critical.
# Override the host with HEALTH_HOST (e.g. HEALTH_HOST=macrotracker-remote).
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -n "${HEALTH_HOST:-}" ]; then
  HOST="$HEALTH_HOST"
elif ssh -o ConnectTimeout=4 -o BatchMode=yes macrotracker true 2>/dev/null; then
  HOST="macrotracker"
else
  HOST="macrotracker-remote"
fi

PYTHON="python3"
[ -x .venv/bin/python ] && PYTHON=".venv/bin/python"

echo "Checking MacroTracker via $HOST..."
collected="$(ssh -o ConnectTimeout=8 -o BatchMode=yes "$HOST" python3 - < deploy/health_collect.py)" \
  || { echo "❌ Can't reach the Pi as '$HOST'. Is it on, and are you on a network that can reach it?"; exit 1; }

github_commit=""
behind=""
if git fetch -q origin 2>/dev/null; then
  github_commit="$(git rev-parse origin/main)"
  deployed="$(printf '%s' "$collected" | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["bot"].get("commit") or "")')"
  if [ -n "$deployed" ] && git cat-file -e "$deployed" 2>/dev/null; then
    behind="$(git rev-list --count "$deployed..origin/main")"
  else
    behind="?"
  fi
fi

printf '%s' "$collected" | "$PYTHON" deploy/health_report.py \
  --history data/health_history.csv --github-commit "$github_commit" --behind "$behind"
