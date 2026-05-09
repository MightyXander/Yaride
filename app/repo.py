from __future__ import annotations

import sqlite3
from datetime import date, datetime
from typing import Iterable

from app.db import Database
from app.driver_license import assert_license_not_expired, normalize_license_number
from app.seeds import ROUTE_HIERARCHY


class _BaseRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    @staticmethod
    def _ensure_telegram_identity(conn: sqlite3.Connection, user_id: int, tg_user_id: int) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO user_identities(user_id, provider, external_uid)
            VALUES (?, 'telegram', ?)
            """,
            (user_id, str(tg_user_id)),
        )

    @staticmethod
    def _trip_start_dt(trip_date: str | None, departure_time: str | None) -> datetime | None:
        if not trip_date or not departure_time:
            return None
        try:
            return datetime.strptime(f"{trip_date.strip()} {departure_time.strip()}", "%Y-%m-%d %H:%M")
        except ValueError:
            return None

    @staticmethod
    def _get_internal_user_id(conn: sqlite3.Connection, tg_user_id: int) -> int:
        row = conn.execute("SELECT id FROM users WHERE tg_user_id = ?", (tg_user_id,)).fetchone()
        if not row:
            raise ValueError("Пользователь не зарегистрирован.")
        return int(row["id"])


class UserRepository(_BaseRepository):
    def upsert_user(self, tg_user_id: int, name: str, username: str | None, role: str) -> None:
        if role == "driver":
            raise ValueError(
                "Роль водителя сохраняется только вместе с данными водительского удостоверения."
            )
        with self.db.transaction() as conn:
            row = conn.execute("SELECT id FROM users WHERE tg_user_id = ?", (tg_user_id,)).fetchone()
            if row:
                conn.execute(
                    """
                    UPDATE users
                    SET name = ?, username = ?, role = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE tg_user_id = ?
                    """,
                    (name, username, role, tg_user_id),
                )
                self._ensure_telegram_identity(conn, int(row["id"]), tg_user_id)
                return

            cur = conn.execute(
                """
                INSERT INTO users(tg_user_id, name, username, role)
                VALUES (?, ?, ?, ?)
                """,
                (tg_user_id, name, username, role),
            )
            uid = int(cur.lastrowid)
            self._ensure_telegram_identity(conn, uid, tg_user_id)

    def get_user(self, tg_user_id: int) -> sqlite3.Row | None:
        with self.db.transaction() as conn:
            return conn.execute("SELECT * FROM users WHERE tg_user_id = ?", (tg_user_id,)).fetchone()

    def switch_role(self, tg_user_id: int, new_role: str, for_date: str) -> tuple[bool, str]:
        if new_role not in ("driver", "passenger"):
            return False, "Недопустимая роль."

        with self.db.transaction() as conn:
            user = conn.execute("SELECT id, role FROM users WHERE tg_user_id = ?", (tg_user_id,)).fetchone()
            if not user:
                return False, "Сначала зарегистрируйся через /start."
            if user["role"] == new_role:
                return False, "У тебя уже выбрана эта роль."

            if user["role"] == "driver":
                cnt_row = conn.execute(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM trips
                    WHERE driver_id = ? AND trip_date = ? AND status = 'open'
                    """,
                    (user["id"], for_date),
                ).fetchone()
                if cnt_row and int(cnt_row["cnt"]) > 0:
                    return False, "Нельзя сменить роль: на выбранную дату есть активные поездки."

            if new_role == "driver":
                lic = conn.execute(
                    "SELECT valid_until FROM driver_license_verifications WHERE user_id = ?",
                    (user["id"],),
                ).fetchone()
                if not lic:
                    return False, "Для роли водителя сначала укажи данные водительского удостоверения."
                try:
                    switch_date = datetime.strptime(for_date, "%Y-%m-%d").date()
                    expiry_date = datetime.strptime(str(lic["valid_until"]), "%Y-%m-%d").date()
                except ValueError:
                    return False, "Некорректная дата действия прав в профиле."
                if expiry_date < switch_date:
                    return False, "Нельзя выбрать роль водителя: права недействительны на выбранную дату."

            conn.execute(
                "UPDATE users SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_role, user["id"]),
            )
            return True, "Роль обновлена."


class DriverLicenseRepository(_BaseRepository):
    """Базовая верификация по ВУ: самодекларация + проверка формата и срока (без ГИБДД)."""

    def register_driver_with_license(
        self,
        tg_user_id: int,
        name: str,
        username: str | None,
        license_series_number: str,
        valid_until: date,
    ) -> None:
        normalized = normalize_license_number(license_series_number)
        assert_license_not_expired(valid_until)
        valid_iso = valid_until.isoformat()
        with self.db.transaction() as conn:
            row = conn.execute("SELECT id FROM users WHERE tg_user_id = ?", (tg_user_id,)).fetchone()
            if row:
                uid = int(row["id"])
                conn.execute(
                    """
                    UPDATE users
                    SET name = ?, username = ?, role = 'driver', updated_at = CURRENT_TIMESTAMP
                    WHERE tg_user_id = ?
                    """,
                    (name, username, tg_user_id),
                )
            else:
                cur = conn.execute(
                    """
                    INSERT INTO users(tg_user_id, name, username, role)
                    VALUES (?, ?, ?, 'driver')
                    """,
                    (tg_user_id, name, username),
                )
                uid = int(cur.lastrowid)

            self._ensure_telegram_identity(conn, uid, tg_user_id)

            conn.execute(
                """
                INSERT INTO driver_license_verifications(
                    user_id, license_series_number, valid_until, verification_method, updated_at
                ) VALUES (?, ?, ?, 'self_declared', CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    license_series_number = excluded.license_series_number,
                    valid_until = excluded.valid_until,
                    verification_method = 'self_declared',
                    updated_at = CURRENT_TIMESTAMP
                """,
                (uid, normalized, valid_iso),
            )


class RouteRepository(_BaseRepository):
    def route_points(self) -> list[sqlite3.Row]:
        with self.db.transaction() as conn:
            return conn.execute("SELECT * FROM route_points ORDER BY locality, district, title").fetchall()

    def list_localities(self) -> list[str]:
        with self.db.transaction() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT locality FROM route_points
                WHERE kind = 'stop'
                ORDER BY locality
                """
            ).fetchall()
        localities = [str(row["locality"]) for row in rows]
        localities.sort(key=lambda name: (0 if name == "Ярославль" else 1, name))
        return localities

    def list_districts(self, locality: str) -> list[str]:
        with self.db.transaction() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT COALESCE(district, '') AS d
                FROM route_points
                WHERE locality = ? AND kind = 'stop'
                """,
                (locality,),
            ).fetchall()
        districts = [str(row["d"]).strip() for row in rows]
        non_empty_districts = [district for district in districts if district]
        if non_empty_districts:
            districts = non_empty_districts

        preferred = list(ROUTE_HIERARCHY.get(locality, {}).keys())
        if not preferred:
            districts.sort()
            return districts

        def sort_key(district: str) -> tuple[int, int, str]:
            if district in preferred:
                return (0, preferred.index(district), district)
            return (1, 0, district)

        districts.sort(key=sort_key)
        return districts

    def list_admin_areas(self, locality: str, district: str) -> list[str]:
        with self.db.transaction() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT COALESCE(admin_area, '') AS a
                FROM route_points
                WHERE locality = ? AND COALESCE(district, '') = ? AND kind = 'stop'
                """,
                (locality, district),
            ).fetchall()
        areas = [str(row["a"]).strip() for row in rows]
        non_empty_areas = [area for area in areas if area]
        if non_empty_areas:
            areas = non_empty_areas

        preferred = list(ROUTE_HIERARCHY.get(locality, {}).get(district, {}).keys())
        if not preferred:
            areas.sort()
            return areas

        def sort_key(area: str) -> tuple[int, int, str]:
            if area in preferred:
                return (0, preferred.index(area), area)
            return (1, 0, area)

        areas.sort(key=sort_key)
        return areas

    def list_stops(self, locality: str, district: str, admin_area: str) -> list[sqlite3.Row]:
        with self.db.transaction() as conn:
            return conn.execute(
                """
                SELECT * FROM route_points
                WHERE locality = ? AND COALESCE(district, '') = ? AND COALESCE(admin_area, '') = ? AND kind = 'stop'
                ORDER BY title
                """,
                (locality, district, admin_area),
            ).fetchall()

    def get_point(self, point_id: int) -> sqlite3.Row | None:
        with self.db.transaction() as conn:
            return conn.execute("SELECT * FROM route_points WHERE id = ?", (point_id,)).fetchone()


class TripRepository(_BaseRepository):
    def create_trip(
        self,
        tg_driver_id: int,
        start_point_id: int,
        end_point_id: int,
        trip_date: str,
        departure_time: str,
        price_rub: int,
        seats_total: int,
    ) -> int:
        with self.db.transaction() as conn:
            driver = conn.execute(
                """
                SELECT u.id
                FROM users u
                INNER JOIN driver_license_verifications d ON d.user_id = u.id
                WHERE u.tg_user_id = ? AND u.role = 'driver'
                  AND date(d.valid_until) >= date(?)
                """,
                (tg_driver_id, trip_date),
            ).fetchone()
            if not driver:
                raise ValueError(
                    "Только водитель с действующей записью о водительском удостоверении может создавать поездку."
                )

            trip_start = self._trip_start_dt(trip_date, departure_time)
            if trip_start is None:
                raise ValueError("Некорректные дата/время поездки.")
            if trip_start <= datetime.now():
                raise ValueError("Нельзя создать поездку на прошедшее время.")

            cur = conn.execute(
                """
                INSERT INTO trips(
                    driver_id, start_point_id, end_point_id, trip_date, departure_time, time_slot, price_rub, seats_total
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    driver["id"],
                    start_point_id,
                    end_point_id,
                    trip_date,
                    departure_time,
                    f"{trip_date} {departure_time}",
                    price_rub,
                    seats_total,
                ),
            )
            return int(cur.lastrowid)

    def find_open_trips(
        self,
        start_point_id: int | None = None,
        end_point_id: int | None = None,
        trip_date: str | None = None,
        departure_time: str | None = None,
    ) -> list[sqlite3.Row]:
        query = """
            SELECT
                t.id,
                t.driver_id,
                t.time_slot,
                t.trip_date,
                t.departure_time,
                t.price_rub,
                t.seats_total,
                t.seats_booked,
                t.status,
                sp.title AS start_title,
                ep.title AS end_title,
                u.name AS driver_name,
                u.rating_avg AS driver_rating
            FROM trips t
            JOIN route_points sp ON sp.id = t.start_point_id
            JOIN route_points ep ON ep.id = t.end_point_id
            JOIN users u ON u.id = t.driver_id
            WHERE t.status = 'open'
        """
        params: list[object] = []
        if start_point_id:
            query += " AND t.start_point_id = ?"
            params.append(start_point_id)
        if end_point_id:
            query += " AND t.end_point_id = ?"
            params.append(end_point_id)
        if trip_date:
            query += " AND t.trip_date = ?"
            params.append(trip_date)
        if departure_time:
            query += " AND t.departure_time = ?"
            params.append(departure_time)
        query += " ORDER BY t.id DESC LIMIT 25"

        with self.db.transaction() as conn:
            return conn.execute(query, tuple(params)).fetchall()

    def list_driver_trips(self, tg_driver_id: int) -> list[sqlite3.Row]:
        with self.db.transaction() as conn:
            driver_id = self._get_internal_user_id(conn, tg_driver_id)
            return conn.execute(
                """
                SELECT
                    t.id,
                    t.trip_date,
                    t.departure_time,
                    t.time_slot,
                    t.price_rub,
                    t.seats_total,
                    t.seats_booked,
                    t.status,
                    sp.title AS start_title,
                    ep.title AS end_title
                FROM trips t
                JOIN route_points sp ON sp.id = t.start_point_id
                JOIN route_points ep ON ep.id = t.end_point_id
                WHERE t.driver_id = ?
                ORDER BY t.id DESC
                """,
                (driver_id,),
            ).fetchall()

    def list_all_trips_for_debug(self) -> list[sqlite3.Row]:
        with self.db.transaction() as conn:
            return conn.execute(
                """
                SELECT
                    t.id,
                    t.trip_date,
                    t.departure_time,
                    t.time_slot,
                    t.price_rub,
                    t.seats_total,
                    t.seats_booked,
                    t.status,
                    sp.title AS start_title,
                    ep.title AS end_title,
                    u.name AS driver_name
                FROM trips t
                JOIN route_points sp ON sp.id = t.start_point_id
                JOIN route_points ep ON ep.id = t.end_point_id
                JOIN users u ON u.id = t.driver_id
                ORDER BY t.id DESC
                """
            ).fetchall()


class BookingRepository(_BaseRepository):
    def create_booking(self, tg_passenger_id: int, trip_id: int) -> int:
        with self.db.transaction() as conn:
            passenger_id = self._get_internal_user_id(conn, tg_passenger_id)
            trip = conn.execute(
                """
                SELECT t.*, d.tg_user_id AS driver_tg_user_id
                FROM trips t
                JOIN users d ON d.id = t.driver_id
                WHERE t.id = ?
                """,
                (trip_id,),
            ).fetchone()
            if not trip:
                raise ValueError("Поездка не найдена.")
            if trip["status"] != "open":
                raise ValueError("Поездка недоступна.")

            trip_start = self._trip_start_dt(trip["trip_date"], trip["departure_time"])
            if trip_start and trip_start <= datetime.now():
                raise ValueError("Нельзя забронировать поездку: время отправления уже прошло.")
            if trip["driver_tg_user_id"] == tg_passenger_id:
                raise ValueError("Нельзя бронировать свою поездку.")
            if trip["seats_booked"] >= trip["seats_total"]:
                raise ValueError("Свободных мест нет.")

            existing = conn.execute(
                "SELECT id, status FROM bookings WHERE trip_id = ? AND passenger_id = ?",
                (trip_id, passenger_id),
            ).fetchone()
            if existing and existing["status"] == "active":
                raise ValueError("Вы уже забронировали эту поездку.")

            if existing and existing["status"] != "active":
                conn.execute(
                    """
                    UPDATE bookings
                    SET status = 'active', cancel_reason = NULL, cancelled_at = NULL, created_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (existing["id"],),
                )
                booking_id = int(existing["id"])
            else:
                cur = conn.execute("INSERT INTO bookings(trip_id, passenger_id) VALUES (?, ?)", (trip_id, passenger_id))
                booking_id = int(cur.lastrowid)

            conn.execute("UPDATE trips SET seats_booked = seats_booked + 1 WHERE id = ?", (trip_id,))
            return booking_id

    def list_passenger_bookings(self, tg_passenger_id: int) -> list[sqlite3.Row]:
        with self.db.transaction() as conn:
            passenger_id = self._get_internal_user_id(conn, tg_passenger_id)
            return conn.execute(
                """
                SELECT
                    b.id,
                    b.status,
                    b.created_at,
                    b.cancel_reason,
                    t.id AS trip_id,
                    t.trip_date,
                    t.departure_time,
                    t.time_slot,
                    t.price_rub,
                    sp.title AS start_title,
                    ep.title AS end_title,
                    u.name AS driver_name
                FROM bookings b
                JOIN trips t ON t.id = b.trip_id
                JOIN route_points sp ON sp.id = t.start_point_id
                JOIN route_points ep ON ep.id = t.end_point_id
                JOIN users u ON u.id = t.driver_id
                WHERE b.passenger_id = ?
                ORDER BY b.id DESC
                """,
                (passenger_id,),
            ).fetchall()

    def get_booking_for_cancel(self, tg_passenger_id: int, booking_id: int) -> sqlite3.Row | None:
        with self.db.transaction() as conn:
            passenger_id = self._get_internal_user_id(conn, tg_passenger_id)
            return conn.execute(
                """
                SELECT
                    b.id,
                    b.status,
                    b.trip_id,
                    t.driver_id,
                    du.tg_user_id AS driver_tg_user_id,
                    sp.title AS start_title,
                    ep.title AS end_title,
                    t.trip_date,
                    t.departure_time,
                    t.time_slot
                FROM bookings b
                JOIN trips t ON t.id = b.trip_id
                JOIN users du ON du.id = t.driver_id
                JOIN route_points sp ON sp.id = t.start_point_id
                JOIN route_points ep ON ep.id = t.end_point_id
                WHERE b.id = ? AND b.passenger_id = ?
                """,
                (booking_id, passenger_id),
            ).fetchone()

    def cancel_booking_by_passenger(
        self,
        tg_passenger_id: int,
        booking_id: int,
        reason: str,
    ) -> tuple[int, dict[str, object]]:
        with self.db.transaction() as conn:
            passenger_id = self._get_internal_user_id(conn, tg_passenger_id)
            booking = conn.execute(
                """
                SELECT
                    b.*,
                    t.id AS trip_id,
                    t.status AS trip_status,
                    t.driver_id,
                    du.tg_user_id AS driver_tg_user_id,
                    sp.title AS start_title,
                    ep.title AS end_title,
                    t.trip_date,
                    t.departure_time,
                    t.time_slot
                FROM bookings b
                JOIN trips t ON t.id = b.trip_id
                JOIN users du ON du.id = t.driver_id
                JOIN route_points sp ON sp.id = t.start_point_id
                JOIN route_points ep ON ep.id = t.end_point_id
                WHERE b.id = ? AND b.passenger_id = ?
                """,
                (booking_id, passenger_id),
            ).fetchone()
            if not booking:
                raise ValueError("Бронь не найдена.")
            if booking["status"] != "active":
                raise ValueError("Бронь уже отменена или завершена.")

            cleaned_reason = reason.strip()
            conn.execute(
                """
                UPDATE bookings
                SET status = 'cancelled_by_passenger',
                    cancel_reason = ?,
                    cancelled_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (cleaned_reason, booking_id),
            )
            conn.execute(
                "UPDATE trips SET seats_booked = CASE WHEN seats_booked > 0 THEN seats_booked - 1 ELSE 0 END WHERE id = ?",
                (booking["trip_id"],),
            )

            payload: dict[str, object] = {
                "driver_tg_user_id": int(booking["driver_tg_user_id"]),
                "trip_id": int(booking["trip_id"]),
                "start_title": booking["start_title"],
                "end_title": booking["end_title"],
                "trip_date": booking["trip_date"],
                "departure_time": booking["departure_time"],
                "time_slot": booking["time_slot"],
                "reason": cleaned_reason,
            }
            return int(booking["trip_id"]), payload


class Repo:
    """Facade for bot handlers; delegates to focused OOP repositories."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.routes = RouteRepository(db)
        self.trips = TripRepository(db)
        self.bookings = BookingRepository(db)
        self.driver_licenses = DriverLicenseRepository(db)

    def upsert_user(self, tg_user_id: int, name: str, username: str | None, role: str) -> None:
        self.users.upsert_user(tg_user_id, name, username, role)

    def register_driver_with_license(
        self,
        tg_user_id: int,
        name: str,
        username: str | None,
        license_series_number: str,
        valid_until: date,
    ) -> None:
        self.driver_licenses.register_driver_with_license(
            tg_user_id, name, username, license_series_number, valid_until
        )

    def get_user(self, tg_user_id: int) -> sqlite3.Row | None:
        return self.users.get_user(tg_user_id)

    def route_points(self) -> list[sqlite3.Row]:
        return self.routes.route_points()

    def list_localities(self) -> list[str]:
        return self.routes.list_localities()

    def list_districts(self, locality: str) -> list[str]:
        return self.routes.list_districts(locality)

    def list_admin_areas(self, locality: str, district: str) -> list[str]:
        return self.routes.list_admin_areas(locality, district)

    def list_stops(self, locality: str, district: str, admin_area: str) -> list[sqlite3.Row]:
        return self.routes.list_stops(locality, district, admin_area)

    def get_point(self, point_id: int) -> sqlite3.Row | None:
        return self.routes.get_point(point_id)

    def create_trip(
        self,
        tg_driver_id: int,
        start_point_id: int,
        end_point_id: int,
        trip_date: str,
        departure_time: str,
        price_rub: int,
        seats_total: int,
    ) -> int:
        return self.trips.create_trip(
            tg_driver_id=tg_driver_id,
            start_point_id=start_point_id,
            end_point_id=end_point_id,
            trip_date=trip_date,
            departure_time=departure_time,
            price_rub=price_rub,
            seats_total=seats_total,
        )

    def find_open_trips(
        self,
        start_point_id: int | None = None,
        end_point_id: int | None = None,
        trip_date: str | None = None,
        departure_time: str | None = None,
    ) -> list[sqlite3.Row]:
        return self.trips.find_open_trips(start_point_id, end_point_id, trip_date, departure_time)

    def create_booking(self, tg_passenger_id: int, trip_id: int) -> int:
        return self.bookings.create_booking(tg_passenger_id, trip_id)

    def list_passenger_bookings(self, tg_passenger_id: int) -> list[sqlite3.Row]:
        return self.bookings.list_passenger_bookings(tg_passenger_id)

    def get_booking_for_cancel(self, tg_passenger_id: int, booking_id: int) -> sqlite3.Row | None:
        return self.bookings.get_booking_for_cancel(tg_passenger_id, booking_id)

    def cancel_booking_by_passenger(
        self,
        tg_passenger_id: int,
        booking_id: int,
        reason: str,
    ) -> tuple[int, dict[str, object]]:
        return self.bookings.cancel_booking_by_passenger(tg_passenger_id, booking_id, reason)

    def list_driver_trips(self, tg_driver_id: int) -> list[sqlite3.Row]:
        return self.trips.list_driver_trips(tg_driver_id)

    def list_all_trips_for_debug(self) -> list[sqlite3.Row]:
        return self.trips.list_all_trips_for_debug()

    def switch_role(self, tg_user_id: int, new_role: str, for_date: str) -> tuple[bool, str]:
        return self.users.switch_role(tg_user_id, new_role, for_date)

    @staticmethod
    def default_date() -> str:
        return date.today().isoformat()

    @staticmethod
    def chunk_rows(rows: Iterable[sqlite3.Row], size: int = 10) -> list[list[sqlite3.Row]]:
        rows_list = list(rows)
        return [rows_list[i : i + size] for i in range(0, len(rows_list), size)]
