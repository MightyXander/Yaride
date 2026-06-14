"""Фабрика БД: PostgreSQL (DATABASE_URL) или SQLite (DB_PATH)."""

from __future__ import annotations

import os
import sqlite3
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from app.db import Database as SqliteDatabase
    from app.db_postgres import PostgresDatabase

DbHandle = Union["SqliteDatabase", "PostgresDatabase"]


def resolve_database_url() -> str | None:
    raw = os.getenv("DATABASE_URL", "").strip()
    return raw or None


def open_database(*, database_url: str | None = None, db_path: str | None = None) -> DbHandle:
    """Открыть БД: Postgres при DATABASE_URL, иначе SQLite по DB_PATH."""
    url = database_url if database_url is not None else resolve_database_url()
    if url:
        from app.db_postgres import PostgresDatabase

        return PostgresDatabase(url)

    from app.db import Database

    path = (db_path or os.getenv("DB_PATH", "yaride.db").strip() or "yaride.db")
    return Database(path)


def is_unique_violation(exc: BaseException) -> bool:
    """Нарушение UNIQUE — SQLite IntegrityError или Postgres UniqueViolation."""
    if isinstance(exc, sqlite3.IntegrityError):
        return True
    try:
        import psycopg.errors
    except ImportError:
        return False
    return isinstance(exc, psycopg.errors.UniqueViolation)


def insert_returning_id(db: DbHandle, conn, sql: str, params: tuple) -> int:  # noqa: ANN001
    """Вставка с получением id (RETURNING для Postgres, lastrowid для SQLite)."""
    if hasattr(db, "insert_returning_id"):
        return db.insert_returning_id(conn, sql, params)  # type: ignore[attr-defined]
    cur = conn.execute(sql, params)
    return int(cur.lastrowid)
