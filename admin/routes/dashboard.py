"""Дашборд: сводные счётчики по пользователям, поездкам и броням."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from admin.deps import get_repo, require_admin
from admin.routes.common import render
from app.repo import Repo

router = APIRouter()


@router.get("/")
async def dashboard(request: Request, repo: Repo = Depends(get_repo)):
    require_admin(request)
    by_status = repo.trips.count_trips_by_status()
    stats = {
        "users": repo.users.count_users(),
        "drivers_pending": repo.users.count_pending_drivers(),
        "trips_open": by_status.get("open", 0),
        "trips_cancelled": by_status.get("cancelled", 0),
        "trips_completed": by_status.get("completed", 0),
        "bookings_active": repo.bookings.count_active_bookings(),
    }
    return render(request, "dashboard.html", active="dashboard", stats=stats)
