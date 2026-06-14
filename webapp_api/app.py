"""Фабрика FastAPI-приложения Mini App API: lifespan с БД/repo, CORS, маршруты."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.database import open_database
from app.repo import Repo
from webapp_api.bot_notify import BotNotifier
from webapp_api.config import WebAppSettings, load_webapp_settings
from webapp_api.routes import (
    bookings,
    catalog,
    favorites,
    history,
    manage,
    me,
    notifications,
    ratings,
    templates,
    trips,
)

logger = logging.getLogger(__name__)


def create_app(settings: WebAppSettings | None = None) -> FastAPI:
    settings = settings or load_webapp_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = open_database(database_url=settings.database_url, db_path=settings.db_path)
        db.init_schema()
        app.state.settings = settings
        app.state.db = db
        app.state.repo = Repo(db)
        app.state.notifier = BotNotifier(settings.bot_token)
        try:
            yield
        finally:
            await app.state.notifier.close()
            db.close()

    app = FastAPI(title="Yaride Mini App API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health(request: Request) -> dict:
        db = request.app.state.db
        backend = "postgresql" if db.__class__.__name__ == "PostgresDatabase" else "sqlite"
        return {"status": "ok", "database": backend}

    app.include_router(me.router)
    app.include_router(catalog.router)
    app.include_router(trips.router)
    app.include_router(bookings.router)
    app.include_router(manage.router)
    app.include_router(ratings.router)
    app.include_router(notifications.router)
    app.include_router(history.router)
    app.include_router(favorites.router)
    app.include_router(templates.router)
    return app
