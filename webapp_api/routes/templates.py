"""Маршруты-шаблоны водителя: CRUD + быстрая публикация поездки из шаблона."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.repo import Repo
from webapp_api.auth import TelegramAuthUser
from webapp_api.deps import get_auth_user, get_repo
from webapp_api.schemas import CreateTemplateRequest, PublishTemplateRequest

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("")
def list_templates(
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    rows = repo.templates.list_templates(auth.tg_user_id)
    return {
        "templates": [
            {
                "id": r["id"],
                "startPointId": r["start_point_id"],
                "endPointId": r["end_point_id"],
                "fromTitle": r["start_title"],
                "toTitle": r["end_title"],
                "priceRub": r["price_rub"],
                "seatsTotal": r["seats_total"],
                "comment": r["comment"],
            }
            for r in rows
        ]
    }


@router.post("", status_code=201)
def create_template(
    body: CreateTemplateRequest,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    try:
        template_id = repo.templates.create_template(
            auth.tg_user_id,
            start_point_id=body.start_point_id,
            end_point_id=body.end_point_id,
            price_rub=body.price_rub,
            seats_total=body.seats_total,
            comment=body.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": template_id}


@router.delete("/{template_id}")
def delete_template(
    template_id: int,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    if not repo.templates.delete_template(auth.tg_user_id, template_id):
        raise HTTPException(status_code=404, detail="Маршрут не найден.")
    return {"ok": True}


@router.post("/{template_id}/publish", status_code=201)
def publish_template(
    template_id: int,
    body: PublishTemplateRequest,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Опубликовать поездку из шаблона: маршрут/цена/места берутся из шаблона, дата/время — из запроса."""
    tpl = repo.templates.get_template(auth.tg_user_id, template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="Маршрут не найден.")
    try:
        trip_id = repo.trips.create_trip(
            auth.tg_user_id,
            int(tpl["start_point_id"]),
            int(tpl["end_point_id"]),
            body.trip_date,
            body.departure_time,
            int(tpl["price_rub"]),
            int(tpl["seats_total"]),
        )
        if tpl["comment"]:
            repo.trips.set_trip_comment(trip_id, str(tpl["comment"]))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": trip_id}
