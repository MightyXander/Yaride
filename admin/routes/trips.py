"""Поездки: список с фильтрами, редактирование, принудительная отмена."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from admin.deps import get_notifier, get_repo, get_service, require_admin
from admin.notifications import Notifier
from admin.routes.common import render
from app.repo import Repo
from app.services.admin_service import AdminService

router = APIRouter()

_STATUSES = ("open", "cancelled", "completed")


@router.get("/trips")
async def trips_list(
    request: Request,
    status: str = "",
    trip_date: str = "",
    repo: Repo = Depends(get_repo),
):
    require_admin(request)
    rows = repo.trips.list_all_trips(
        status=status or None,
        trip_date=trip_date or None,
        limit=200,
    )
    return render(
        request,
        "trips_list.html",
        active="trips",
        trips=rows,
        statuses=_STATUSES,
        f_status=status,
        f_date=trip_date,
    )


@router.get("/trips/{trip_id}")
async def trip_edit_form(request: Request, trip_id: int, repo: Repo = Depends(get_repo)):
    require_admin(request)
    trip = repo.trips.get_trip_admin(trip_id)
    if not trip:
        return RedirectResponse(url="/trips?error=Поездка не найдена", status_code=303)
    bookings = repo.bookings.list_all_bookings(trip_id=trip_id, limit=200)
    return render(request, "trip_edit.html", active="trips", trip=trip, bookings=bookings, statuses=_STATUSES)


@router.post("/trips/{trip_id}")
async def trip_update(
    request: Request,
    trip_id: int,
    price_rub: int = Form(...),
    seats_total: int = Form(...),
    trip_date: str = Form(...),
    departure_time: str = Form(...),
    status: str = Form(...),
    service: AdminService = Depends(get_service),
):
    admin = require_admin(request)
    try:
        service.update_trip(
            admin,
            trip_id,
            price_rub=price_rub,
            seats_total=seats_total,
            trip_date=trip_date.strip(),
            departure_time=departure_time.strip(),
            status=status,
        )
    except ValueError as exc:
        return RedirectResponse(url=f"/trips/{trip_id}?error={exc}", status_code=303)
    return RedirectResponse(url=f"/trips/{trip_id}?msg=Сохранено", status_code=303)


@router.post("/trips/{trip_id}/cancel")
async def trip_cancel(
    request: Request,
    trip_id: int,
    service: AdminService = Depends(get_service),
    notifier: Notifier = Depends(get_notifier),
):
    admin = require_admin(request)
    try:
        notifications = service.cancel_trip(admin, trip_id)
    except ValueError as exc:
        return RedirectResponse(url=f"/trips/{trip_id}?error={exc}", status_code=303)
    await notifier.send(notifications)
    return RedirectResponse(url=f"/trips/{trip_id}?msg=Поездка отменена", status_code=303)
