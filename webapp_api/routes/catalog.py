"""Справочник маршрутов: районы Ярославля и остановки внутри района."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.cache import CATALOG_TTL_S, cache_get, cache_set
from app.repo import Repo
from webapp_api.deps import get_auth_user, get_repo

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

LOCALITY = "Ярославль"


@router.get("/districts", dependencies=[Depends(get_auth_user)])
def list_districts(repo: Repo = Depends(get_repo)) -> dict:
    """Районы Ярославля в порядке справочника (ROUTE_HIERARCHY)."""
    cache_key = f"catalog:districts:{LOCALITY}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    payload = {"locality": LOCALITY, "districts": repo.routes.list_districts(LOCALITY)}
    cache_set(cache_key, payload, ttl_s=CATALOG_TTL_S)
    return payload


@router.get("/stops", dependencies=[Depends(get_auth_user)])
def list_stops(
    district: str = Query(..., min_length=1),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Все остановки района (с указанием подрайона)."""
    cache_key = f"catalog:stops:{LOCALITY}:{district}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    admin_areas = repo.routes.list_admin_areas(LOCALITY, district)
    stops: list[dict] = []
    for aa in admin_areas:
        for s in repo.routes.list_stops(LOCALITY, district, aa):
            stops.append({"id": s["id"], "title": s["title"], "adminArea": aa})
    payload = {"locality": LOCALITY, "district": district, "stops": stops}
    cache_set(cache_key, payload, ttl_s=CATALOG_TTL_S)
    return payload


@router.get("/stops/all", dependencies=[Depends(get_auth_user)])
def list_all_stops(repo: Repo = Depends(get_repo)) -> dict:
    """Все остановки города с координатами — для выбора точки на карте."""
    cache_key = f"catalog:stops:all:{LOCALITY}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    stops: list[dict] = []
    for s in repo.routes.list_all_stops_with_coords(LOCALITY):
        stops.append(
            {
                "id": int(s["id"]),
                "title": s["title"],
                "district": s["district"] or None,
                "adminArea": s["admin_area"] or None,
                "lat": float(s["latitude"]),
                "lng": float(s["longitude"]),
            }
        )
    payload = {"locality": LOCALITY, "stops": stops}
    cache_set(cache_key, payload, ttl_s=CATALOG_TTL_S)
    return payload
