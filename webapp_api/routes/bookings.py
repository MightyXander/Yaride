"""Брони пассажира: список, создание, отмена."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.repo import Repo
from webapp_api.auth import TelegramAuthUser
from webapp_api.bot_notify import BotNotifier
from webapp_api.deps import get_auth_user, get_notifier, get_repo
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
async def create_booking(
    body: BookRequest,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
    notifier: BotNotifier = Depends(get_notifier),
) -> dict:
    """Бронирование места (проверки прав/мест/рейтинга — на стороне repo)."""
    try:
        booking_id = repo.bookings.create_booking(auth.tg_user_id, body.trip_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    trip = repo.trips.get_trip_public_card(body.trip_id)
    if trip:
        driver = repo.users.get_user_by_id(int(trip["driver_id"]))
        if driver is not None:
            driver_tg = int(driver["tg_user_id"])
            await notifier.booking_created(
                driver_tg_user_id=driver_tg,
                passenger_tg_user_id=auth.tg_user_id,
                booking_id=booking_id,
                trip_id=body.trip_id,
                start_title=str(trip["start_title"]),
                end_title=str(trip["end_title"]),
                trip_date=trip["trip_date"],
                departure_time=trip["departure_time"],
                time_slot=trip["time_slot"] if "time_slot" in trip.keys() else None,
            )

    return {"id": booking_id}


@router.post("/{booking_id}/cancel")
async def cancel_booking(
    booking_id: int,
    body: CancelBookingRequest,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
    notifier: BotNotifier = Depends(get_notifier),
) -> dict:
    """Отмена брони пассажиром с причиной (уведомление водителю в бот)."""
    try:
        _trip_id, payload = repo.bookings.cancel_booking_by_passenger(
            auth.tg_user_id,
            booking_id,
            body.reason.strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await notifier.booking_cancelled_by_passenger(payload)
    return {"ok": True}
