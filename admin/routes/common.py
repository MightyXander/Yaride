"""Помощник рендеринга шаблонов с общим контекстом (текущий админ, активный раздел, флеш-сообщения)."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse

from admin.deps import current_admin


def render(request: Request, template: str, *, active: str = "", **context) -> HTMLResponse:
    templates = request.app.state.templates
    base = {
        "request": request,
        "admin": current_admin(request),
        "active": active,
        "error": request.query_params.get("error"),
        "msg": request.query_params.get("msg"),
    }
    base.update(context)
    # Современная сигнатура Starlette: первым идёт request, затем имя шаблона и контекст.
    return templates.TemplateResponse(request, template, base)
