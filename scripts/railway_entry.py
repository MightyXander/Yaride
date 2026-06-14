#!/usr/bin/env python3
"""Точка входа Docker/Railway: core (бот+API) или только админка.

На сервисе yaride-admin задайте переменную YARIDE_SERVICE=admin.
На yaride-core переменную не задавайте (или YARIDE_SERVICE=core).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent


def main() -> int:
    mode = os.getenv("YARIDE_SERVICE", "core").strip().lower()
    if mode == "admin":
        from admin.__main__ import main as admin_main

        admin_main()
        return 0

    # scripts/ не Python-пакет — запускаем start_prod.py как отдельный процесс.
    proc = subprocess.run([sys.executable, str(_SCRIPTS / "start_prod.py")], check=False)
    return int(proc.returncode or 0)


if __name__ == "__main__":
    raise SystemExit(main())
