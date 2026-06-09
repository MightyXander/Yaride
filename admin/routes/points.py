"""Точки маршрута: список, создание, редактирование, удаление (с защитой по ссылкам из поездок)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from admin.deps import get_repo, get_service, require_admin
from admin.geo_map import map_center_for_point, stops_for_admin_map
from admin.routes.common import render
from app.repo import Repo
from app.services.admin_service import AdminService

router = APIRouter()


def _parse_coord(raw: str) -> float | None:
    raw = raw.strip()
    if not raw:
        return None
    return float(raw)


class PointCoordinatesBody(BaseModel):
    latitude: float = Field(..., ge=57.0, le=58.5)
    longitude: float = Field(..., ge=38.5, le=41.0)


@router.get("/points")
async def points_list(request: Request, q: str = "", repo: Repo = Depends(get_repo)):
    require_admin(request)
    rows = repo.routes.list_points_admin(query=q or None)
    return render(request, "points_list.html", active="points", points=rows, f_q=q)


@router.get("/points/map")
async def points_map(request: Request, q: str = "", focus: int | None = None, repo: Repo = Depends(get_repo)):
    require_admin(request)
    rows = repo.routes.list_points_admin(query=q or None, limit=2000)
    stops = stops_for_admin_map(rows)
    return render(
        request,
        "points_map.html",
        active="points",
        stops_json=json.dumps(stops, ensure_ascii=False),
        f_q=q,
        focus_id=focus,
    )


@router.get("/points/new")
async def point_new_form(request: Request):
    require_admin(request)
    lat, lng, saved = map_center_for_point(latitude=None, longitude=None)
    return render(
        request,
        "point_edit.html",
        active="points",
        point=None,
        map_lat=lat,
        map_lng=lng,
        map_saved=saved,
    )


@router.get("/points/{point_id}")
async def point_edit_form(request: Request, point_id: int, repo: Repo = Depends(get_repo)):
    require_admin(request)
    point = repo.routes.get_point(point_id)
    if not point:
        return RedirectResponse(url="/points?error=Точка не найдена", status_code=303)
    lat, lng, saved = map_center_for_point(
        latitude=point["latitude"],
        longitude=point["longitude"],
        locality=point["locality"],
        district=point["district"] or "",
        admin_area=point["admin_area"] or "",
        title=point["title"],
    )
    return render(
        request,
        "point_edit.html",
        active="points",
        point=point,
        map_lat=lat,
        map_lng=lng,
        map_saved=saved,
    )


@router.post("/points/new")
async def point_create(
    request: Request,
    locality: str = Form(...),
    district: str = Form(""),
    admin_area: str = Form(""),
    title: str = Form(...),
    latitude: str = Form(""),
    longitude: str = Form(""),
    service: AdminService = Depends(get_service),
):
    admin = require_admin(request)
    try:
        point_id = service.create_point(
            admin,
            locality=locality,
            district=district,
            admin_area=admin_area,
            title=title,
            latitude=_parse_coord(latitude),
            longitude=_parse_coord(longitude),
        )
    except ValueError as exc:
        return RedirectResponse(url=f"/points/new?error={exc}", status_code=303)
    return RedirectResponse(url=f"/points/{point_id}?msg=Точка создана", status_code=303)


@router.post("/points/{point_id}")
async def point_update(
    request: Request,
    point_id: int,
    locality: str = Form(...),
    district: str = Form(""),
    admin_area: str = Form(""),
    title: str = Form(...),
    latitude: str = Form(""),
    longitude: str = Form(""),
    service: AdminService = Depends(get_service),
):
    admin = require_admin(request)
    try:
        service.update_point(
            admin,
            point_id,
            locality=locality,
            district=district,
            admin_area=admin_area,
            title=title,
            latitude=_parse_coord(latitude),
            longitude=_parse_coord(longitude),
        )
    except ValueError as exc:
        return RedirectResponse(url=f"/points/{point_id}?error={exc}", status_code=303)
    return RedirectResponse(url=f"/points/{point_id}?msg=Сохранено", status_code=303)


@router.patch("/points/{point_id}/coordinates")
async def point_patch_coordinates(
    request: Request,
    point_id: int,
    body: PointCoordinatesBody,
    service: AdminService = Depends(get_service),
):
    admin = require_admin(request)
    try:
        service.patch_point_coordinates(
            admin,
            point_id,
            latitude=body.latitude,
            longitude=body.longitude,
        )
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return JSONResponse(
        {
            "ok": True,
            "latitude": round(body.latitude, 6),
            "longitude": round(body.longitude, 6),
        }
    )


@router.post("/points/{point_id}/delete")
async def point_delete(
    request: Request,
    point_id: int,
    service: AdminService = Depends(get_service),
):
    admin = require_admin(request)
    try:
        service.delete_point(admin, point_id)
    except ValueError as exc:
        return RedirectResponse(url=f"/points/{point_id}?error={exc}", status_code=303)
    return RedirectResponse(url="/points?msg=Точка удалена", status_code=303)
