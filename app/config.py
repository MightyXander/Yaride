from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    bot_token: str
    db_path: str
    didit_api_key: str
    didit_workflow_id: str
    didit_callback_url: str
    didit_base_url: str

    @property
    def didit_enabled(self) -> bool:
        return bool(self.didit_api_key and self.didit_workflow_id)


def load_settings() -> Settings:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    db_path = os.getenv("DB_PATH", "yaride.db").strip()
    didit_api_key = os.getenv("DIDIT_API_KEY", "").strip()
    didit_workflow_id = os.getenv("DIDIT_WORKFLOW_ID", "").strip()
    didit_callback_url = os.getenv("DIDIT_CALLBACK_URL", "").strip()
    didit_base_url = os.getenv("DIDIT_BASE_URL", "https://verification.didit.me/v3").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set. Add it to environment or .env file.")
    return Settings(
        bot_token=token,
        db_path=db_path,
        didit_api_key=didit_api_key,
        didit_workflow_id=didit_workflow_id,
        didit_callback_url=didit_callback_url,
        didit_base_url=didit_base_url,
    )
