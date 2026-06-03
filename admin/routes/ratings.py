"""Оценки: список для модерации, правка/скрытие текста отзыва, удаление оценки."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from admin.deps import get_repo, get_service, require_admin
from admin.routes.common import render
from app.repo import Repo
from app.services.admin_service import AdminService

router = APIRouter()


@router.get("/ratings")
async def ratings_list(
    request: Request,
    only_review: str = "",
    repo: Repo = Depends(get_repo),
):
    require_admin(request)
    rows = repo.ratings.list_all_ratings(only_with_review=bool(only_review), limit=200)
    return render(request, "ratings_list.html", active="ratings", ratings=rows, f_only_review=only_review)


@router.post("/ratings/{rating_id}/review")
async def rating_moderate(
    request: Request,
    rating_id: int,
    review_text: str = Form(""),
    action: str = Form("save"),
    service: AdminService = Depends(get_service),
):
    admin = require_admin(request)
    text = None if action == "clear" else (review_text.strip() or None)
    try:
        service.moderate_review(admin, rating_id, text)
    except ValueError as exc:
        return RedirectResponse(url=f"/ratings?error={exc}", status_code=303)
    return RedirectResponse(url="/ratings?msg=Отзыв обновлён", status_code=303)


@router.post("/ratings/{rating_id}/delete")
async def rating_delete(
    request: Request,
    rating_id: int,
    service: AdminService = Depends(get_service),
):
    admin = require_admin(request)
    try:
        service.delete_rating(admin, rating_id)
    except ValueError as exc:
        return RedirectResponse(url=f"/ratings?error={exc}", status_code=303)
    return RedirectResponse(url="/ratings?msg=Оценка удалена", status_code=303)
