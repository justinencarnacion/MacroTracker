#!/usr/bin/env bash
# Deploy the code on GitHub (origin/main) to the Raspberry Pi.
#
#   ./deploy.sh              check, test, then update and restart the bot on the Pi
#   ./deploy.sh --rollback   put the Pi back on the version it ran before the last deploy
#
# Secrets (.env, credentials.json) are never copied; scp them manually when they change.
# Override the target with DEPLOY_HOST (default: the "macrotracker" SSH alias).
set -euo pipefail

HOST="${DEPLOY_HOST:-macrotracker}"
BRANCH="main"
cd "$(dirname "$0")"

red() { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
fail() { red "✗ $*"; exit 1; }

case "${1:-}" in
  "") MODE="deploy" ;;
  --rollback) MODE="rollback" ;;
  -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
  *) fail "Unknown option '$1'. Use ./deploy.sh or ./deploy.sh --rollback" ;;
esac

if [ "$MODE" = "deploy" ]; then
  step "Checking git state"
  current_branch="$(git rev-parse --abbrev-ref HEAD)"
  [ "$current_branch" = "$BRANCH" ] || fail "You're on '$current_branch'. Switch to '$BRANCH' first."

  if [ -n "$(git status --porcelain)" ]; then
    red "✗ You have uncommitted changes:"
    git status --short
    fail "Commit and push them (or stash them) before deploying."
  fi

  git fetch --quiet origin
  unpushed="$(git log --oneline "origin/$BRANCH..HEAD")"
  if [ -n "$unpushed" ]; then
    red "✗ These commits aren't on GitHub yet:"
    echo "$unpushed"
    fail "Run 'git push origin $BRANCH' first."
  fi
  if [ -n "$(git log --oneline "HEAD..origin/$BRANCH")" ]; then
    echo "Note: GitHub has commits your Mac doesn't. Deploying GitHub's version."
  fi
  green "✓ Deploying $(git log -1 --format='%h %s' "origin/$BRANCH")"

  step "Running tests"
  python_bin="python3"
  [ -x .venv/bin/python ] && python_bin=".venv/bin/python"
  "$python_bin" -m unittest discover -s tests -t . >/dev/null 2>/tmp/macrotracker-tests.log \
    || { cat /tmp/macrotracker-tests.log; fail "Tests failed; nothing was deployed."; }
  green "✓ $(grep -E '^Ran ' /tmp/macrotracker-tests.log)"
fi

step "Connecting to $HOST"
ssh -o ConnectTimeout=8 -o BatchMode=yes "$HOST" true 2>/dev/null \
  || fail "Can't reach '$HOST'. Is the Pi on and are you on the same network?"
green "✓ Connected"

step "Updating the Pi"
ssh -T "$HOST" "bash -s -- $MODE $BRANCH" <<'REMOTE'
set -euo pipefail
mode="$1"; branch="$2"
cd ~/MacroTracker
previous_file=".deploy-previous"
current="$(git rev-parse HEAD)"

bot_running() { [ -n "$(docker compose ps --status running -q)" ]; }

if [ "$mode" = "rollback" ]; then
  [ -f "$previous_file" ] || { echo "✗ No earlier deploy recorded; nothing to roll back to."; exit 1; }
  target="$(cat "$previous_file")"
  if [ "$target" = "$current" ]; then
    echo "✗ The Pi is already on the previous version ($(git log -1 --format='%h %s'))."
    exit 1
  fi
  git checkout --quiet --detach "$target"
  echo "Rolled back from $(git log -1 --format='%h' "$current") to $(git log -1 --format='%h %s')"
else
  git fetch --quiet origin
  target="$(git rev-parse "origin/$branch")"
  if [ "$target" = "$current" ] && bot_running; then
    echo "✓ The Pi is already running $(git log -1 --format='%h %s'). Nothing to do."
    exit 0
  fi
  echo "$current" > "$previous_file"
  git checkout --quiet "$branch"
  git merge --quiet --ff-only "origin/$branch"
  echo "Updated $(git log -1 --format='%h' "$current") -> $(git log -1 --format='%h %s')"
fi

since="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
docker compose up -d --build --force-recreate

echo "Waiting for the bot to log in..."
for _ in $(seq 1 45); do
  if docker compose logs --since "$since" 2>&1 | grep "Logged in as" >/dev/null; then
    docker compose logs --since "$since" 2>&1 | grep -E "Connected to spreadsheet|Logged in as" | sed 's/^[^|]*| //'
    echo "✓ Bot is online"
    exit 0
  fi
  bot_running || break
  sleep 2
done

echo "✗ The bot didn't come online. Last log lines:"
docker compose logs --tail 30
exit 1
REMOTE

if [ "$MODE" = "rollback" ]; then
  green "✓ Rollback complete. Fix the problem, push, and run ./deploy.sh to move forward again."
else
  green "✓ Deploy complete"
fi
