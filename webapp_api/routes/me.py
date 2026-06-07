"""Профиль и регистрация пользователя Mini App."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.repo import Repo
from webapp_api.auth import TelegramAuthUser
from webapp_api.deps import get_auth_user, get_repo
from webapp_api.schemas import RegisterRequest
from webapp_api.serializers import user_to_dict

router = APIRouter(prefix="/api", tags=["me"])


@router.get("/me")
def get_me(
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Текущий пользователь: признак регистрации + профиль + базовые данные из Telegram."""
    user = repo.users.get_user(auth.tg_user_id)
    return {
        "registered": user is not None,
        "user": user_to_dict(user) if user is not None else None,
        "telegram": {
            "id": auth.tg_user_id,
            "name": auth.display_name,
            "username": auth.username,
            "photoUrl": auth.photo_url,
        },
    }


@router.post("/register")
def register(
    body: RegisterRequest,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Регистрация/обновление профиля. Для водителя обязательны данные ВУ."""
    if body.role not in ("driver", "passenger"):
        raise HTTPException(status_code=400, detail="Роль должна быть 'driver' или 'passenger'.")
    try:
        repo.users.upsert_user(
            auth.tg_user_id,
            body.name.strip(),
            auth.username,
            body.role,
            dl_series_number=body.dl_series_number,
            dl_valid_until=body.dl_valid_until,
        )
        if body.role == "driver":
            repo.users.update_car(
                auth.tg_user_id,
                car_model=body.car_model,
                car_color=body.car_color,
                car_plate=body.car_plate,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = repo.users.get_user(auth.tg_user_id)
    return {"registered": True, "user": user_to_dict(user) if user else None}
