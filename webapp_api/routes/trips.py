"""Поиск, детали и создание поездок."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.cache import TRIPS_SEARCH_TTL_S, cache_get, cache_set, invalidate_trip_search_cache
from app.repo import Repo
from webapp_api.auth import TelegramAuthUser
from webapp_api.bot_notify import BotNotifier
from webapp_api.config import WebAppSettings
from webapp_api.deps import get_auth_user, get_notifier, get_repo, get_settings
from webapp_api.schemas import CreateTripRequest
from webapp_api.serializers import trip_card_to_dict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trips", tags=["trips"])


@router.get("", dependencies=[Depends(get_auth_user)])
def search_trips(
    start_point: int | None = Query(default=None),
    end_point: int | None = Query(default=None),
    start_district: str | None = Query(default=None),
    end_district: str | None = Query(default=None),
    date: str | None = Query(default=None),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Открытые поездки: точное совпадение остановок или поиск по парам районов."""
    by_district = bool(start_district and end_district)
    cache_key = (
        f"trips:search:district:{start_district}:{end_district}:{date or ''}"
        if by_district
        else f"trips:search:exact:{start_point}:{end_point}:{date or ''}"
    )
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    if by_district:
        rows = repo.trips.find_open_trips(
            start_district=start_district,
            end_district=end_district,
            trip_date=date,
        )
        out = {
            "trips": [trip_card_to_dict(r) for r in rows],
            "searchScope": "district",
        }
        cache_set(cache_key, out, ttl_s=TRIPS_SEARCH_TTL_S)
        return out

    rows = repo.trips.find_open_trips(start_point_id=start_point, end_point_id=end_point, trip_date=date)
    out: dict = {
        "trips": [trip_card_to_dict(r) for r in rows],
        "searchScope": "exact",
    }
    if not rows and start_point and end_point:
        sp = repo.routes.get_point(start_point)
        ep = repo.routes.get_point(end_point)
        sd = str(sp["district"] or "").strip() if sp is not None else ""
        ed = str(ep["district"] or "").strip() if ep is not None else ""
        if sd and ed:
            out["districtFallback"] = {"startDistrict": sd, "endDistrict": ed}
    cache_set(cache_key, out, ttl_s=TRIPS_SEARCH_TTL_S)
    return out


@router.get("/nearby/by-geo", dependencies=[Depends(get_auth_user)])
def nearest_stops(
    lat: float = Query(...),
    lng: float = Query(...),
    repo: Repo = Depends(get_repo),
    settings: WebAppSettings = Depends(get_settings),
) -> dict:
    """Ближайшие остановки посадки по координатам (для гео-подбора, расстояние по прямой)."""
    _ = settings
    ranked = repo.routes.nearest_stops_global(lat, lng, limit=5, max_km=85.0)
    out = []
    for row, distance_km in ranked:
        keys = row.keys()
        out.append(
            {
                "id": int(row["id"]),
                "title": row["title"] if "title" in keys else None,
                "district": row["district"] if "district" in keys else None,
                "adminArea": row["admin_area"] if "admin_area" in keys else None,
                "distanceKm": round(float(distance_km), 1),
            }
        )
    return {"stops": out}


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
        data["driverUsername"] = driver["username"] if "username" in keys and driver["username"] else None
        data["driverRatingCount"] = int(driver["rating_count"]) if "rating_count" in keys else None
        data["driverCreatedAt"] = driver["created_at"] if "created_at" in keys else None
    return data


@router.post("", status_code=201)
async def create_trip(
    body: CreateTripRequest,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
    notifier: BotNotifier = Depends(get_notifier),
    settings: WebAppSettings = Depends(get_settings),
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
    _enrich_with_intermediate_stops(repo, trip_id, body.start_point_id, body.end_point_id)
    invalidate_trip_search_cache()

    # Матчинг подписок на маршрут: уведомляем пассажиров о новой поездке
    await _notify_route_alerts(
        repo, notifier, settings, trip_id, body.start_point_id, body.end_point_id, body.trip_date, body.departure_time
    )

    return {"id": trip_id}


def _enrich_with_intermediate_stops(
    repo: Repo,
    trip_id: int,
    start_point_id: int,
    end_point_id: int,
) -> None:
    """Запрашивает маршрут у Яндекса и сохраняет промежуточные остановки. Soft fail."""
    from app.route_compute import (
        compute_intermediate_stops,
        fetch_route_polyline,
        polyline_to_json,
    )

    try:
        sp = repo.routes.get_point(start_point_id)
        ep = repo.routes.get_point(end_point_id)
        if sp is None or ep is None or sp["latitude"] is None or ep["latitude"] is None:
            repo.trips.disable_intermediate_pickup(trip_id)
            return

        polyline = fetch_route_polyline(
            float(sp["latitude"]), float(sp["longitude"]),
            float(ep["latitude"]), float(ep["longitude"]),
        )
        if polyline is None:
            repo.trips.disable_intermediate_pickup(trip_id)
            return

        locality = str(sp["locality"])
        all_stops = repo.routes.list_all_stops_with_coords(locality)
        intermediate = compute_intermediate_stops(polyline, all_stops, start_point_id, end_point_id)
        repo.trips.save_route_compute(trip_id, polyline_to_json(polyline), intermediate)
    except Exception:
        logger.warning("route_compute failed for trip %s", trip_id, exc_info=True)
        try:
            repo.trips.disable_intermediate_pickup(trip_id)
        except Exception:
            pass


async def _notify_route_alerts(
    repo: Repo,
    notifier: BotNotifier,
    settings: WebAppSettings,
    trip_id: int,
    start_point_id: int,
    end_point_id: int,
    trip_date: str,
    departure_time: str,
) -> None:
    """Матчинг подписок на маршрут: уведомляем пассажиров о новой поездке. Soft fail."""
    try:
        matching_alerts = repo.alerts.find_matching_alerts(start_point_id, end_point_id, trip_date)
        miniapp_url = getattr(settings, "miniapp_url", None)
        for alert in matching_alerts:
            try:
                await notifier.route_alert_matched(
                    passenger_tg_user_id=int(alert["passenger_tg_user_id"]),
                    trip_id=trip_id,
                    from_title=str(alert["from_title"]),
                    to_title=str(alert["to_title"]),
                    trip_date=trip_date,
                    departure_time=departure_time,
                    miniapp_url=miniapp_url,
                )
                repo.alerts.mark_as_notified(int(alert["id"]))
            except Exception:
                logger.warning("Failed to notify alert %s", alert["id"], exc_info=True)
    except Exception:
        logger.warning("route_alerts matching failed for trip %s", trip_id, exc_info=True)

