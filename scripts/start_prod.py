#!/usr/bin/env python3
"""Production-оркестратор: webapp_api (healthcheck) + бот + опционально админка.

Используется в Docker/Railway. API слушает PORT (Railway) или WEBAPP_PORT.
БД по умолчанию на volume: /data/yaride.db (переопределяется DB_PATH).
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCS: list[tuple[str, subprocess.Popen[bytes], bool]] = []


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _spawn(name: str, args: list[str], *, fatal: bool = True) -> subprocess.Popen[bytes]:
    print(f"[yaride] starting {name}: {' '.join(args)}", flush=True)
    proc = subprocess.Popen(args, cwd=str(ROOT), env=os.environ.copy())  # noqa: S603
    PROCS.append((name, proc, fatal))
    return proc


def _terminate_all() -> None:
    for name, proc, _fatal in PROCS:
        if proc.poll() is not None:
            continue
        print(f"[yaride] stopping {name}…", flush=True)
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    PROCS.clear()


def _on_signal(signum: int, _frame: object) -> None:
    print(f"\n[yaride] signal {signum}, shutting down…", flush=True)
    _terminate_all()
    raise SystemExit(0)


def _wait_api(host: str, port: int, *, timeout_s: float = 90.0) -> bool:
    import urllib.error
    import urllib.request

    url = f"http://{host}:{port}/health"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as resp:  # noqa: S310
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.5)
    return False


def main() -> int:
    port_raw = os.getenv("PORT", "").strip() or os.getenv("WEBAPP_PORT", "8080").strip() or "8080"
    os.environ["WEBAPP_PORT"] = port_raw
    os.environ.setdefault("WEBAPP_HOST", "0.0.0.0")
    os.environ.setdefault("DB_PATH", "/data/yaride.db")

    skip_bot = _env_bool("YARIDE_SKIP_BOT")
    skip_admin = _env_bool("YARIDE_SKIP_ADMIN")
    bot_fatal = _env_bool("YARIDE_BOT_FATAL", default=True)

    db_path = Path(os.environ["DB_PATH"])
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if not os.getenv("BOT_TOKEN", "").strip() and not skip_bot:
        print("Ошибка: BOT_TOKEN не задан", file=sys.stderr)
        return 1

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    try:
        _spawn("webapp_api", [sys.executable, "-m", "webapp_api"], fatal=True)
        api_port = int(port_raw)
        print(f"[yaride] waiting for API on 127.0.0.1:{api_port}/health …", flush=True)
        if not _wait_api("127.0.0.1", api_port):
            print("Ошибка: API не ответил на /health", file=sys.stderr)
            _terminate_all()
            return 1
        print("[yaride] API ready", flush=True)

        if not skip_admin:
            os.environ.setdefault("ADMIN_HOST", "0.0.0.0")
            _spawn("admin", [sys.executable, "-m", "admin"], fatal=False)

        if not skip_bot:
            _spawn("bot", [sys.executable, "main.py"], fatal=bot_fatal)
    except Exception as exc:
        print(f"Ошибка запуска: {exc}", file=sys.stderr)
        _terminate_all()
        return 1

    print("[yaride] production stack running", flush=True)
    try:
        while True:
            alive: list[tuple[str, subprocess.Popen[bytes], bool]] = []
            for name, proc, fatal in PROCS:
                code = proc.poll()
                if code is None:
                    alive.append((name, proc, fatal))
                    continue
                if fatal:
                    print(f"[yaride] {name} завершился с кодом {code}", flush=True)
                    _terminate_all()
                    return code or 1
                print(f"[yaride] {name} завершился с кодом {code} (остальные работают)", flush=True)
            PROCS[:] = alive
            if not PROCS:
                print("[yaride] все процессы завершились", flush=True)
                return 0
            time.sleep(0.5)
    except KeyboardInterrupt:
        _terminate_all()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
