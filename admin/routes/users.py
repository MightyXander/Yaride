"""Пользователи: список с поиском, редактирование профиля, бан/разбан, модерация водителей."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from admin.deps import get_notifier, get_repo, get_service, require_admin
from admin.notifications import Notifier
from admin.routes.common import render
from app.driver_access import DRIVER_MOD_PENDING, moderation_status_label
from app.repo import Repo
from app.services.admin_service import AdminService

router = APIRouter()

_ROLES = ("driver", "passenger")
_MODERATION_STATUSES = ("pending", "approved", "rejected")


@router.get("/users")
async def users_list(
    request: Request,
    q: str = "",
    role: str = "",
    moderation: str = "",
    repo: Repo = Depends(get_repo),
):
    require_admin(request)
    rows = repo.users.list_all_users(
        query=q or None,
        role=role or None,
        driver_moderation_status=moderation or None,
        limit=200,
    )
    return render(
        request,
        "users_list.html",
        active="users",
        users=rows,
        roles=_ROLES,
        moderation_statuses=_MODERATION_STATUSES,
        moderation_label=moderation_status_label,
        f_q=q,
        f_role=role,
        f_moderation=moderation,
        pending_count=repo.users.count_pending_drivers(),
    )


@router.get("/drivers/pending")
async def drivers_pending(request: Request, repo: Repo = Depends(get_repo)):
    require_admin(request)
    rows = repo.users.list_all_users(driver_moderation_status=DRIVER_MOD_PENDING, limit=200)
    return render(
        request,
        "drivers_pending.html",
        active="drivers",
        users=rows,
        pending_count=len(rows),
    )


@router.get("/users/{user_id}")
async def user_edit_form(request: Request, user_id: int, repo: Repo = Depends(get_repo)):
    require_admin(request)
    user = repo.users.get_user_by_id(user_id)
    if not user:
        return RedirectResponse(url="/users?error=Пользователь не найден", status_code=303)
    return render(
        request,
        "user_edit.html",
        active="users",
        user=user,
        roles=_ROLES,
        moderation_label=moderation_status_label,
    )


@router.post("/users/{user_id}")
async def user_update(
    request: Request,
    user_id: int,
    name: str = Form(...),
    role: str = Form(...),
    min_passenger_rating: str = Form(""),
    dl_series_number: str = Form(""),
    dl_valid_until: str = Form(""),
    car_model: str = Form(""),
    car_color: str = Form(""),
    car_plate: str = Form(""),
    service: AdminService = Depends(get_service),
):
    admin = require_admin(request)
    min_rating = None
    if min_passenger_rating.strip():
        try:
            min_rating = float(min_passenger_rating.strip())
        except ValueError:
            return RedirectResponse(url=f"/users/{user_id}?error=Порог рейтинга должен быть числом", status_code=303)
    try:
        service.update_user(
            admin,
            user_id,
            name=name,
            role=role,
            min_passenger_rating=min_rating,
            dl_series_number=dl_series_number.strip() or None,
            dl_valid_until=dl_valid_until.strip() or None,
            car_model=car_model.strip() or None,
            car_color=car_color.strip() or None,
            car_plate=car_plate.strip() or None,
        )
    except ValueError as exc:
        return RedirectResponse(url=f"/users/{user_id}?error={exc}", status_code=303)
    return RedirectResponse(url=f"/users/{user_id}?msg=Сохранено", status_code=303)


@router.post("/users/{user_id}/ban")
async def user_ban(
    request: Request,
    user_id: int,
    banned: str = Form(...),
    service: AdminService = Depends(get_service),
    notifier: Notifier = Depends(get_notifier),
):
    admin = require_admin(request)
    do_ban = banned == "1"
    try:
        notifications = service.set_user_ban(admin, user_id, do_ban)
    except ValueError as exc:
        return RedirectResponse(url=f"/users/{user_id}?error={exc}", status_code=303)
    await notifier.send(notifications)
    return RedirectResponse(url=f"/users/{user_id}?msg=Готово", status_code=303)


@router.post("/users/{user_id}/approve-driver")
async def user_approve_driver(
    request: Request,
    user_id: int,
    service: AdminService = Depends(get_service),
    notifier: Notifier = Depends(get_notifier),
):
    admin = require_admin(request)
    try:
        notifications = service.approve_driver(admin, user_id)
    except ValueError as exc:
        return RedirectResponse(url=f"/users/{user_id}?error={exc}", status_code=303)
    await notifier.send(notifications)
    return RedirectResponse(url=f"/users/{user_id}?msg=Водитель одобрен", status_code=303)


@router.post("/users/{user_id}/reject-driver")
async def user_reject_driver(
    request: Request,
    user_id: int,
    service: AdminService = Depends(get_service),
    notifier: Notifier = Depends(get_notifier),
):
    admin = require_admin(request)
    try:
        notifications = service.reject_driver(admin, user_id)
    except ValueError as exc:
        return RedirectResponse(url=f"/users/{user_id}?error={exc}", status_code=303)
    await notifier.send(notifications)
    return RedirectResponse(url=f"/users/{user_id}?msg=Заявка отклонена", status_code=303)
