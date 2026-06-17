#!/usr/bin/env python3
"""
gh_manager.py — GitHub Issue manager via local `gh` CLI.

Usage:
    python gh_manager.py create --title "..." --body "..." --labels "status: todo"
    python gh_manager.py read --issue 42
    python gh_manager.py comment --issue 42 --body "..." --add-labels "status: QA-review"
    python gh_manager.py update-labels --issue 42 --add "status: done" --remove "status: todo"
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
WSL_CONFIG_PATH = SCRIPT_DIR.parent / "config" / "wsl_isolation.json"
_wsl_cfg: dict[str, Any] | None = None


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
    quiet = False

    @classmethod
    def _print(cls, msg: str) -> None:
        if cls.quiet:
            return
        stream = sys.stderr
        try:
            print(msg, file=stream)
        except UnicodeEncodeError:
            safe = msg.encode("ascii", errors="replace").decode("ascii")
            print(safe, file=stream)

    @classmethod
    def _ts(cls) -> str:
        return datetime.now().strftime("%H:%M:%S")

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
        cls._print(f"{cls.DIM}[{cls._ts()}]{cls.RESET} {cls.RED} ERR{cls.RESET}  {msg}")


# ── gh CLI wrapper ───────────────────────────────────────────────────────────

class GhError(Exception):
    def __init__(self, message: str, returncode: int = 1, stderr: str = ""):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


def load_wsl_config() -> dict[str, Any] | None:
    if not WSL_CONFIG_PATH.exists():
        return None
    try:
        cfg = json.loads(WSL_CONFIG_PATH.read_text(encoding="utf-8"))
        return cfg if cfg.get("enabled") else None
    except (json.JSONDecodeError, OSError):
        return None


def repo_from_config(cfg: dict[str, Any]) -> str | None:
    if cfg.get("repo"):
        return cfg["repo"]
    url = cfg.get("repo_url", "")
    if "github.com/" in url:
        part = url.split("github.com/")[-1].rstrip("/").removesuffix(".git")
        return part or None
    return None


def should_use_wsl_gh() -> bool:
    global _wsl_cfg
    if platform.system() != "Windows":
        return False
    if shutil.which("gh"):
        return False
    _wsl_cfg = load_wsl_config()
    return _wsl_cfg is not None


def run_gh_wsl(cfg: dict[str, Any], args: list[str], *, input_text: str | None = None) -> str:
    """Run gh inside WSL without shell interpolation (safe for special chars)."""
    distro = cfg.get("distro", "Ubuntu-24.04")
    project = cfg["project_path"]
    gh_args = list(args)

    if gh_args and gh_args[0] == "api":
        repo = repo_from_config(cfg)
        if repo:
            owner, name = repo.split("/", 1)
            gh_args = [
                a.replace("{owner}/{repo}", repo)
                .replace("{owner}", owner)
                .replace("{repo}", name)
                for a in gh_args
            ]

    cmd = ["wsl", "-d", distro, "--cd", project, "--", "gh", *gh_args]
    Log.step(f"WSL gh {' '.join(gh_args[:3])}{'...' if len(gh_args) > 3 else ''}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_text,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise GhError(f"gh (WSL) завершился с кодом {result.returncode}: {stderr}", result.returncode, stderr)
    return result.stdout.strip()


def run_gh(args: list[str], *, input_text: str | None = None) -> str:
    """Execute `gh` with given arguments and return stdout."""
    if should_use_wsl_gh():
        assert _wsl_cfg is not None
        return run_gh_wsl(_wsl_cfg, args, input_text=input_text)

    cmd = ["gh", *args]
    Log.step(f"gh {' '.join(args[:4])}{'...' if len(args) > 4 else ''}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            input=input_text,
            check=False,
        )
    except FileNotFoundError:
        raise GhError(
            "Команда `gh` не найдена. Установите GitHub CLI или настройте WSL: "
            "py -3 .agentic/tools/wsl_setup.py setup",
            returncode=127,
        )

    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise GhError(f"gh завершился с кодом {result.returncode}: {stderr}", result.returncode, stderr)

    return result.stdout.strip()


def get_repo() -> str | None:
    """Return current repo in owner/name format, or None."""
    try:
        out = run_gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
        return out or None
    except GhError:
        cfg = load_wsl_config()
        if cfg:
            return repo_from_config(cfg)
        return None


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_create(args: argparse.Namespace) -> dict[str, Any]:
    Log.info(f"Создание Issue: «{args.title}»")

    gh_args = ["issue", "create", "--title", args.title, "--body", args.body or ""]

    if args.labels:
        for label in _split_labels(args.labels):
            gh_args.extend(["--label", label])

    if args.assignee:
        gh_args.extend(["--assignee", args.assignee])

    url = run_gh(gh_args)
    Log.ok(f"Issue создан: {url}")

    # Extract issue number from URL
    issue_number = url.rstrip("/").split("/")[-1]
    issue_data = cmd_read(_make_namespace(issue=int(issue_number)))
    return {"success": True, "url": url, "issue": issue_data}


def cmd_read(args: argparse.Namespace) -> dict[str, Any]:
    issue_num = args.issue
    Log.info(f"Чтение Issue #{issue_num}")

    issue_json = run_gh([
        "issue", "view", str(issue_num),
        "--json", "number,title,body,state,labels,author,createdAt,updatedAt,url,assignees,milestone",
    ])
    issue = json.loads(issue_json)

    Log.step(f"Загрузка комментариев к Issue #{issue_num}")
    comments_json = run_gh([
        "api", f"repos/{{owner}}/{{repo}}/issues/{issue_num}/comments",
        "--paginate",
    ])
    comments = json.loads(comments_json) if comments_json else []

    Log.ok(f"Issue #{issue_num}: «{issue['title']}» — {len(comments)} комментар(иев/я)")

    return {
        "number": issue["number"],
        "title": issue["title"],
        "body": issue["body"],
        "state": issue["state"],
        "url": issue["url"],
        "labels": [lb["name"] for lb in issue.get("labels", [])],
        "author": issue.get("author", {}).get("login"),
        "created_at": issue.get("createdAt"),
        "updated_at": issue.get("updatedAt"),
        "assignees": [a["login"] for a in issue.get("assignees", [])],
        "comments": [
            {
                "id": c["id"],
                "author": c.get("user", {}).get("login"),
                "body": c["body"],
                "created_at": c.get("created_at"),
                "updated_at": c.get("updated_at"),
            }
            for c in comments
        ],
    }


def cmd_comment(args: argparse.Namespace) -> dict[str, Any]:
    issue_num = args.issue
    Log.info(f"Добавление комментария к Issue #{issue_num}")

    run_gh(["issue", "comment", str(issue_num), "--body", args.body])
    Log.ok("Комментарий добавлен")

    if args.add_labels or args.remove_labels:
        label_result = cmd_update_labels(_make_namespace(
            issue=issue_num,
            add=args.add_labels,
            remove=args.remove_labels,
        ))
        return {"success": True, "comment_added": True, "labels": label_result}

    return {"success": True, "comment_added": True}


def cmd_update_labels(args: argparse.Namespace) -> dict[str, Any]:
    issue_num = args.issue
    added: list[str] = []
    removed: list[str] = []

    for label in _split_labels(args.add or ""):
        Log.step(f"Добавление метки «{label}» к Issue #{issue_num}")
        run_gh(["issue", "edit", str(issue_num), "--add-label", label])
        added.append(label)

    for label in _split_labels(args.remove or ""):
        Log.step(f"Удаление метки «{label}» с Issue #{issue_num}")
        run_gh(["issue", "edit", str(issue_num), "--remove-label", label])
        removed.append(label)

    if added or removed:
        Log.ok(f"Метки обновлены: +{added}, -{removed}")
    else:
        Log.warn("Метки не указаны — изменений нет")

    return {"success": True, "added": added, "removed": removed}


def cmd_list(args: argparse.Namespace) -> dict[str, Any]:
    Log.info("Получение списка открытых Issues")
    labels = _split_labels(args.labels) if args.labels else []
    gh_args = ["issue", "list", "--json", "number,title,labels,state,url", "--limit", str(args.limit)]

    for label in labels:
        gh_args.extend(["--label", label])

    if args.state:
        gh_args.extend(["--state", args.state])

    raw = run_gh(gh_args)
    issues = json.loads(raw) if raw else []
    Log.ok(f"Найдено Issues: {len(issues)}")
    return {"success": True, "issues": issues, "count": len(issues)}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _split_labels(labels: str) -> list[str]:
    if not labels:
        return []
    return [lb.strip() for lb in labels.replace(";", ",").split(",") if lb.strip()]


def _make_namespace(**kwargs: Any) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


def _output(data: dict[str, Any], args: argparse.Namespace) -> None:
    if getattr(args, "quiet", False):
        print(json.dumps(data, ensure_ascii=False, indent=2 if args.pretty else None))
        return
    if args.pretty:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(data, ensure_ascii=False))


# ── CLI ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--pretty", action="store_true", help="Форматированный JSON-вывод")
    parent.add_argument("-q", "--quiet", action="store_true", help="Только JSON, без логов (для скриптов)")

    parser = argparse.ArgumentParser(
        description="GitHub Issue manager — обёртка над `gh` CLI для agentic-оркестрации.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # create
    p_create = sub.add_parser("create", parents=[parent], help="Создать новый Issue")
    p_create.add_argument("--title", required=True, help="Заголовок Issue")
    p_create.add_argument("--body", default="", help="Тело Issue (markdown)")
    p_create.add_argument("--labels", help="Метки через запятую, напр. 'status: todo,area: backend'")
    p_create.add_argument("--assignee", help="GitHub username исполнителя")

    # read
    p_read = sub.add_parser("read", parents=[parent], help="Прочитать Issue и все комментарии")
    p_read.add_argument("--issue", type=int, required=True, help="Номер Issue")

    # comment
    p_comment = sub.add_parser("comment", parents=[parent], help="Добавить комментарий и опционально сменить метки")
    p_comment.add_argument("--issue", type=int, required=True)
    p_comment.add_argument("--body", required=True, help="Текст комментария")
    p_comment.add_argument("--add-labels", dest="add_labels", help="Добавить метки")
    p_comment.add_argument("--remove-labels", dest="remove_labels", help="Удалить метки")

    # update-labels
    p_labels = sub.add_parser("update-labels", parents=[parent], help="Изменить метки Issue")
    p_labels.add_argument("--issue", type=int, required=True)
    p_labels.add_argument("--add", help="Метки для добавления")
    p_labels.add_argument("--remove", help="Метки для удаления")

    # list
    p_list = sub.add_parser("list", parents=[parent], help="Список Issues")
    p_list.add_argument("--labels", help="Фильтр по меткам")
    p_list.add_argument("--state", choices=["open", "closed", "all"], default="open")
    p_list.add_argument("--limit", type=int, default=20)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not getattr(args, "quiet", False):
        Log.info("gh_manager — GitHub Issue Manager")
        if should_use_wsl_gh() and _wsl_cfg:
            Log.info(f"gh через WSL ({_wsl_cfg['distro']}): {_wsl_cfg['project_path']}")
        repo = get_repo()
        if repo:
            Log.info(f"Репозиторий: {repo}")
        elif args.command != "read":
            Log.warn("Репозиторий не определён — проверьте wsl_setup или git remote")
    else:
        Log.quiet = True

    handlers = {
        "create": cmd_create,
        "read": cmd_read,
        "comment": cmd_comment,
        "update-labels": cmd_update_labels,
        "list": cmd_list,
    }

    try:
        result = handlers[args.command](args)
        _output(result, args)
        return 0
    except GhError as e:
        Log.error(str(e))
        _output({"success": False, "error": str(e), "returncode": e.returncode}, args)
        return e.returncode
    except json.JSONDecodeError as e:
        Log.error(f"Ошибка парсинга JSON от gh: {e}")
        _output({"success": False, "error": str(e)}, args)
        return 1


if __name__ == "__main__":
    sys.exit(main())
