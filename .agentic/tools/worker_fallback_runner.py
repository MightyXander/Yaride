#!/usr/bin/env python3
"""
worker_fallback_runner.py — Autonomous fallback when Claude Code CLI is unavailable.

This script simulates a worker session by:
1. Reading the assembled worker prompt
2. Writing a structured task manifest for manual or scripted continuation
3. Providing hooks for integration with Claude API or other LLM backends

Extend `_execute_agent_loop()` to wire your preferred agent runtime.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
AGENTIC_ROOT = SCRIPT_DIR.parent
TOOLS_DIR = AGENTIC_ROOT / "tools"
MANIFEST_DIR = AGENTIC_ROOT / "context" / "worker_manifests"


def _relative_or_abs(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def log(level: str, msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    colors = {"INFO": "\033[36m", "WARN": "\033[33m", "ERR": "\033[31m", "OK": "\033[32m"}
    reset = "\033[0m"
    color = colors.get(level, "")
    print(f"[{ts}] {color}{level:4}{reset}  {msg}")


def run_gh_comment(issue_id: int, body: str, project_root: Path) -> bool:
    gh_script = TOOLS_DIR / "gh_manager.py"
    result = subprocess.run(
        [sys.executable, str(gh_script), "comment",
         "--issue", str(issue_id),
         "--body", body,
         "--add-labels", "status: blocked",
         "--remove-labels", "status: in-progress"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _execute_agent_loop(prompt: str, manifest_path: Path) -> int:
    """
    Placeholder for autonomous agent execution.

    To integrate Claude API, replace this function with your runtime:
      - Anthropic Messages API
      - Local LLM via ollama
      - Cursor SDK agent

    Returns exit code (0 = success).
    """
    log("WARN", "Autonomous agent loop не подключён — сохраняю manifest для ручного/внешнего запуска")
    log("INFO", f"Manifest: {manifest_path}")
    log("INFO", "Подключите _execute_agent_loop() к вашему LLM runtime или установите Claude Code CLI")
    return 2  # Exit 2 = needs external agent


def main() -> int:
    parser = argparse.ArgumentParser(description="Worker fallback runner")
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--issue-id", type=int, required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()

    project_root = Path(args.project_root)
    prompt_path = Path(args.prompt_file)
    prompt = prompt_path.read_text(encoding="utf-8")

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = MANIFEST_DIR / f"issue-{args.issue_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"

    manifest = {
        "issue_id": args.issue_id,
        "branch": args.branch,
        "project_root": str(project_root),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "prompt_file": str(prompt_path),
        "prompt_length": len(prompt),
        "status": "pending_external_agent",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    prompt_path.write_text(prompt, encoding="utf-8")  # persist alongside manifest

    log("INFO", f"Fallback runner — Issue #{args.issue_id}, branch `{args.branch}`")

    exit_code = _execute_agent_loop(prompt, manifest_path)

    if exit_code == 2:
        comment_body = (
            f"## Worker Fallback — требуется внешний агент\n\n"
            f"Claude Code CLI недоступен. Manifest сохранён:\n"
            f"`{_relative_or_abs(manifest_path, project_root)}`\n\n"
            f"**Ветка:** `{args.branch}`\n"
            f"**Статус:** ожидает подключения agent runtime\n"
        )
        run_gh_comment(args.issue_id, comment_body, project_root)
        log("WARN", "Issue помечен как blocked — подключите agent runtime или Claude Code")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
