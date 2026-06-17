#!/usr/bin/env python3
"""
wsl_setup.py — One-time setup and maintenance of WSL worker isolation.

Usage:
    py -3 .agentic/tools/wsl_setup.py setup     # create isolated WSL workspace
    py -3 .agentic/tools/wsl_setup.py status    # check isolation status
    py -3 .agentic/tools/wsl_setup.py sync      # pull latest into WSL workspace
    py -3 .agentic/tools/wsl_setup.py verify    # verify dependencies in WSL
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
AGENTIC_ROOT = SCRIPT_DIR.parent
CONFIG_PATH = AGENTIC_ROOT / "config" / "wsl_isolation.json"
STATUS_PATH = AGENTIC_ROOT / "context" / "wsl_status.json"
WORKER_EXEC_NAME = "wsl_worker_exec.sh"


class Log:
    CYAN, GREEN, YELLOW, RED, RESET = "\033[36m", "\033[32m", "\033[33m", "\033[31m", "\033[0m"

    @classmethod
    def _out(cls, tag: str, color: str, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {color}{tag:4}{cls.RESET}  {msg}"
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode("ascii", errors="replace").decode())

    @classmethod
    def info(cls, msg: str) -> None:
        cls._out("INFO", cls.CYAN, msg)

    @classmethod
    def ok(cls, msg: str) -> None:
        cls._out(" OK ", cls.GREEN, msg)

    @classmethod
    def warn(cls, msg: str) -> None:
        cls._out("WARN", cls.YELLOW, msg)

    @classmethod
    def error(cls, msg: str) -> None:
        cls._out(" ERR", cls.RED, msg)


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config not found: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def is_windows() -> bool:
    return platform.system() == "Windows"


def wsl_cmd(cfg: dict[str, Any], inner: str) -> list[str]:
    return ["wsl", "-d", cfg["distro"], "--", "sh", "-c", inner]


def run_local(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    Log.info("$ " + " ".join(cmd[:8]) + ("..." if len(cmd) > 8 else ""))
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, check=False)


def run_wsl(cfg: dict[str, Any], script: str) -> subprocess.CompletedProcess[str]:
    cmd = wsl_cmd(cfg, script)
    Log.info(f"WSL [{cfg['distro']}]: {script[:100]}...")
    return run_local(cmd)


def gh_login(cfg: dict[str, Any]) -> str:
    result = run_wsl(cfg, "gh api user --jq .login 2>/dev/null")
    return result.stdout.strip() if result.returncode == 0 else ""


def write_worker_exec_script(cfg: dict[str, Any]) -> None:
    """Deploy worker exec script into WSL workspace (LF line endings)."""
    project = cfg["project_path"]
    tools_dir = f"{project}/.agentic/tools"
    target = f"{tools_dir}/{WORKER_EXEC_NAME}"

    script = r"""#!/bin/sh
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
"""

    # Write to Windows path first (for git tracking), then copy to WSL workspace
    local_script = SCRIPT_DIR / WORKER_EXEC_NAME
    local_script.write_text(script, encoding="utf-8", newline="\n")

    run_wsl(cfg, f"mkdir -p '{tools_dir}'")
    # Copy via wsl cp from /mnt/c path
    win_script = str(local_script).replace("\\", "/")
    if is_windows() and len(win_script) > 1 and win_script[1] == ":":
        drive = win_script[0].lower()
        rest = win_script[2:].lstrip("/\\")
        wsl_src = f"/mnt/{drive}/{rest}"
    else:
        wsl_src = win_script

    run_wsl(cfg, f"cp '{wsl_src}' '{target}' && chmod +x '{target}'")
    Log.ok(f"Worker exec script: {target}")


def setup_git_identity(cfg: dict[str, Any]) -> None:
    login = gh_login(cfg)
    if not login:
        Log.warn("gh не авторизован в WSL — git identity не настроен")
        return
    email = f"{login}@users.noreply.github.com"
    project = cfg["project_path"]
    cmds = (
        f"cd '{project}' && "
        f"git config user.name '{login}' && "
        f"git config user.email '{email}'"
    )
    run_wsl(cfg, cmds)
    Log.ok(f"Git identity (local): {login} <{email}>")


def cmd_setup(cfg: dict[str, Any]) -> dict[str, Any]:
    Log.info("=== WSL Isolation Setup ===")
    project = cfg["project_path"]
    workspace = cfg["workspace_root"]
    repo_url = cfg["repo_url"]

    run_wsl(cfg, f"mkdir -p '{workspace}'")

    check = run_wsl(cfg, f"test -d '{project}/.git' && echo exists || echo missing")
    if "exists" in check.stdout:
        Log.info(f"Workspace уже существует: {project}")
        run_wsl(cfg, f"cd '{project}' && git remote -v && git pull --ff-only 2>/dev/null || true")
    else:
        Log.info(f"Клонирование {repo_url} -> {project}")
        result = run_wsl(cfg, f"git clone '{repo_url}' '{project}'")
        if result.returncode != 0:
            raise RuntimeError(f"git clone failed: {result.stderr or result.stdout}")

    setup_git_identity(cfg)
    write_worker_exec_script(cfg)

    # Verify tools
    verify = cmd_verify(cfg)
    status = {
        "setup_at": datetime.now(timezone.utc).isoformat(),
        "ready": verify.get("ready", False),
        "project_path": project,
        "distro": cfg["distro"],
        "checks": verify.get("checks", {}),
    }
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    Log.ok(f"WSL isolation ready: {project}")
    return status


def cmd_sync(cfg: dict[str, Any]) -> dict[str, Any]:
    project = cfg["project_path"]
    branch = cfg["default_branch"]
    result = run_wsl(
        cfg,
        f"cd '{project}' && git fetch origin && git checkout '{branch}' && git pull --ff-only origin '{branch}'",
    )
    ok = result.returncode == 0
    if ok:
        Log.ok(f"Synced {project} @ {branch}")
    else:
        Log.warn(f"Sync issue: {result.stderr or result.stdout}")
    return {"success": ok, "stdout": result.stdout, "stderr": result.stderr}


def cmd_verify(cfg: dict[str, Any]) -> dict[str, Any]:
    project = cfg["project_path"]
    checks: dict[str, Any] = {}

    for tool in ["python3", "git", "gh"]:
        r = run_wsl(cfg, f"command -v {tool} && {tool} --version 2>/dev/null | head -1")
        checks[tool] = {"ok": r.returncode == 0, "detail": (r.stdout or r.stderr).strip().split("\n")[0] if r.stdout or r.stderr else ""}

    r = run_wsl(cfg, f"test -d '{project}/.git' && echo ok")
    checks["workspace"] = {"ok": "ok" in r.stdout, "path": project}

    r = run_wsl(cfg, "gh auth status 2>&1 | head -3")
    checks["gh_auth"] = {"ok": r.returncode == 0 and "Logged in" in r.stdout, "detail": r.stdout.strip()[:200]}

    r = run_wsl(cfg, "command -v claude && claude --version 2>/dev/null | head -1")
    checks["claude_code"] = {"ok": r.returncode == 0, "detail": (r.stdout or "not installed — will use fallback").strip()}

    exec_path = f"{project}/.agentic/tools/{WORKER_EXEC_NAME}"
    r = run_wsl(cfg, f"test -x '{exec_path}' && echo ok")
    checks["worker_exec"] = {"ok": "ok" in r.stdout, "path": exec_path}

    ready = all(v.get("ok") for k, v in checks.items() if k != "claude_code")
    return {"ready": ready, "checks": checks}


def cmd_status(cfg: dict[str, Any]) -> dict[str, Any]:
    status: dict[str, Any] = {
        "config": {
            "enabled": cfg.get("enabled"),
            "distro": cfg.get("distro"),
            "project_path": cfg.get("project_path"),
        },
    }
    if STATUS_PATH.exists():
        status["last_setup"] = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    status["verify"] = cmd_verify(cfg)
    return status


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="WSL worker isolation setup")
    p.add_argument("command", choices=["setup", "status", "sync", "verify"])
    p.add_argument("--pretty", action="store_true")
    return p


def main() -> int:
    args = build_parser().parse_args()
    if not is_windows() and not os.environ.get("AGENTIC_WSL_SETUP"):
        Log.warn("Running inside WSL — executing directly")

    try:
        cfg = load_config()
        handlers = {
            "setup": cmd_setup,
            "sync": cmd_sync,
            "verify": cmd_verify,
            "status": cmd_status,
        }
        result = handlers[args.command](cfg)
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
        if args.command == "verify" and not result.get("ready"):
            return 1
        return 0
    except Exception as e:
        Log.error(str(e))
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
