"""Журнал действий администраторов (read-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from admin.deps import get_repo, require_admin
from admin.routes.common import render
from app.repo import Repo

router = APIRouter()


@router.get("/audit")
async def audit_list(request: Request, repo: Repo = Depends(get_repo)):
    require_admin(request)
    rows = repo.admin.list_audit(limit=200)
    return render(request, "audit_list.html", active="audit", entries=rows)
