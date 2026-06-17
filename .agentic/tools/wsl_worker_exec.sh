#!/bin/sh
# Isolated WSL worker executor — do not run directly from Windows.
set -eu

ISSUE_ID=""
PROMPT_FILE=""
BRANCH=""
BASE_BRANCH="master"
FORCE_FALLBACK="0"

while [ $# -gt 0 ]; do
  case "$1" in
    --issue-id) ISSUE_ID="$2"; shift 2 ;;
    --prompt-file) PROMPT_FILE="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --base-branch) BASE_BRANCH="$2"; shift 2 ;;
    --force-fallback) FORCE_FALLBACK="1"; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$ISSUE_ID" ] || [ -z "$PROMPT_FILE" ] || [ -z "$BRANCH" ]; then
  echo "Missing required args" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

export AGENTIC_WSL_WORKER=1
export AGENTIC_ISSUE_ID="$ISSUE_ID"
export AGENTIC_WORKER_BRANCH="$BRANCH"
export HOME="${HOME:-/home/user}"
export PATH="/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin:$PATH"

echo "[WSL Worker] project=$PROJECT_ROOT branch=$BRANCH issue=$ISSUE_ID"

git fetch origin "$BASE_BRANCH" 2>/dev/null || true
if git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
  git checkout "$BRANCH"
else
  git checkout -b "$BRANCH" "origin/$BASE_BRANCH" 2>/dev/null || git checkout -b "$BRANCH" "$BASE_BRANCH"
fi

PYTHON=python3
WORKER_MODEL="${WORKER_MODEL:-claude-sonnet-4-5}"
PROMPT_CONTENT="$(cat "$PROMPT_FILE")"

echo "[WSL Worker] model=$WORKER_MODEL"

run_fallback() {
  exec "$PYTHON" "$SCRIPT_DIR/worker_fallback_runner.py" \
    --prompt-file "$PROMPT_FILE" \
    --issue-id "$ISSUE_ID" \
    --branch "$BRANCH" \
    --project-root "$PROJECT_ROOT"
}

if [ "$FORCE_FALLBACK" = "1" ]; then
  run_fallback
fi

if command -v claude >/dev/null 2>&1; then
  if claude code --agentic --model "$WORKER_MODEL" -p "$PROMPT_CONTENT" 2>/dev/null; then
    exit 0
  fi
  if printf '%s' "$PROMPT_CONTENT" | claude code --agentic --model "$WORKER_MODEL" 2>/dev/null; then
    exit 0
  fi
  if claude --model "$WORKER_MODEL" -p "$PROMPT_CONTENT" 2>/dev/null; then
    exit 0
  fi
  echo "[WSL Worker] Claude Code failed, falling back to Python runner" >&2
fi

run_fallback
