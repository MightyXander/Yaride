#!/usr/bin/env python3
"""
worker_launcher.py — Launch isolated worker sessions for GitHub Issues.

Usage:
    python worker_launcher.py --issue-id 42 --prompt "Implement login endpoint"
    python worker_launcher.py --issue-id 42 --prompt "..." --no-wsl
    python worker_launcher.py --issue-id 42 --prompt "..." --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
AGENTIC_ROOT = SCRIPT_DIR.parent
CONFIG_DIR = AGENTIC_ROOT / "config"
PROMPTS_DIR = AGENTIC_ROOT / "prompts"
TOOLS_DIR = AGENTIC_ROOT / "tools"
WSL_CONFIG_PATH = CONFIG_DIR / "wsl_isolation.json"
WORKER_PROMPT = PROMPTS_DIR / "worker_system_prompt.md"
FALLBACK_RUNNER = TOOLS_DIR / "worker_fallback_runner.py"
WSL_WORKER_EXEC = TOOLS_DIR / "wsl_worker_exec.sh"

# Постоянный дефолт модели воркера. Закреплён также в worker_system_prompt.md
# и в wsl_worker_exec.sh (env WORKER_MODEL).
DEFAULT_WORKER_MODEL = "claude-sonnet-4-5"


# ── Logging ──────────────────────────────────────────────────────────────────

class Log:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"

    @classmethod
    def _ts(cls) -> str:
        return datetime.now().strftime("%H:%M:%S")

    @classmethod
    def banner(cls, title: str) -> None:
        line = "=" * 60
        cls._print(f"\n{cls.BLUE}{line}{cls.RESET}")
        cls._print(f"{cls.BLUE}{cls.BOLD}  {title}{cls.RESET}")
        cls._print(f"{cls.BLUE}{line}{cls.RESET}\n")

    @classmethod
    def _print(cls, msg: str, *, err: bool = False) -> None:
        stream = sys.stderr
        try:
            print(msg, file=stream)
        except UnicodeEncodeError:
            safe = msg.encode("ascii", errors="replace").decode("ascii")
            print(safe, file=stream)

    @classmethod
    def info(cls, msg: str) -> None:
        cls._print(f"{cls.DIM}[{cls._ts()}]{cls.RESET} {cls.CYAN}INFO{cls.RESET}  {msg}")

    @classmethod
    def step(cls, msg: str) -> None:
        cls._print(f"{cls.DIM}[{cls._ts()}]{cls.RESET} {cls.MAGENTA}STEP{cls.RESET}  {cls.BOLD}{msg}{cls.RESET}")

    @classmethod
    def ok(cls, msg: str) -> None:
        cls._print(f"{cls.DIM}[{cls._ts()}]{cls.RESET} {cls.GREEN} OK {cls.RESET}  {msg}")

    @classmethod
    def warn(cls, msg: str) -> None:
        cls._print(f"{cls.DIM}[{cls._ts()}]{cls.RESET} {cls.YELLOW}WARN{cls.RESET}  {msg}")

    @classmethod
    def error(cls, msg: str) -> None:
        cls._print(f"{cls.DIM}[{cls._ts()}]{cls.RESET} {cls.RED} ERR{cls.RESET}  {msg}", err=True)


# ── Utilities ────────────────────────────────────────────────────────────────

def find_project_root(start: Path | None = None) -> Path:
    """Walk up from start to find directory containing .agentic/."""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".agentic").is_dir():
            return candidate
    return current


def run_command(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    Log.step(f"$ {' '.join(cmd[:6])}{'...' if len(cmd) > 6 else ''}")
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def load_wsl_config() -> dict[str, Any] | None:
    if not WSL_CONFIG_PATH.exists():
        return None
    try:
        cfg = json.loads(WSL_CONFIG_PATH.read_text(encoding="utf-8"))
        return cfg if cfg.get("enabled") else None
    except (json.JSONDecodeError, OSError):
        return None


def is_inside_wsl() -> bool:
    return os.environ.get("AGENTIC_WSL_WORKER") == "1" or Path("/proc/version").exists() and "microsoft" in Path("/proc/version").read_text(encoding="utf-8", errors="ignore").lower()


def wsl_run(cfg: dict[str, Any], shell_cmd: str, *, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    cmd = ["wsl", "-d", cfg["distro"], "--", "sh", "-c", shell_cmd]
    return run_command(cmd, timeout=timeout)


def wsl_project_python(cfg: dict[str, Any]) -> str:
    return cfg.get("worker", {}).get("python", "python3")


def sync_wsl_workspace(cfg: dict[str, Any]) -> None:
    Log.step("Sync WSL workspace")
    project = cfg["project_path"]
    branch = cfg.get("default_branch", "main")
    result = wsl_run(
        cfg,
        f"cd '{project}' && git fetch origin && git checkout '{branch}' && git pull --ff-only origin '{branch}' 2>/dev/null || true",
    )
    if result.returncode == 0:
        Log.ok(f"WSL workspace synced: {project}")
    else:
        Log.warn(f"WSL sync warning: {(result.stderr or result.stdout)[:200]}")


def fetch_issue_context_wsl(issue_id: int, cfg: dict[str, Any]) -> dict[str, Any]:
    project = cfg["project_path"]
    py = wsl_project_python(cfg)
    result = wsl_run(
        cfg,
        f"cd '{project}' && {py} .agentic/tools/gh_manager.py read --issue {issue_id} --quiet --pretty",
    )
    if result.returncode != 0:
        raise RuntimeError(f"Не удалось прочитать Issue #{issue_id} в WSL: {result.stderr or result.stdout}")
    return json.loads(result.stdout.strip())


def ensure_git_branch_wsl(branch_name: str, cfg: dict[str, Any], base_branch: str) -> None:
    project = cfg["project_path"]
    Log.step(f"Подготовка ветки `{branch_name}` в WSL workspace")
    script = (
        f"cd '{project}' && "
        f"git fetch origin '{base_branch}' 2>/dev/null; "
        f"if git rev-parse --verify '{branch_name}' >/dev/null 2>&1; then "
        f"  git checkout '{branch_name}'; "
        f"else "
        f"  git checkout -b '{branch_name}' 'origin/{base_branch}' 2>/dev/null || git checkout -b '{branch_name}' '{base_branch}'; "
        f"fi"
    )
    result = wsl_run(cfg, script)
    if result.returncode != 0:
        raise RuntimeError(f"WSL branch setup failed: {result.stderr or result.stdout}")
    Log.ok(f"WSL branch ready: {branch_name}")


def launch_wsl_isolated_worker(
    issue_id: int,
    full_prompt: str,
    branch_name: str,
    cfg: dict[str, Any],
    project_root: Path,
    args: argparse.Namespace,
) -> subprocess.CompletedProcess[str]:
    """Run worker inside isolated WSL native workspace."""
    project = cfg["project_path"]
    exec_script = f"{project}/.agentic/tools/wsl_worker_exec.sh"
    py = wsl_project_python(cfg)

    prompt_path = save_worker_prompt(issue_id, full_prompt, project_root)
    prompt_rel = f".agentic/context/worker_prompts/issue-{issue_id}.md"
    wsl_src = to_wsl_path(prompt_path)
    wsl_run(cfg, f"mkdir -p '{project}/.agentic/context/worker_prompts'")
    wsl_run(cfg, f"cp '{wsl_src}' '{project}/{prompt_rel}'")

    if not args.skip_gh_update:
        Log.step("Обновление меток Issue -> in-progress (WSL)")
        wsl_run(
            cfg,
            f"cd '{project}' && {py} .agentic/tools/gh_manager.py update-labels "
            f"--issue {issue_id} --add 'status: in-progress' --remove 'status: todo'",
        )

    fallback_flag = "--force-fallback" if args.force_fallback else ""
    shell = (
        f"cd '{project}' && "
        f"export WORKER_MODEL='{args.model}' && "
        f"'{exec_script}' "
        f"--issue-id {issue_id} "
        f"--prompt-file '{project}/{prompt_rel}' "
        f"--branch '{branch_name}' "
        f"--base-branch '{args.base_branch}' "
        f"{fallback_flag}"
    )
    Log.info(f"WSL isolated worker @ {project} (model={args.model})")
    return wsl_run(cfg, shell, timeout=args.timeout)


def to_wsl_path(windows_path: Path) -> str:
    """Convert Windows path to WSL /mnt/c/... format."""
    resolved = windows_path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    rest = str(resolved).replace(resolved.drive + "\\", "").replace("\\", "/")
    return f"/mnt/{drive}/{rest}"


def fetch_issue_context(issue_id: int, project_root: Path) -> dict[str, Any]:
    """Load issue + comments via gh_manager.py."""
    gh_script = TOOLS_DIR / "gh_manager.py"
    result = run_command(
        [sys.executable, str(gh_script), "read", "--issue", str(issue_id), "--quiet", "--pretty"],
        cwd=project_root,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Не удалось прочитать Issue #{issue_id}: {result.stderr or result.stdout}")
    return json.loads(result.stdout.strip())


def ensure_git_branch(branch_name: str, project_root: Path, base_branch: str) -> None:
    """Create and checkout feature branch, or checkout if exists."""
    Log.step(f"Подготовка ветки `{branch_name}` от `{base_branch}`")

    status = run_command(["git", "status", "--porcelain"], cwd=project_root)
    if status.stdout.strip():
        Log.warn("Рабочая директория не чиста — воркер продолжит на текущем состоянии")

    # Fetch latest base
    run_command(["git", "fetch", "origin", base_branch], cwd=project_root)

    # Check if branch exists locally
    branch_check = run_command(["git", "rev-parse", "--verify", branch_name], cwd=project_root)
    if branch_check.returncode == 0:
        checkout = run_command(["git", "checkout", branch_name], cwd=project_root)
    else:
        # Try create from origin/base or local base
        checkout = run_command(["git", "checkout", "-b", branch_name, base_branch], cwd=project_root)
        if checkout.returncode != 0:
            checkout = run_command(["git", "checkout", "-b", branch_name], cwd=project_root)

    if checkout.returncode != 0:
        raise RuntimeError(f"Не удалось переключиться на ветку {branch_name}: {checkout.stderr}")

    Log.ok(f"Активная ветка: {branch_name}")


def build_worker_prompt(
    issue: dict[str, Any],
    user_prompt: str,
    worker_system_prompt: str,
    branch_name: str,
) -> str:
    """Assemble full prompt for worker agent."""
    comments_block = ""
    if issue.get("comments"):
        comments_block = "\n\n## Комментарии к Issue\n\n"
        for c in issue["comments"]:
            comments_block += f"**@{c['author']}** ({c.get('created_at', '?')}):\n{c['body']}\n\n---\n\n"

    return f"""{worker_system_prompt}

---

# ЗАДАЧА ВОРКЕРА

## GitHub Issue #{issue['number']}: {issue['title']}

**URL:** {issue['url']}
**Метки:** {', '.join(issue.get('labels', [])) or 'нет'}
**Ветка:** `{branch_name}`

## Описание Issue

{issue.get('body') or '_Описание отсутствует_'}
{comments_block}

## Дополнительные инструкции от Director

{user_prompt}

---

## Чеклист завершения

1. Реализуй задачу в ветке `{branch_name}`
2. Напиши/обнови тесты
3. Сделай git commit с понятным сообщением
4. Оставь детальный технический комментарий в Issue через gh_manager.py
5. Обнови метки Issue на `status: QA-review`
"""


def detect_claude_code() -> str | None:
    """Return path to claude CLI if available."""
    return shutil.which("claude")


def save_worker_prompt(issue_id: int, full_prompt: str, project_root: Path) -> Path:
    """Persist worker prompt for debugging and CLI handoff."""
    prompts_dir = project_root / ".agentic" / "context" / "worker_prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = prompts_dir / f"issue-{issue_id}.md"
    prompt_path.write_text(full_prompt, encoding="utf-8")
    Log.info(f"Worker prompt сохранён: {prompt_path.relative_to(project_root)}")
    return prompt_path


def launch_claude_code(
    full_prompt: str,
    project_root: Path,
    issue_id: int,
    timeout: int,
    model: str = DEFAULT_WORKER_MODEL,
) -> subprocess.CompletedProcess[str]:
    """Launch Claude Code in agentic mode."""
    Log.step(f"Запуск Claude Code (--agentic) на модели {model}")

    prompt_path = save_worker_prompt(issue_id, full_prompt, project_root)
    env = os.environ.copy()
    env["AGENTIC_WORKER"] = "1"
    env["WORKER_MODEL"] = model

    # Claude Code CLI v2+: claude -p --model <model> --dangerously-skip-permissions
    # Prompt передаётся через stdin (из сохранённого файла) чтобы обойти лимит аргументов
    attempts: list[list[str]] = [
        ["claude", "-p", "--model", model, "--dangerously-skip-permissions"],   # prompt via stdin
        ["claude", "-p", full_prompt, "--model", model, "--dangerously-skip-permissions"],  # short prompts
    ]

    last_result: subprocess.CompletedProcess[str] | None = None
    for i, cmd in enumerate(attempts):
        Log.info(f"Claude Code attempt {i + 1}/{len(attempts)}")
        if full_prompt in cmd and len(full_prompt) > 4000:
            Log.warn("Prompt слишком длинный для -p аргумента, пропускаем этот вариант")
            continue
        stdin_text = full_prompt if full_prompt not in cmd else None
        result = run_command(cmd, cwd=project_root, env=env, input_text=stdin_text, timeout=timeout)
        last_result = result
        if result.returncode == 0:
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            return result
        if result.returncode == 127:
            break

    Log.warn(f"Claude Code не ответил — prompt сохранён в {prompt_path}")
    if last_result:
        return last_result
    return subprocess.CompletedProcess(args=[], returncode=127, stdout="", stderr="claude not found")


def launch_fallback_runner(
    full_prompt: str,
    issue_id: int,
    project_root: Path,
    branch_name: str,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    """Fallback: autonomous Python runner when Claude Code unavailable."""
    Log.warn("Claude Code недоступен — запуск fallback runner")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(full_prompt)
        prompt_file = f.name

    try:
        cmd = [
            sys.executable,
            str(FALLBACK_RUNNER),
            "--prompt-file", prompt_file,
            "--issue-id", str(issue_id),
            "--branch", branch_name,
            "--project-root", str(project_root),
        ]
        return run_command(cmd, cwd=project_root, timeout=timeout)
    finally:
        try:
            os.unlink(prompt_file)
        except OSError:
            pass


def wrap_for_wsl(
    inner_cmd: list[str],
    project_root: Path,
) -> list[str]:
    """Wrap command to run inside WSL."""
    wsl_root = to_wsl_path(project_root)
    # Build bash command string
    cmd_str = " ".join(_shell_quote(arg) for arg in inner_cmd)
    bash_cmd = f"cd {_shell_quote(wsl_root)} && {cmd_str}"
    return ["wsl", "bash", "-lc", bash_cmd]


def _shell_quote(s: str) -> str:
    if not s:
        return "''"
    if all(c.isalnum() or c in "/._-" for c in s):
        return s
    return "'" + s.replace("'", "'\\''") + "'"


def update_session_state(project_root: Path, worker_record: dict[str, Any]) -> None:
    """Append worker launch record to session_state.json."""
    state_path = project_root / ".agentic" / "context" / "session_state.json"
    if not state_path.exists():
        return

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    state.setdefault("workers", {}).setdefault("history", []).append(worker_record)

    active = state["workers"].setdefault("active", [])
    active[:] = [w for w in active if w.get("worker_id") != worker_record.get("worker_id")]

    if worker_record.get("status") == "running":
        active.append(worker_record)
    else:
        state["metrics"]["workers_launched_session"] = (
            state.get("metrics", {}).get("workers_launched_session", 0) + 1
        )

    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def launch_worker(args: argparse.Namespace) -> dict[str, Any]:
    project_root = find_project_root()
    wsl_cfg = load_wsl_config()
    issue_id = args.issue_id
    branch_name = f"feature/issue-{issue_id}"
    worker_id = f"worker-{issue_id}-{uuid.uuid4().hex[:8]}"
    started_at = datetime.now(timezone.utc).isoformat()

    use_wsl_isolation = (
        args.wsl
        and platform.system() == "Windows"
        and wsl_cfg is not None
        and not is_inside_wsl()
    )

    if not args.base_branch:
        args.base_branch = (wsl_cfg or {}).get("default_branch", "main")

    Log.banner(f"Worker Launcher — Issue #{issue_id}")
    Log.info(f"Project root: {project_root}")
    Log.info(f"Worker ID: {worker_id}")
    if use_wsl_isolation:
        Log.info(f"WSL isolation: {wsl_cfg['project_path']}")

    worker_record: dict[str, Any] = {
        "worker_id": worker_id,
        "issue_id": issue_id,
        "branch": branch_name,
        "status": "running",
        "started_at": started_at,
        "finished_at": None,
        "exit_code": None,
    }
    update_session_state(project_root, worker_record)

    if args.dry_run:
        Log.warn("DRY RUN — воркер не будет запущен")
        Log.info(f"Модель воркера: {args.model}")
        return {
            "success": True,
            "dry_run": True,
            "worker_id": worker_id,
            "issue_id": issue_id,
            "branch": branch_name,
            "model": args.model,
            "project_root": str(project_root),
            "wsl_isolation": use_wsl_isolation,
            "wsl_project_path": wsl_cfg["project_path"] if wsl_cfg else None,
        }

    if use_wsl_isolation:
        sync_wsl_workspace(wsl_cfg)
        Log.step("Загрузка контекста Issue (WSL)")
        issue = fetch_issue_context_wsl(issue_id, wsl_cfg)
        Log.ok(f"Контекст загружен: «{issue['title']}»")
        ensure_git_branch_wsl(branch_name, wsl_cfg, args.base_branch)
        worker_system = WORKER_PROMPT.read_text(encoding="utf-8") if WORKER_PROMPT.exists() else ""
        full_prompt = build_worker_prompt(issue, args.prompt, worker_system, branch_name)
        result = launch_wsl_isolated_worker(issue_id, full_prompt, branch_name, wsl_cfg, project_root, args)
        runner = "wsl-isolated"
        use_wsl = True
    else:
        # Legacy/local path (WSL terminal directly or Linux/macOS)
        Log.step("Загрузка контекста Issue")
        issue = fetch_issue_context(issue_id, project_root)
        Log.ok(f"Контекст загружен: «{issue['title']}»")
        ensure_git_branch(branch_name, project_root, args.base_branch)
        worker_system = WORKER_PROMPT.read_text(encoding="utf-8") if WORKER_PROMPT.exists() else ""
        full_prompt = build_worker_prompt(issue, args.prompt, worker_system, branch_name)

        if not args.skip_gh_update:
            Log.step("Обновление меток Issue -> in-progress")
            gh_script = TOOLS_DIR / "gh_manager.py"
        run_command([
            sys.executable, str(gh_script), "update-labels",
            "--issue", str(issue_id),
            "--add", "status: in-progress",
            "--remove", "status: todo",
            "--quiet",
        ], cwd=project_root)

        use_wsl = args.wsl and platform.system() == "Windows"
        claude_available = detect_claude_code() is not None

        if use_wsl and wsl_cfg is None:
            Log.warn("WSL config missing — using legacy /mnt/c/ launch")
            if claude_available and not args.force_fallback:
                result = launch_claude_code(full_prompt, project_root, issue_id, args.timeout, args.model)
            else:
                result = launch_fallback_runner(full_prompt, issue_id, project_root, branch_name, args.timeout)
        elif claude_available and not args.force_fallback:
            result = launch_claude_code(full_prompt, project_root, issue_id, args.timeout, args.model)
        else:
            result = launch_fallback_runner(full_prompt, issue_id, project_root, branch_name, args.timeout)
        runner = "claude-code" if (detect_claude_code() and not args.force_fallback) else "fallback"

    finished_at = datetime.now(timezone.utc).isoformat()
    success = result.returncode == 0

    worker_record.update({
        "status": "completed" if success else "failed",
        "finished_at": finished_at,
        "exit_code": result.returncode,
        "runner": runner,
        "wsl": use_wsl,
        "wsl_project_path": wsl_cfg["project_path"] if use_wsl_isolation and wsl_cfg else None,
    })
    update_session_state(project_root, worker_record)

    if success:
        Log.ok(f"Воркер завершил работу успешно (exit 0)")
    else:
        Log.error(f"Воркер завершился с кодом {result.returncode}")

    return {
        "success": success,
        "worker_id": worker_id,
        "issue_id": issue_id,
        "branch": branch_name,
        "model": args.model,
        "exit_code": result.returncode,
        "started_at": started_at,
        "finished_at": finished_at,
        "runner": worker_record.get("runner", "unknown"),
        "wsl": worker_record.get("wsl", False),
        "wsl_project_path": worker_record.get("wsl_project_path"),
        "stdout_tail": (result.stdout or "")[-2000:],
        "stderr_tail": (result.stderr or "")[-2000:],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Worker Launcher — изолированный агент-исполнитель для GitHub Issue.",
    )
    parser.add_argument("--issue-id", type=int, required=True, help="Номер GitHub Issue")
    parser.add_argument("--prompt", required=True, help="Дополнительные инструкции от Director")
    parser.add_argument("--base-branch", default=None, help="Базовая ветка (default: from wsl_isolation.json or main)")
    parser.add_argument("--model", default=DEFAULT_WORKER_MODEL, help=f"Модель воркера, уходит в claude --model (default: {DEFAULT_WORKER_MODEL})")
    parser.add_argument("--timeout", type=int, default=3600, help="Таймаут в секундах (default: 3600)")
    parser.add_argument("--wsl", action="store_true", default=True, help="Запуск в WSL на Windows (default: True)")
    parser.add_argument("--no-wsl", dest="wsl", action="store_false", help="Не использовать WSL")
    parser.add_argument("--force-fallback", action="store_true", help="Принудительно использовать fallback runner")
    parser.add_argument("--skip-gh-update", action="store_true", help="Не обновлять метки Issue")
    parser.add_argument("--dry-run", action="store_true", help="Только подготовка, без запуска воркера")
    parser.add_argument("--pretty", action="store_true", help="Форматированный JSON-вывод")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        result = launch_worker(args)
        output = json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None)
        print(output)
        return 0 if result.get("success") else 1
    except Exception as e:
        Log.error(str(e))
        err = {"success": False, "error": str(e)}
        print(json.dumps(err, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
