"""Избранные маршруты пользователя."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.repo import Repo
from webapp_api.auth import TelegramAuthUser
from webapp_api.deps import get_auth_user, get_repo
from webapp_api.schemas import FavoriteRequest

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


@router.get("")
def list_favorites(
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    rows = repo.favorites.list_favorites(auth.tg_user_id)
    return {
        "favorites": [
            {
                "id": r["id"],
                "startPointId": r["start_point_id"],
                "endPointId": r["end_point_id"],
                "fromTitle": r["start_title"],
                "toTitle": r["end_title"],
            }
            for r in rows
        ]
    }


@router.post("", status_code=201)
def add_favorite(
    body: FavoriteRequest,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Добавить маршрут в избранное — по паре точек или из конкретной поездки."""
    if body.trip_id is not None:
        added = repo.favorites.add_favorite_from_trip(auth.tg_user_id, body.trip_id)
    elif body.start_point_id is not None and body.end_point_id is not None:
        added = repo.favorites.add_favorite_route(auth.tg_user_id, body.start_point_id, body.end_point_id)
    else:
        raise HTTPException(status_code=400, detail="Нужны trip_id или пара start_point_id/end_point_id.")
    return {"added": added}


@router.delete("/{favorite_id}")
def delete_favorite(
    favorite_id: int,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    removed = repo.favorites.delete_favorite(auth.tg_user_id, favorite_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Маршрут не найден.")
    return {"ok": True}
