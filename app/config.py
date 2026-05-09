from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    bot_token: str
    db_path: str


def load_settings() -> Settings:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    db_path = os.getenv("DB_PATH", "yaride.db").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set. Add it to environment or .env file.")
    return Settings(bot_token=token, db_path=db_path)
