"""Вход и выход администратора."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from admin.auth import authenticate
from admin.deps import get_repo
from admin.routes.common import render
from app.repo import Repo

router = APIRouter()


@router.get("/login")
async def login_form(request: Request):
    if request.session.get("admin"):
        return RedirectResponse(url="/", status_code=303)
    return render(request, "login.html")


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    repo: Repo = Depends(get_repo),
):
    if not authenticate(repo, username, password):
        return RedirectResponse(url="/login?error=Неверный логин или пароль", status_code=303)
    request.session["admin"] = username.strip()
    return RedirectResponse(url="/", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
