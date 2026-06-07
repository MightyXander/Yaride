"""Оценки, полученные пользователем."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.repo import Repo
from webapp_api.auth import TelegramAuthUser
from webapp_api.deps import get_auth_user, get_repo
from webapp_api.schemas import RateRequest
from webapp_api.serializers import rating_to_dict

router = APIRouter(prefix="/api/ratings", tags=["ratings"])


@router.get("/received")
def received(
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    rows = repo.ratings.list_ratings_received(auth.tg_user_id)
    return {"ratings": [rating_to_dict(r) for r in rows]}


@router.post("", status_code=201)
def submit_rating(
    body: RateRequest,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
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
    return {"ok": True}
