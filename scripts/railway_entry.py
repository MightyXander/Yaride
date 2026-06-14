#!/usr/bin/env python3
"""Точка входа Docker/Railway: core (бот+API) или только админка.

На сервисе yaride-admin задайте переменную YARIDE_SERVICE=admin.
На yaride-core переменную не задавайте (или YARIDE_SERVICE=core).
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    mode = os.getenv("YARIDE_SERVICE", "core").strip().lower()
    if mode == "admin":
        from admin.__main__ import main as admin_main

        admin_main()
        return 0
    from scripts.start_prod import main as core_main

    return core_main()


if __name__ == "__main__":
    raise SystemExit(main())
