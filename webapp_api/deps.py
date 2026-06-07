"""FastAPI-зависимости: доступ к repo/настройкам и текущий пользователь из Telegram initData."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request, status

from app.repo import Repo
from webapp_api.auth import TelegramAuthUser, validate_init_data
from webapp_api.config import WebAppSettings


def get_settings(request: Request) -> WebAppSettings:
    return request.app.state.settings


def get_repo(request: Request) -> Repo:
    return request.app.state.repo


def get_auth_user(
    request: Request,
    x_init_data: str | None = Header(default=None, alias="X-Init-Data"),
    settings: WebAppSettings = Depends(get_settings),
) -> TelegramAuthUser:
    """Возвращает проверенного пользователя Telegram. Заголовок X-Init-Data несёт WebApp.initData.

    В dev-режиме (WEBAPP_DEV_USER_ID задан) при отсутствии initData подставляем тестового пользователя —
    чтобы фронт работал в обычном браузере без Telegram.
    """
    if x_init_data:
        user = validate_init_data(x_init_data, settings.bot_token, max_age_s=settings.init_data_max_age_s)
        if user is not None:
            return user
    if settings.dev_user_id is not None:
        return TelegramAuthUser(
            tg_user_id=settings.dev_user_id,
            first_name="Dev",
            last_name=None,
            username="dev",
            photo_url=None,
        )
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидные данные авторизации Telegram.")


def require_registered_user(
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
):
    """Требует, чтобы пользователь уже прошёл регистрацию (есть запись в users)."""
    user = repo.users.get_user(auth.tg_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не зарегистрирован.")
    return user
