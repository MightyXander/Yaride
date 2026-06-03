"""Пользователи: список с поиском, редактирование профиля, бан/разбан."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from admin.deps import get_notifier, get_repo, get_service, require_admin
from admin.notifications import Notifier
from admin.routes.common import render
from app.repo import Repo
from app.services.admin_service import AdminService

router = APIRouter()

_ROLES = ("driver", "passenger")


@router.get("/users")
async def users_list(
    request: Request,
    q: str = "",
    role: str = "",
    repo: Repo = Depends(get_repo),
):
    require_admin(request)
    rows = repo.users.list_all_users(query=q or None, role=role or None, limit=200)
    return render(request, "users_list.html", active="users", users=rows, roles=_ROLES, f_q=q, f_role=role)


@router.get("/users/{user_id}")
async def user_edit_form(request: Request, user_id: int, repo: Repo = Depends(get_repo)):
    require_admin(request)
    user = repo.users.get_user_by_id(user_id)
    if not user:
        return RedirectResponse(url="/users?error=Пользователь не найден", status_code=303)
    return render(request, "user_edit.html", active="users", user=user, roles=_ROLES)


@router.post("/users/{user_id}")
async def user_update(
    request: Request,
    user_id: int,
    name: str = Form(...),
    role: str = Form(...),
    min_passenger_rating: str = Form(""),
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
        service.update_user(admin, user_id, name=name, role=role, min_passenger_rating=min_rating)
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
