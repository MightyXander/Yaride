"""Точки маршрута: список, создание, редактирование, удаление (с защитой по ссылкам из поездок)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from admin.deps import get_repo, get_service, require_admin
from admin.routes.common import render
from app.repo import Repo
from app.services.admin_service import AdminService

router = APIRouter()


def _parse_coord(raw: str) -> float | None:
    raw = raw.strip()
    if not raw:
        return None
    return float(raw)


@router.get("/points")
async def points_list(request: Request, repo: Repo = Depends(get_repo)):
    require_admin(request)
    rows = repo.routes.route_points()
    return render(request, "points_list.html", active="points", points=rows)


@router.get("/points/new")
async def point_new_form(request: Request):
    require_admin(request)
    return render(request, "point_edit.html", active="points", point=None)


@router.get("/points/{point_id}")
async def point_edit_form(request: Request, point_id: int, repo: Repo = Depends(get_repo)):
    require_admin(request)
    point = repo.routes.get_point(point_id)
    if not point:
        return RedirectResponse(url="/points?error=Точка не найдена", status_code=303)
    return render(request, "point_edit.html", active="points", point=point)


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
