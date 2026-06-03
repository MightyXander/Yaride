"""Общие зависимости запросов: доступ к repo/service/notifier из app.state и проверка авторизации."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import RedirectResponse

from admin.notifications import Notifier
from app.repo import Repo
from app.services.admin_service import AdminService


def get_repo(request: Request) -> Repo:
    return request.app.state.repo


def get_service(request: Request) -> AdminService:
    return request.app.state.service


def get_notifier(request: Request) -> Notifier:
    return request.app.state.notifier


def current_admin(request: Request) -> str | None:
    """Логин текущего администратора из сессии (или None)."""
    return request.session.get("admin")


class RequireLogin(Exception):
    """Сигнал middleware/обработчику, что нужен редирект на страницу входа."""


def require_admin(request: Request) -> str:
    admin = current_admin(request)
    if not admin:
        raise RequireLogin()
    return admin


def redirect_to_login() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=303)
