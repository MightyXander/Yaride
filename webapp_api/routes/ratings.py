"""Оценки, полученные пользователем."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.formatting import format_trip_when
from app.repo import Repo
from webapp_api.auth import TelegramAuthUser
from webapp_api.bot_notify import BotNotifier
from webapp_api.deps import get_auth_user, get_notifier, get_repo
from webapp_api.schemas import RateRequest
from webapp_api.serializers import pending_rating_to_dict, rating_to_dict

router = APIRouter(prefix="/api/ratings", tags=["ratings"])


@router.get("/received")
def received(
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    rows = repo.ratings.list_ratings_received(auth.tg_user_id)
    return {"ratings": [rating_to_dict(r) for r in rows]}


@router.get("/pending")
def pending(
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Поездки, которые пользователь может оценить (окно открыто, оценки ещё нет)."""
    prompts = repo.ratings.list_pending_rating_prompts()
    mine = [p for p in prompts if p.rater_tg_user_id == auth.tg_user_id]
    out = []
    for p in mine:
        card = repo.trips.get_trip_public_card(p.trip_id)
        out.append(pending_rating_to_dict(p, trip_row=card))
    return {"pending": out}


@router.post("", status_code=201)
async def submit_rating(
    body: RateRequest,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
    notifier: BotNotifier = Depends(get_notifier),
) -> dict:
    """Выставить оценку участнику поездки (звёзды + опциональный отзыв)."""
    try:
        repo.ratings.submit_rating(
            auth.tg_user_id,
            body.trip_id,
            body.rated_tg_user_id,
            body.stars,
            review_text=body.review_text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rater = repo.users.get_user(auth.tg_user_id)
    trip = repo.trips.get_trip_public_card(body.trip_id)
    when_label = "—"
    if trip:
        when_label = format_trip_when(trip["trip_date"], trip["departure_time"], trip["time_slot"])
    await notifier.rating_received(
        rated_tg_user_id=body.rated_tg_user_id,
        rater_name=str(rater["name"]) if rater else "Пользователь",
        stars=body.stars,
        trip_id=body.trip_id,
        when_label=when_label,
        review_text=body.review_text,
    )
    return {"ok": True}
