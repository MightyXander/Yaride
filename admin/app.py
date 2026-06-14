"""Фабрика FastAPI-приложения админки: жизненный цикл зависимостей, сессии, маршруты."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from admin.config import AdminSettings, load_admin_settings
from admin.deps import RequireLogin, redirect_to_login
from admin.notifications import Notifier
from admin.routes import audit, auth_routes, bookings, dashboard, points, ratings, trips, users
from app.database import open_database
from app.repo import Repo
from app.services.admin_service import AdminService

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(_BASE_DIR / "templates"))


def create_app(settings: AdminSettings | None = None) -> FastAPI:
    settings = settings or load_admin_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = open_database(database_url=settings.database_url, db_path=settings.db_path)
        db.init_schema()
        repo = Repo(db)
        app.state.settings = settings
        app.state.db = db
        app.state.repo = repo
        app.state.service = AdminService(repo)
        app.state.notifier = Notifier(settings.bot_token if settings.notify_enabled else None)
        app.state.templates = TEMPLATES
        try:
            yield
        finally:
            await app.state.notifier.close()
            db.close()

    app = FastAPI(title="Yaride Admin", lifespan=lifespan)
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, same_site="lax")
    app.mount("/static", StaticFiles(directory=str(_BASE_DIR / "static")), name="static")

    @app.get("/health")
    async def health(request: Request) -> dict[str, str]:
        db = request.app.state.db
        backend = "postgresql" if db.__class__.__name__ == "PostgresDatabase" else "sqlite"
        return {"status": "ok", "database": backend}

    @app.exception_handler(RequireLogin)
    async def _require_login_handler(request: Request, exc: RequireLogin):
        return redirect_to_login()

    app.include_router(auth_routes.router)
    app.include_router(dashboard.router)
    app.include_router(trips.router)
    app.include_router(bookings.router)
    app.include_router(users.router)
    app.include_router(ratings.router)
    app.include_router(points.router)
    app.include_router(audit.router)
    return app
