"""Фабрика FastAPI-приложения Mini App API: lifespan с БД/repo, CORS, маршруты."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Database
from app.repo import Repo
from webapp_api.config import WebAppSettings, load_webapp_settings
from webapp_api.routes import bookings, catalog, favorites, manage, me, ratings, templates, trips

logger = logging.getLogger(__name__)


def create_app(settings: WebAppSettings | None = None) -> FastAPI:
    settings = settings or load_webapp_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(settings.db_path)
        db.init_schema()
        app.state.settings = settings
        app.state.db = db
        app.state.repo = Repo(db)
        try:
            yield
        finally:
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
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(me.router)
    app.include_router(catalog.router)
    app.include_router(trips.router)
    app.include_router(bookings.router)
    app.include_router(manage.router)
    app.include_router(ratings.router)
    app.include_router(favorites.router)
    app.include_router(templates.router)
    return app
