from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from app.seeds import ROUTE_HIERARCHY


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @contextmanager
    def transaction(self):
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.transaction() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tg_user_id INTEGER UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    username TEXT,
                    role TEXT CHECK(role IN ('driver', 'passenger')) NOT NULL,
                    phone TEXT,
                    rating_avg REAL NOT NULL DEFAULT 0.0,
                    rating_count INTEGER NOT NULL DEFAULT 0,
                    trips_driver_count INTEGER NOT NULL DEFAULT 0,
                    trips_passenger_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS route_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    locality TEXT NOT NULL,
                    district TEXT NOT NULL DEFAULT '',
                    admin_area TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'stop' CHECK(kind IN ('stop', 'locality'))
                );

                CREATE TABLE IF NOT EXISTS trips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    driver_id INTEGER NOT NULL,
                    start_point_id INTEGER NOT NULL,
                    end_point_id INTEGER NOT NULL,
                    trip_date TEXT NOT NULL DEFAULT '',
                    departure_time TEXT NOT NULL DEFAULT '',
                    time_slot TEXT NOT NULL,
                    price_rub INTEGER NOT NULL,
                    seats_total INTEGER NOT NULL,
                    seats_booked INTEGER NOT NULL DEFAULT 0,
                    status TEXT CHECK(status IN ('open', 'cancelled', 'completed')) NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(driver_id) REFERENCES users(id),
                    FOREIGN KEY(start_point_id) REFERENCES route_points(id),
                    FOREIGN KEY(end_point_id) REFERENCES route_points(id)
                );

                CREATE TABLE IF NOT EXISTS bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trip_id INTEGER NOT NULL,
                    passenger_id INTEGER NOT NULL,
                    status TEXT CHECK(status IN ('active', 'cancelled_by_passenger', 'cancelled_by_driver')) NOT NULL DEFAULT 'active',
                    cancel_reason TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    cancelled_at TEXT,
                    UNIQUE(trip_id, passenger_id),
                    FOREIGN KEY(trip_id) REFERENCES trips(id),
                    FOREIGN KEY(passenger_id) REFERENCES users(id)
                );
                """
            )
            self._migrate_schema(conn)
            self._migrate_users_dl_columns(conn)
            self._migrate_users_min_passenger_rating(conn)
            self._migrate_route_points_schema(conn)
            self._migrate_favorites_and_ratings(conn)
            self._migrate_bot_chat_messages(conn)
            self._migrate_trip_ratings_review_text(conn)
            self._seed_route_points(conn)

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(trips)").fetchall()
        }
        if "trip_date" not in columns:
            conn.execute("ALTER TABLE trips ADD COLUMN trip_date TEXT NOT NULL DEFAULT ''")
        if "departure_time" not in columns:
            conn.execute("ALTER TABLE trips ADD COLUMN departure_time TEXT NOT NULL DEFAULT ''")

    def _migrate_users_dl_columns(self, conn: sqlite3.Connection) -> None:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "dl_series_number" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN dl_series_number TEXT")
        if "dl_valid_until" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN dl_valid_until TEXT")
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_users_dl_series
            ON users(dl_series_number)
            WHERE dl_series_number IS NOT NULL AND dl_series_number != ''
            """
        )

    def _migrate_users_min_passenger_rating(self, conn: sqlite3.Connection) -> None:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "min_passenger_rating" not in cols:
            conn.execute(
                "ALTER TABLE users ADD COLUMN min_passenger_rating REAL"
            )

    def _migrate_route_points_schema(self, conn: sqlite3.Connection) -> None:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='route_points'"
        ).fetchone()
        if not row or not row["sql"]:
            return
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(route_points)").fetchall()}
        if "locality" in cols and "admin_area" in cols:
            conn.execute("DROP INDEX IF EXISTS uq_route_point")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_route_point ON route_points(locality, district, admin_area, title)"
            )
            return

        # Старый формат без locality: только ALTER+UPDATE — без DROP (есть FK из trips).
        if "locality" not in cols:
            conn.execute("ALTER TABLE route_points ADD COLUMN locality TEXT")
            conn.execute(
                """
                UPDATE route_points
                SET locality = title,
                    title = 'Центр · ' || title,
                    district = '',
                    kind = 'stop'
                WHERE kind = 'locality'
                """
            )
            conn.execute(
                """
                UPDATE route_points
                SET locality = 'Ярославль',
                    district = COALESCE(district, '')
                WHERE locality IS NULL
                """
            )
        if "admin_area" not in cols:
            conn.execute("ALTER TABLE route_points ADD COLUMN admin_area TEXT NOT NULL DEFAULT ''")
            conn.execute("UPDATE route_points SET admin_area = '' WHERE admin_area IS NULL")
        conn.execute("DROP INDEX IF EXISTS uq_route_point")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_route_point ON route_points(locality, district, admin_area, title)"
        )

    def _migrate_favorites_and_ratings(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS favorite_routes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_user_id INTEGER NOT NULL,
                start_point_id INTEGER NOT NULL,
                end_point_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tg_user_id, start_point_id, end_point_id),
                FOREIGN KEY(start_point_id) REFERENCES route_points(id),
                FOREIGN KEY(end_point_id) REFERENCES route_points(id)
            );
            CREATE INDEX IF NOT EXISTS idx_favorite_routes_user ON favorite_routes(tg_user_id);

            CREATE TABLE IF NOT EXISTS trip_ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                rater_user_id INTEGER NOT NULL,
                rated_user_id INTEGER NOT NULL,
                stars INTEGER NOT NULL CHECK(stars >= 1 AND stars <= 5),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(trip_id, rater_user_id, rated_user_id),
                FOREIGN KEY(trip_id) REFERENCES trips(id),
                FOREIGN KEY(rater_user_id) REFERENCES users(id),
                FOREIGN KEY(rated_user_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_trip_ratings_trip ON trip_ratings(trip_id);

            CREATE TABLE IF NOT EXISTS rating_prompts_sent (
                trip_id INTEGER NOT NULL,
                rater_user_id INTEGER NOT NULL,
                rated_user_id INTEGER NOT NULL,
                sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (trip_id, rater_user_id, rated_user_id),
                FOREIGN KEY(trip_id) REFERENCES trips(id),
                FOREIGN KEY(rater_user_id) REFERENCES users(id),
                FOREIGN KEY(rated_user_id) REFERENCES users(id)
            );
            """
        )

    def _migrate_bot_chat_messages(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS bot_chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_bot_chat_messages_chat ON bot_chat_messages(chat_id);
            """
        )

    def _migrate_trip_ratings_review_text(self, conn: sqlite3.Connection) -> None:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(trip_ratings)").fetchall()}
        if cols and "review_text" not in cols:
            conn.execute("ALTER TABLE trip_ratings ADD COLUMN review_text TEXT")

    def _seed_route_points(self, conn: sqlite3.Connection) -> None:
        existing = conn.execute("SELECT COUNT(*) AS cnt FROM route_points").fetchone()["cnt"]
        if existing > 0:
            trips_cnt = conn.execute("SELECT COUNT(*) AS cnt FROM trips").fetchone()["cnt"]
            if trips_cnt == 0:
                conn.execute("DELETE FROM route_points")

        for locality, districts in ROUTE_HIERARCHY.items():
            for district, admin_areas in districts.items():
                d = district if district else ""
                for admin_area, stops in admin_areas.items():
                    a = admin_area if admin_area else ""
                    for stop_name in stops:
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO route_points(locality, district, admin_area, title, kind)
                            VALUES (?, ?, ?, ?, 'stop')
                            """,
                            (locality, d, a, stop_name),
                        )
