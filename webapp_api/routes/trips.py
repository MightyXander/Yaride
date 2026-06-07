"""Поиск, детали и создание поездок."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.repo import Repo
from webapp_api.auth import TelegramAuthUser
from webapp_api.config import WebAppSettings
from webapp_api.deps import get_auth_user, get_repo, get_settings
from webapp_api.schemas import CreateTripRequest
from webapp_api.serializers import trip_card_to_dict

router = APIRouter(prefix="/api/trips", tags=["trips"])


@router.get("", dependencies=[Depends(get_auth_user)])
def search_trips(
    start_point: int | None = Query(default=None),
    end_point: int | None = Query(default=None),
    date: str | None = Query(default=None),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Открытые поездки по фильтрам маршрута/даты (точное совпадение точек, статус open)."""
    rows = repo.trips.find_open_trips(start_point_id=start_point, end_point_id=end_point, trip_date=date)
    return {"trips": [trip_card_to_dict(r) for r in rows]}


@router.get("/{trip_id}", dependencies=[Depends(get_auth_user)])
def trip_details(trip_id: int, repo: Repo = Depends(get_repo)) -> dict:
    """Карточка поездки + комментарий и авто водителя (поля под Mini App)."""
    card = repo.trips.get_trip_public_card(trip_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Поездка не найдена.")
    data = trip_card_to_dict(card)

    full = repo.trips.get_trip_admin(trip_id)
    if full is not None and "comment" in full.keys():
        data["comment"] = full["comment"]

    driver = repo.users.get_user_by_id(int(card["driver_id"]))
    if driver is not None:
        keys = driver.keys()
        data["carModel"] = driver["car_model"] if "car_model" in keys else None
        data["carColor"] = driver["car_color"] if "car_color" in keys else None
        data["carPlate"] = driver["car_plate"] if "car_plate" in keys else None
        data["driverTripsCount"] = int(driver["trips_driver_count"]) if "trips_driver_count" in keys else None
    return data


@router.post("", status_code=201)
def create_trip(
    body: CreateTripRequest,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Создание поездки водителем (проверки роли/ВУ/времени — на стороне repo)."""
    try:
        trip_id = repo.trips.create_trip(
            auth.tg_user_id,
            body.start_point_id,
            body.end_point_id,
            body.trip_date,
            body.departure_time,
            body.price_rub,
            body.seats_total,
        )
        if body.comment:
            repo.trips.set_trip_comment(trip_id, body.comment)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": trip_id}


@router.get("/nearby/by-geo", dependencies=[Depends(get_auth_user)])
def nearest_stops(
    lat: float = Query(...),
    lng: float = Query(...),
    repo: Repo = Depends(get_repo),
    settings: WebAppSettings = Depends(get_settings),
) -> dict:
    """Ближайшие остановки посадки по координатам (для гео-подбора, расстояние по прямой)."""
    _ = settings
    rows = repo.routes.nearest_stops_global(lat, lng, limit=5, max_km=85.0)
    out = []
    for r in rows:
        keys = r.keys()
        out.append(
            {
                "id": r["id"] if "id" in keys else r["point_id"] if "point_id" in keys else None,
                "title": r["title"] if "title" in keys else None,
                "district": r["district"] if "district" in keys else None,
                "distanceKm": round(float(r["distance_km"]), 1) if "distance_km" in keys else None,
            }
        )
    return {"stops": out}
