"""Настройки админки. Отдельно от app.config: бот требует BOT_TOKEN, а админке он нужен только для уведомлений."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(slots=True)
class AdminSettings:
    db_path: str
    session_secret: str
    host: str
    port: int
    bot_token: str | None
    notify_enabled: bool
    database_url: str | None = None


def load_admin_settings() -> AdminSettings:
    """Конфиг из окружения. Сессионный секрет берём из ADMIN_SESSION_SECRET; иначе генерируем эфемерный."""
    load_dotenv()
    db_path = os.getenv("DB_PATH", "yaride.db").strip() or "yaride.db"
    database_url = os.getenv("DATABASE_URL", "").strip() or None
    secret = os.getenv("ADMIN_SESSION_SECRET", "").strip()
    ephemeral = not secret
    if ephemeral:
        # Эфемерный секрет: при рестарте сессии сбросятся. Для постоянного входа задайте ADMIN_SESSION_SECRET.
        secret = secrets.token_urlsafe(32)
    bot_token = os.getenv("BOT_TOKEN", "").strip() or None
    notify_enabled = _env_bool("ADMIN_NOTIFY_USERS", True) and bot_token is not None
    port_raw = os.getenv("PORT", "").strip() or os.getenv("ADMIN_PORT", "").strip()
    default_host = "0.0.0.0" if os.getenv("PORT", "").strip() else "127.0.0.1"
    return AdminSettings(
        db_path=db_path,
        database_url=database_url,
        session_secret=secret,
        host=os.getenv("ADMIN_HOST", default_host).strip() or default_host,
        port=int(port_raw) if port_raw else 8000,
        bot_token=bot_token,
        notify_enabled=notify_enabled,
    )


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer: {raw!r}") from exc
