"""Проверка Telegram initData по официальному алгоритму (HMAC-SHA256).

Док: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
secret_key = HMAC_SHA256(key="WebAppData", data=bot_token); затем сверяем hash от отсортированных
полей data_check_string. Так бэкенд доверяет личности пользователя без отдельного логина.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


@dataclass(frozen=True)
class TelegramAuthUser:
    tg_user_id: int
    first_name: str
    last_name: str | None
    username: str | None
    photo_url: str | None

    @property
    def display_name(self) -> str:
        parts = [self.first_name]
        if self.last_name:
            parts.append(self.last_name)
        name = " ".join(p for p in parts if p).strip()
        return name or (self.username or f"user{self.tg_user_id}")


def _data_check_string(pairs: list[tuple[str, str]]) -> str:
    # Все поля, кроме hash, сортируются по ключу и склеиваются как key=value\n.
    items = sorted(f"{k}={v}" for k, v in pairs if k != "hash")
    return "\n".join(items)


def validate_init_data(init_data: str, bot_token: str, *, max_age_s: int = 24 * 3600) -> TelegramAuthUser | None:
    """Проверяет подпись initData и срок годности; возвращает пользователя или None при невалидности."""
    if not init_data:
        return None
    pairs = parse_qsl(init_data, keep_blank_values=True)
    data = dict(pairs)
    received_hash = data.get("hash")
    if not received_hash:
        return None

    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    check_string = _data_check_string(pairs)
    expected = hmac.new(secret_key, check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        return None

    auth_date_raw = data.get("auth_date")
    if auth_date_raw:
        try:
            if max_age_s > 0 and (time.time() - int(auth_date_raw)) > max_age_s:
                return None
        except ValueError:
            return None

    user_raw = data.get("user")
    if not user_raw:
        return None
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        return None
    uid = user.get("id")
    if not isinstance(uid, int):
        return None
    return TelegramAuthUser(
        tg_user_id=uid,
        first_name=str(user.get("first_name") or ""),
        last_name=user.get("last_name"),
        username=user.get("username"),
        photo_url=user.get("photo_url"),
    )
