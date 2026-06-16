"""PostgreSQL: соединение, схема v11, транзакции."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg import Connection, Cursor
from psycopg.rows import dict_row

from app.db import CURRENT_SCHEMA_VERSION
from app.db_common import apply_route_hierarchy_simplify, fill_route_point_coordinates, seed_route_points
from app.sql_dialect import SqlDialect

_POSTGRES_BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    tg_user_id BIGINT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    username TEXT,
    role TEXT NOT NULL CHECK (role IN ('driver', 'passenger')),
    phone TEXT,
    rating_avg DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    rating_count INTEGER NOT NULL DEFAULT 0,
    trips_driver_count INTEGER NOT NULL DEFAULT 0,
    trips_passenger_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dl_series_number TEXT,
    dl_valid_until TEXT,
    min_passenger_rating DOUBLE PRECISION,
    is_banned INTEGER NOT NULL DEFAULT 0,
    car_model TEXT,
    car_color TEXT,
    car_plate TEXT,
    driver_moderation_status TEXT NOT NULL DEFAULT 'approved'
        CHECK (driver_moderation_status IN ('pending', 'approved', 'rejected'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_dl_series
    ON users(dl_series_number)
    WHERE dl_series_number IS NOT NULL AND dl_series_number != '';

CREATE TABLE IF NOT EXISTS route_points (
    id SERIAL PRIMARY KEY,
    locality TEXT NOT NULL,
    district TEXT NOT NULL DEFAULT '',
    admin_area TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'stop' CHECK (kind IN ('stop', 'locality')),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_route_point
    ON route_points(locality, district, admin_area, title);

CREATE TABLE IF NOT EXISTS trips (
    id SERIAL PRIMARY KEY,
    driver_id INTEGER NOT NULL REFERENCES users(id),
    start_point_id INTEGER NOT NULL REFERENCES route_points(id),
    end_point_id INTEGER NOT NULL REFERENCES route_points(id),
    trip_date TEXT NOT NULL DEFAULT '',
    departure_time TEXT NOT NULL DEFAULT '',
    time_slot TEXT NOT NULL,
    price_rub INTEGER NOT NULL,
    seats_total INTEGER NOT NULL,
    seats_booked INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'cancelled', 'completed')),
    comment TEXT,
    allow_intermediate_pickup BOOLEAN NOT NULL DEFAULT TRUE,
    route_polyline TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bookings (
    id SERIAL PRIMARY KEY,
    trip_id INTEGER NOT NULL REFERENCES trips(id),
    passenger_id INTEGER NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'cancelled_by_passenger', 'cancelled_by_driver')),
    cancel_reason TEXT,
    boarding_stop_id INTEGER REFERENCES route_points(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cancelled_at TIMESTAMPTZ,
    UNIQUE(trip_id, passenger_id)
);

CREATE TABLE IF NOT EXISTS favorite_routes (
    id SERIAL PRIMARY KEY,
    tg_user_id BIGINT NOT NULL,
    start_point_id INTEGER NOT NULL REFERENCES route_points(id),
    end_point_id INTEGER NOT NULL REFERENCES route_points(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tg_user_id, start_point_id, end_point_id)
);

CREATE INDEX IF NOT EXISTS idx_favorite_routes_user ON favorite_routes(tg_user_id);

CREATE TABLE IF NOT EXISTS trip_ratings (
    id SERIAL PRIMARY KEY,
    trip_id INTEGER NOT NULL REFERENCES trips(id),
    rater_user_id INTEGER NOT NULL REFERENCES users(id),
    rated_user_id INTEGER NOT NULL REFERENCES users(id),
    stars INTEGER NOT NULL CHECK (stars >= 1 AND stars <= 5),
    review_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(trip_id, rater_user_id, rated_user_id)
);

CREATE INDEX IF NOT EXISTS idx_trip_ratings_trip ON trip_ratings(trip_id);
CREATE INDEX IF NOT EXISTS idx_trip_ratings_rated ON trip_ratings(rated_user_id);
CREATE INDEX IF NOT EXISTS idx_trip_ratings_trip_rater_rated
    ON trip_ratings(trip_id, rater_user_id, rated_user_id);

CREATE TABLE IF NOT EXISTS rating_prompts_sent (
    trip_id INTEGER NOT NULL REFERENCES trips(id),
    rater_user_id INTEGER NOT NULL REFERENCES users(id),
    rated_user_id INTEGER NOT NULL REFERENCES users(id),
    sent_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trip_id, rater_user_id, rated_user_id)
);

CREATE INDEX IF NOT EXISTS idx_rating_prompts_trip_rater_rated
    ON rating_prompts_sent(trip_id, rater_user_id, rated_user_id);

CREATE TABLE IF NOT EXISTS chat_anchors (
    chat_id BIGINT PRIMARY KEY,
    anchor_message_id BIGINT NOT NULL,
    flow_kind TEXT NOT NULL,
    reply_aux_message_id BIGINT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admin_users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id SERIAL PRIMARY KEY,
    admin_username TEXT NOT NULL,
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_id TEXT,
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_admin_audit_created ON admin_audit_log(created_at);

CREATE TABLE IF NOT EXISTS trip_templates (
    id SERIAL PRIMARY KEY,
    driver_id INTEGER NOT NULL REFERENCES users(id),
    start_point_id INTEGER NOT NULL REFERENCES route_points(id),
    end_point_id INTEGER NOT NULL REFERENCES route_points(id),
    price_rub INTEGER NOT NULL,
    seats_total INTEGER NOT NULL,
    comment TEXT,
    schedule_days TEXT,
    schedule_time TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trip_templates_driver ON trip_templates(driver_id);

CREATE TABLE IF NOT EXISTS trip_stops (
    id SERIAL PRIMARY KEY,
    trip_id INTEGER NOT NULL REFERENCES trips(id),
    stop_id INTEGER NOT NULL REFERENCES route_points(id),
    order_index INTEGER NOT NULL DEFAULT 0,
    UNIQUE(trip_id, stop_id)
);

CREATE INDEX IF NOT EXISTS idx_trip_stops_trip ON trip_stops(trip_id);
CREATE INDEX IF NOT EXISTS idx_trip_stops_stop ON trip_stops(stop_id);

CREATE INDEX IF NOT EXISTS idx_trips_status_date_route
    ON trips(status, trip_date, start_point_id, end_point_id);
CREATE INDEX IF NOT EXISTS idx_bookings_passenger_status ON bookings(passenger_id, status);
CREATE INDEX IF NOT EXISTS idx_bookings_trip_status ON bookings(trip_id, status);
"""


class _PgConnAdapter:
    """Адаптер: SQL с «?» как в SQLite, драйвер psycopg получает «%s»."""

    def __init__(self, conn: Connection[dict[str, Any]]) -> None:
        self._conn = conn

    def execute(self, query: str, params: tuple[Any, ...] | list[Any] = ()) -> Cursor[dict[str, Any]]:
        return self._conn.execute(query.replace("?", "%s"), params)


class PostgresDatabase:
    """Обёртка над PostgreSQL-соединением (аналог SQLite Database)."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.dialect = SqlDialect("postgres")
        self._conn: Connection[dict[str, Any]] | None = None
        self._lock = threading.RLock()

    def _ensure_connection(self) -> Connection[dict[str, Any]]:
        if self._conn is None:
            self._conn = psycopg.connect(self.database_url, row_factory=dict_row, autocommit=False)
        return self._conn

    def connect(self) -> Connection[dict[str, Any]]:
        return self._ensure_connection()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def wal_checkpoint_truncate(self) -> None:
        """No-op для PostgreSQL (совместимость с SQLite API)."""

    @contextmanager
    def transaction(self) -> Iterator[_PgConnAdapter]:
        with self._lock:
            conn = self._ensure_connection()
            adapter = _PgConnAdapter(conn)
            try:
                yield adapter
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    @contextmanager
    def immediate_transaction(self) -> Iterator[_PgConnAdapter]:
        with self._lock:
            conn = self._ensure_connection()
            adapter = _PgConnAdapter(conn)
            try:
                yield adapter
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def init_schema(self) -> None:
        with self._lock:
            conn = self._ensure_connection()
            conn.execute(_POSTGRES_BOOTSTRAP_SQL)
            row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
            if row is None:
                adapter = _PgConnAdapter(conn)
                seed_route_points(adapter, self.dialect)
                apply_route_hierarchy_simplify(adapter)
                fill_route_point_coordinates(adapter, self.dialect)
                conn.execute(
                    "INSERT INTO schema_version(id, version) VALUES (1, %s)",
                    (CURRENT_SCHEMA_VERSION,),
                )
                conn.commit()
                return
            v = int(row["version"])
            while v < CURRENT_SCHEMA_VERSION:
                self._apply_pg_migration(conn, v, v + 1)
                conn.execute(
                    "UPDATE schema_version SET version = %s WHERE id = 1", (v + 1,)
                )
                conn.commit()
                v += 1
            conn.commit()

    def _apply_pg_migration(self, conn: Any, from_v: int, to_v: int) -> None:
        if from_v == 11 and to_v == 12:
            self._pg_migrate_v11_to_v12(conn)
            return
        raise RuntimeError(f"No PostgreSQL migration defined from v{from_v} to v{to_v}")

    def _pg_migrate_v11_to_v12(self, conn: Any) -> None:
        """Промежуточные посадки: новые колонки в trips/bookings + таблица trip_stops."""
        conn.execute("""
            ALTER TABLE trips
                ADD COLUMN IF NOT EXISTS allow_intermediate_pickup BOOLEAN NOT NULL DEFAULT TRUE,
                ADD COLUMN IF NOT EXISTS route_polyline TEXT
        """)
        conn.execute("""
            ALTER TABLE bookings
                ADD COLUMN IF NOT EXISTS boarding_stop_id INTEGER REFERENCES route_points(id)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trip_stops (
                id SERIAL PRIMARY KEY,
                trip_id INTEGER NOT NULL REFERENCES trips(id),
                stop_id INTEGER NOT NULL REFERENCES route_points(id),
                order_index INTEGER NOT NULL DEFAULT 0,
                UNIQUE(trip_id, stop_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trip_stops_trip ON trip_stops(trip_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trip_stops_stop ON trip_stops(stop_id)")

    def insert_returning_id(self, adapter: _PgConnAdapter, sql: str, params: tuple[Any, ...]) -> int:
        adapted = sql.strip().replace("?", "%s")
        if "RETURNING" not in adapted.upper():
            adapted = adapted.rstrip(";") + " RETURNING id"
        row = adapter.execute(adapted, params).fetchone()
        if row is None:
            raise RuntimeError("INSERT RETURNING id не вернул строку")
        return int(row["id"])
