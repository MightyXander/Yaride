"""История поездок пользователя (пассажир или водитель)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.repo import Repo
from webapp_api.auth import TelegramAuthUser
from webapp_api.deps import get_auth_user, get_repo
from webapp_api.serializers import history_driver_to_dict, history_passenger_to_dict

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
def trip_history(
    role: str = Query(default="passenger", pattern="^(passenger|driver)$"),
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Архив прошлых/завершённых поездок. role=passenger — брони; role=driver — свои рейсы."""
    if role == "driver":
        rows = repo.trips.list_driver_history(auth.tg_user_id)
        return {"role": "driver", "items": [history_driver_to_dict(r) for r in rows]}
    rows = repo.bookings.list_passenger_history(auth.tg_user_id)
    return {"role": "passenger", "items": [history_passenger_to_dict(r) for r in rows]}
