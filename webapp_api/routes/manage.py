"""Управление поездками водителя: список своих поездок и брони по поездке."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.repo import Repo
from webapp_api.auth import TelegramAuthUser
from webapp_api.bot_notify import BotNotifier
from webapp_api.deps import get_auth_user, get_notifier, get_repo
from webapp_api.schemas import PassengerRatingThresholdRequest
from webapp_api.serializers import driver_trip_to_dict, user_to_dict

router = APIRouter(prefix="/api/manage", tags=["manage"])


@router.get("/trips")
def my_trips(
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    rows = repo.trips.list_driver_trips(auth.tg_user_id)
    return {"trips": [driver_trip_to_dict(r) for r in rows]}


@router.get("/trips/{trip_id}/bookings")
def trip_bookings(
    trip_id: int,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Активные/прошлые брони на поездку водителя (с рейтингом пассажира)."""
    rows = repo.bookings.list_bookings_for_driver_trip(auth.tg_user_id, trip_id)
    out = []
    for r in rows:
        keys = r.keys()
        out.append(
            {
                "bookingId": r["booking_id"] if "booking_id" in keys else r["id"] if "id" in keys else None,
                "status": r["status"] if "status" in keys else None,
                "passengerName": r["passenger_name"]
                if "passenger_name" in keys
                else r["name"]
                if "name" in keys
                else None,
                "passengerRating": round(float(r["rating_avg"]), 2)
                if "rating_avg" in keys and r["rating_avg"] is not None
                else None,
            }
        )
    return {"bookings": out}


@router.post("/bookings/{booking_id}/reject")
async def reject_booking(
    booking_id: int,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
    notifier: BotNotifier = Depends(get_notifier),
) -> dict:
    """Водитель отклоняет бронь пассажира (уведомление пассажиру в бот)."""
    try:
        info = repo.bookings.reject_booking_by_driver(auth.tg_user_id, booking_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await notifier.booking_rejected_by_driver(info)
    return {"ok": True, "passengerTgUserId": info.get("passenger_tg_user_id")}


@router.post("/trips/{trip_id}/cancel")
async def cancel_trip(
    trip_id: int,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
    notifier: BotNotifier = Depends(get_notifier),
) -> dict:
    """Водитель полностью отменяет поездку; все активные брони аннулируются."""
    try:
        affected = repo.trips.cancel_trip_by_driver(auth.tg_user_id, trip_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await notifier.trip_cancelled_by_driver(trip_id, affected)
    return {"ok": True, "affectedPassengers": affected}


@router.put("/passenger-rating-threshold")
def set_passenger_rating_threshold(
    body: PassengerRatingThresholdRequest,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Минимальный средний рейтинг пассажира для авто-отклонения брони; off — без ограничения."""
    allowed = {"3.0", "4.0", "4.5", "off"}
    if body.threshold not in allowed:
        raise HTTPException(status_code=400, detail="Порог должен быть 3.0, 4.0, 4.5 или off.")
    try:
        if body.threshold == "off":
            repo.users.set_driver_min_passenger_rating(auth.tg_user_id, None)
        else:
            repo.users.set_driver_min_passenger_rating(auth.tg_user_id, float(body.threshold))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    user = repo.users.get_user(auth.tg_user_id)
    return {"ok": True, "minPassengerRating": user_to_dict(user)["minPassengerRating"] if user else None}
