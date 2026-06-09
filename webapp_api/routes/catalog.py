"""Справочник маршрутов: районы Ярославля и остановки внутри района."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.repo import Repo
from webapp_api.deps import get_auth_user, get_repo

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

LOCALITY = "Ярославль"


@router.get("/districts", dependencies=[Depends(get_auth_user)])
def list_districts(repo: Repo = Depends(get_repo)) -> dict:
    """Районы Ярославля в порядке справочника (ROUTE_HIERARCHY)."""
    return {"locality": LOCALITY, "districts": repo.routes.list_districts(LOCALITY)}


@router.get("/stops", dependencies=[Depends(get_auth_user)])
def list_stops(
    district: str = Query(..., min_length=1),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Все остановки района (с указанием подрайона)."""
    admin_areas = repo.routes.list_admin_areas(LOCALITY, district)
    stops: list[dict] = []
    for aa in admin_areas:
        for s in repo.routes.list_stops(LOCALITY, district, aa):
            stops.append({"id": s["id"], "title": s["title"], "adminArea": aa})
    return {"locality": LOCALITY, "district": district, "stops": stops}


@router.get("/stops/all", dependencies=[Depends(get_auth_user)])
def list_all_stops(repo: Repo = Depends(get_repo)) -> dict:
    """Все остановки города с координатами — для выбора точки на карте."""
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
    return {"locality": LOCALITY, "stops": stops}
