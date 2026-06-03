"""SQLite-база данных: соединение, схема и линейные миграции по версии.

Единственный файл *.db; одно постоянное соединение с RLock гарантирует безопасность
при однопоточном asyncio-боте. WAL включён, чтобы read-транзакции не блокировали writes.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from app.geo_stops import COORDINATE_OVERRIDES, lat_lng_for_stop
from app.seeds import ROUTE_HIERARCHY

# Текущая версия схемы кода.
# v2 — этап 1 (WAL); v3 — этап 2 (индексы);
# v4 — этап 4: таблица anchor-сообщений flow;
# v5 — этап 4: reply_aux_message_id в chat_anchors + drop bot_chat_messages (legacy cleanup_chat).
# v6 — админка: users.is_banned, таблицы admin_users и admin_audit_log.
CURRENT_SCHEMA_VERSION = 6
SCHEMA_VERSION = CURRENT_SCHEMA_VERSION


class Database:
    """Обёртка над единственным SQLite-соединением с поддержкой транзакций и миграций."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    def _ensure_connection(self) -> sqlite3.Connection:
        """Создаёт соединение при первом обращении с оптимальными PRAGMA для single-process бота.

        isolation_level=None — autocommit отключён; транзакции управляются явно через BEGIN/COMMIT,
        что позволяет использовать BEGIN IMMEDIATE для исключения гонок при записи.
        """
        if self._conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.isolation_level = None
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            self._conn = conn
        return self._conn

    def connect(self) -> sqlite3.Connection:
        """Обратная совместимость: возвращает постоянное соединение."""
        return self._ensure_connection()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Стандартная транзакция (BEGIN DEFERRED). Использовать для read-операций и некритичных write."""
        with self._lock:
            conn = self._ensure_connection()
            conn.execute("BEGIN")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    @contextmanager
    def immediate_transaction(self) -> Iterator[sqlite3.Connection]:
        """Транзакция с захватом write-lock сразу (BEGIN IMMEDIATE).

        Используется для критичных секций (бронирование мест, отмена поездки), чтобы исключить
        ситуацию, когда два пользователя одновременно видят «1 свободное место» и оба бронируют.
        """
        with self._lock:
            conn = self._ensure_connection()
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def init_schema(self) -> None:
        """Создаёт схему с нуля или прогоняет линейные миграции до текущей версии.

        Свежий файл .db получает полный bootstrap (версия → CURRENT_SCHEMA_VERSION).
        Существующий файл мигрирует шаг за шагом, чтобы не терять данные пользователей.
        """
        with self._lock:
            conn = self._ensure_connection()
            self._ensure_schema_version_table(conn)
            row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
            if row is None:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    self._bootstrap_full_schema(conn)
                    conn.execute(
                        "INSERT INTO schema_version(id, version) VALUES (1, ?)",
                        (CURRENT_SCHEMA_VERSION,),
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
                return

            v = int(row["version"])
            while v < CURRENT_SCHEMA_VERSION:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    self._apply_migration(conn, v, v + 1)
                    conn.execute("UPDATE schema_version SET version = ? WHERE id = 1", (v + 1,))
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
                v += 1

    def _ensure_schema_version_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY CHECK(id = 1),
                version INTEGER NOT NULL
            )
            """
        )

    def _apply_migration(self, conn: sqlite3.Connection, from_v: int, to_v: int) -> None:
        if from_v == 1 and to_v == 2:
            self._migrate_v1_to_v2(conn)
            return
        if from_v == 2 and to_v == 3:
            self._migrate_v2_to_v3(conn)
            return
        if from_v == 3 and to_v == 4:
            self._migrate_v3_to_v4(conn)
            return
        if from_v == 4 and to_v == 5:
            self._migrate_v4_to_v5(conn)
            return
        if from_v == 5 and to_v == 6:
            self._migrate_v5_to_v6(conn)
            return
        raise RuntimeError(f"No migration defined from v{from_v} to v{to_v}")

    def _migrate_v1_to_v2(self, conn: sqlite3.Connection) -> None:
        """Один раз при переходе с этапа 0: применить правки иерархии route_points (раньше дёргалось на каждой транзакции)."""
        self._migrate_route_hierarchy_simplify(conn)

    def _migrate_v2_to_v3(self, conn: sqlite3.Connection) -> None:
        """Индексы под типовые запросы поездок, броней и рейтингов (этап 2)."""
        self._ensure_performance_indexes(conn)

    def _migrate_v3_to_v4(self, conn: sqlite3.Connection) -> None:
        """Этап 4: таблица chat_anchors для anchor-сообщений flow."""
        self._ensure_chat_anchors_table(conn)

    def _migrate_v4_to_v5(self, conn: sqlite3.Connection) -> None:
        """Этап 4 (завершение): reply_aux_message_id в chat_anchors + удаление bot_chat_messages."""
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(chat_anchors)").fetchall()}
        if "reply_aux_message_id" not in cols:
            conn.execute("ALTER TABLE chat_anchors ADD COLUMN reply_aux_message_id INTEGER")
        conn.execute("DROP TABLE IF EXISTS bot_chat_messages")

    def _migrate_v5_to_v6(self, conn: sqlite3.Connection) -> None:
        """Админка: флаг бана у пользователя + таблицы учётных записей админов и журнала действий."""
        self._ensure_users_is_banned(conn)
        self._ensure_admin_tables(conn)

    def _ensure_users_is_banned(self, conn: sqlite3.Connection) -> None:
        """is_banned — мягкая блокировка: забаненный пользователь сохраняется (FK-связи целы), но не обслуживается ботом."""
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if not cols:
            # Таблицы users ещё нет (порядок bootstrap или искусственная фикстура) — добавит её владелец схемы.
            return
        if "is_banned" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER NOT NULL DEFAULT 0")

    def _ensure_admin_tables(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_login_at TEXT
            );

            CREATE TABLE IF NOT EXISTS admin_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_username TEXT NOT NULL,
                action TEXT NOT NULL,
                entity TEXT NOT NULL,
                entity_id TEXT,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_admin_audit_created ON admin_audit_log(created_at);
            """
        )

    def _ensure_chat_anchors_table(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chat_anchors (
                chat_id INTEGER PRIMARY KEY,
                anchor_message_id INTEGER NOT NULL,
                flow_kind TEXT NOT NULL,
                reply_aux_message_id INTEGER,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

    def _ensure_performance_indexes(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_trips_status_date_route
                ON trips(status, trip_date, start_point_id, end_point_id);

            CREATE INDEX IF NOT EXISTS idx_bookings_passenger_status
                ON bookings(passenger_id, status);

            CREATE INDEX IF NOT EXISTS idx_bookings_trip_status
                ON bookings(trip_id, status);

            CREATE INDEX IF NOT EXISTS idx_trip_ratings_rated
                ON trip_ratings(rated_user_id);

            CREATE INDEX IF NOT EXISTS idx_trip_ratings_trip_rater_rated
                ON trip_ratings(trip_id, rater_user_id, rated_user_id);

            CREATE INDEX IF NOT EXISTS idx_rating_prompts_trip_rater_rated
                ON rating_prompts_sent(trip_id, rater_user_id, rated_user_id);
            """
        )

    def _bootstrap_full_schema(self, conn: sqlite3.Connection) -> None:
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
        self._migrate_route_points_latlng(conn)
        self._migrate_favorites_and_ratings(conn)
        self._migrate_trip_ratings_review_text(conn)
        self._seed_route_points(conn)
        self._migrate_route_hierarchy_simplify(conn)
        self._fill_route_point_coordinates(conn)
        self._ensure_performance_indexes(conn)
        self._ensure_chat_anchors_table(conn)
        self._ensure_users_is_banned(conn)
        self._ensure_admin_tables(conn)

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(trips)").fetchall()}
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
            conn.execute("ALTER TABLE users ADD COLUMN min_passenger_rating REAL")

    def _migrate_route_points_schema(self, conn: sqlite3.Connection) -> None:
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='route_points'").fetchone()
        if not row or not row["sql"]:
            return
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(route_points)").fetchall()}
        if "locality" in cols and "admin_area" in cols:
            conn.execute("DROP INDEX IF EXISTS uq_route_point")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_route_point ON route_points(locality, district, admin_area, title)"
            )
            return

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

    def _migrate_trip_ratings_review_text(self, conn: sqlite3.Connection) -> None:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(trip_ratings)").fetchall()}
        if cols and "review_text" not in cols:
            conn.execute("ALTER TABLE trip_ratings ADD COLUMN review_text TEXT")

    def _migrate_route_hierarchy_simplify(self, conn: sqlite3.Connection) -> None:
        """Объединяет мелкие подрайоны в один, чтобы не показывать пользователю слишком длинный список.

        Применяется и при миграции v1→v2, и при bootstrap — идемпотентно (UPDATE не падает на уже обновлённых строках).
        """
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(route_points)").fetchall()}
        if not cols or "admin_area" not in cols:
            return
        conn.execute(
            """
            UPDATE route_points SET admin_area = 'Весь Ленинский район'
            WHERE locality = 'Ярославль' AND district = 'Ленинский район'
              AND admin_area IN ('Загородный Сад', 'Пятёрка')
            """
        )
        conn.execute(
            """
            UPDATE route_points SET admin_area = 'Посёлки (малые)'
            WHERE locality = 'Ярославль' AND district = 'Красноперекопский район'
              AND admin_area IN (
                'Бутырки', 'Забелицы', 'Новодуховское', 'Творогово', 'пос. Силикатного завода'
              )
            """
        )

    def _migrate_route_points_latlng(self, conn: sqlite3.Connection) -> None:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(route_points)").fetchall()}
        if not cols:
            return
        if "latitude" not in cols:
            conn.execute("ALTER TABLE route_points ADD COLUMN latitude REAL")
        if "longitude" not in cols:
            conn.execute("ALTER TABLE route_points ADD COLUMN longitude REAL")

    def _fill_route_point_coordinates(self, conn: sqlite3.Connection) -> None:
        """Проставить координаты остановкам, у которых они ещё не заполнены.

        Координаты берутся из geo_stops (справочник + jitter), а не из внешнего API,
        чтобы не зависеть от сети при запуске и не терять данные при смене провайдера геокодинга.
        """
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(route_points)").fetchall()}
        if "latitude" not in cols or "longitude" not in cols:
            return
        rows = conn.execute(
            """
            SELECT id, locality, district, admin_area, title FROM route_points
            WHERE kind = 'stop' AND (latitude IS NULL OR longitude IS NULL)
            """
        ).fetchall()
        for r in rows:
            lat, lng = lat_lng_for_stop(
                str(r["locality"]),
                str(r["district"] or ""),
                str(r["admin_area"] or ""),
                str(r["title"]),
            )
            conn.execute(
                "UPDATE route_points SET latitude = ?, longitude = ? WHERE id = ?",
                (lat, lng, int(r["id"])),
            )
        for loc, dist, adm, title in COORDINATE_OVERRIDES:
            lat, lng = lat_lng_for_stop(loc, dist, adm, title)
            conn.execute(
                """
                UPDATE route_points
                SET latitude = ?, longitude = ?
                WHERE kind = 'stop' AND locality = ? AND COALESCE(district, '') = ? AND COALESCE(admin_area, '') = ? AND title = ?
                """,
                (lat, lng, loc, dist, adm, title),
            )

    def _seed_route_points(self, conn: sqlite3.Connection) -> None:
        """Заполнить справочник остановок из статических данных seeds.py.

        Если остановки уже есть, но поездок нет — перезаполнить: это позволяет обновлять
        каталог остановок без ручного SQL при развёртывании свежей копии.
        """
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
