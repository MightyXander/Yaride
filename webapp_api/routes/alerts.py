"""Подписки на маршрут: уведомления при появлении поездки после пустого поиска."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.repo import Repo
from webapp_api.auth import TelegramAuthUser
from webapp_api.deps import get_auth_user, get_repo

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class CreateAlertRequest(BaseModel):
    from_point_id: int
    to_point_id: int
    desired_date: str
    desired_time: str | None = None


@router.post("", status_code=201)
def create_alert(
    body: CreateAlertRequest,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Создать подписку на маршрут (CTA при пустом поиске)."""
    try:
        alert_id = repo.alerts.create_alert(
            auth.tg_user_id,
            body.from_point_id,
            body.to_point_id,
            body.desired_date,
            body.desired_time,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"id": alert_id}


@router.get("")
def my_alerts(
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Список активных подписок пассажира."""
    rows = repo.alerts.list_passenger_alerts(auth.tg_user_id, status="active")
    alerts = [
        {
            "id": int(r["id"]),
            "fromTitle": str(r["from_title"]),
            "toTitle": str(r["to_title"]),
            "desiredDate": str(r["desired_date"]),
            "desiredTime": r["desired_time"],
            "status": str(r["status"]),
            "createdAt": str(r["created_at"]),
        }
        for r in rows
    ]
    return {"alerts": alerts}
