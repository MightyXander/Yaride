"""Брони: список с фильтрами по статусу и поездке (read-only; отмена идёт через отмену поездки)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from admin.deps import get_repo, require_admin
from admin.routes.common import render
from app.repo import Repo

router = APIRouter()

_STATUSES = ("active", "cancelled_by_passenger", "cancelled_by_driver")


@router.get("/bookings")
async def bookings_list(
    request: Request,
    status: str = "",
    trip_id: str = "",
    repo: Repo = Depends(get_repo),
):
    require_admin(request)
    trip_filter = int(trip_id) if trip_id.strip().isdigit() else None
    rows = repo.bookings.list_all_bookings(status=status or None, trip_id=trip_filter, limit=200)
    return render(
        request,
        "bookings_list.html",
        active="bookings",
        bookings=rows,
        statuses=_STATUSES,
        f_status=status,
        f_trip=trip_id,
    )
