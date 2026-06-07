"""Брони пассажира: список, создание, отмена."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.repo import Repo
from webapp_api.auth import TelegramAuthUser
from webapp_api.deps import get_auth_user, get_repo
from webapp_api.schemas import BookRequest, CancelBookingRequest
from webapp_api.serializers import booking_to_dict

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.get("")
def my_bookings(
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    rows = repo.bookings.list_passenger_bookings(auth.tg_user_id)
    return {"bookings": [booking_to_dict(r) for r in rows]}


@router.post("", status_code=201)
def create_booking(
    body: BookRequest,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Бронирование места (проверки прав/мест/рейтинга — на стороне repo)."""
    try:
        booking_id = repo.bookings.create_booking(auth.tg_user_id, body.trip_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": booking_id}


@router.post("/{booking_id}/cancel")
def cancel_booking(
    booking_id: int,
    body: CancelBookingRequest,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Отмена брони пассажиром с причиной (уходит водителю через бота отдельно)."""
    try:
        repo.bookings.cancel_booking_by_passenger(auth.tg_user_id, booking_id, body.reason.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}
