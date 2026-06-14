#!/usr/bin/env python3
"""Чеклист и подсказки перед деплоем на Railway (без доступа к аккаунту Railway)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = [
    ROOT / "Dockerfile",
    ROOT / "railway.toml",
    ROOT / "scripts" / "start_prod.py",
    ROOT / "miniapp" / "Dockerfile",
    ROOT / "miniapp" / "railway.toml",
]
DOCS = ROOT / "docs" / "operations" / "railway-deploy.md"


def main() -> int:
    ok = True
    for path in REQUIRED:
        if path.exists():
            print(f"  OK  {path.relative_to(ROOT)}")
        else:
            print(f"  MISS {path.relative_to(ROOT)}")
            ok = False

    if not ok:
        return 1

    miniapp_out = ROOT / "miniapp" / ".output" / "server" / "index.mjs"
    if miniapp_out.is_file():
        print(f"  OK  {miniapp_out.relative_to(ROOT)} (локальная сборка)")
    else:
        print("  INFO miniapp/.output нет локально — соберётся в Docker на Railway")

    print(f"\nИнструкция: {DOCS.relative_to(ROOT)}")
    print("\nДальше (нужен login в Railway):")
    print("  railway login")
    print("  railway init          # или Deploy from GitHub в Dashboard")
    print("  railway up            # из корня — сервис yaride-core")
    print("\nНе забудьте Volume /data и переменные из .env.example (секция Railway).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
