"""Настройки Mini App API: путь к БД, токен бота для проверки initData, CORS и dev-режим."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(slots=True)
class WebAppSettings:
    bot_token: str
    db_path: str
    host: str = "0.0.0.0"
    port: int = 8080
    # Разрешённые источники для CORS (адрес фронтенда: vite dev / туннель / прод).
    cors_origins: list[str] = field(default_factory=lambda: ["*"])
    # initData действителен ограниченное время — защита от переиспользования старых данных.
    init_data_max_age_s: int = 24 * 3600
    # Dev-режим: если задан WEBAPP_DEV_USER_ID, при отсутствии initData используем этого пользователя
    # (для запуска фронта в обычном браузере без Telegram). В проде оставляем пустым.
    dev_user_id: int | None = None


def _split_origins(raw: str | None) -> list[str]:
    if not raw or not raw.strip():
        return ["*"]
    return [p.strip() for p in raw.split(",") if p.strip()]


def load_webapp_settings() -> WebAppSettings:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set. Add it to environment or .env file.")
    db_path = os.getenv("DB_PATH", "yaride.db").strip() or "yaride.db"
    dev_raw = os.getenv("WEBAPP_DEV_USER_ID", "").strip()
    return WebAppSettings(
        bot_token=token,
        db_path=db_path,
        host=os.getenv("WEBAPP_HOST", "0.0.0.0").strip() or "0.0.0.0",
        port=int(os.getenv("WEBAPP_PORT", "8080").strip() or "8080"),
        cors_origins=_split_origins(os.getenv("WEBAPP_CORS_ORIGINS")),
        init_data_max_age_s=int(os.getenv("WEBAPP_INIT_DATA_MAX_AGE_S", str(24 * 3600))),
        dev_user_id=int(dev_raw) if dev_raw else None,
    )
