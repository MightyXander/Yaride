from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable

from app.db import Database
from app.seeds import ROUTE_HIERARCHY


class _BaseRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

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
    def upsert_user(
        self,
        tg_user_id: int,
        name: str,
        username: str | None,
        role: str,
        *,
        dl_series_number: str | None = None,
        dl_valid_until: str | None = None,
    ) -> None:
        if role == "driver":
            if not dl_series_number or not dl_valid_until:
                raise ValueError("Для роли водителя нужны серия/номер ВУ и срок действия.")
        else:
            dl_series_number = None
            dl_valid_until = None

        with self.db.transaction() as conn:
            row = conn.execute("SELECT id FROM users WHERE tg_user_id = ?", (tg_user_id,)).fetchone()
            try:
                if row:
                    conn.execute(
                        """
                        UPDATE users
                        SET name = ?, username = ?, role = ?, dl_series_number = ?, dl_valid_until = ?
                        WHERE tg_user_id = ?
                        """,
                        (name, username, role, dl_series_number, dl_valid_until, tg_user_id),
                    )
                    return

                conn.execute(
                    """
                    INSERT INTO users(tg_user_id, name, username, role, dl_series_number, dl_valid_until)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (tg_user_id, name, username, role, dl_series_number, dl_valid_until),
                )
            except sqlite3.IntegrityError as exc:
                if "uq_users_dl_series" in str(exc) or "dl_series_number" in str(exc).lower():
                    raise ValueError(
                        "Это водительское удостоверение уже привязано к другому аккаунту."
                    ) from exc
                raise

    def get_user(self, tg_user_id: int) -> sqlite3.Row | None:
        with self.db.transaction() as conn:
            return conn.execute("SELECT * FROM users WHERE tg_user_id = ?", (tg_user_id,)).fetchone()

    def set_driver_min_passenger_rating(self, tg_user_id: int, min_rating: float | None) -> None:
        """Минимальный средний рейтинг пассажира для автоматического принятия брони; None — без ограничения."""
        with self.db.transaction() as conn:
            user = conn.execute(
                "SELECT id, role FROM users WHERE tg_user_id = ?", (tg_user_id,)
            ).fetchone()
            if not user:
                raise ValueError("Пользователь не зарегистрирован.")
            if user["role"] != "driver":
                raise ValueError("Порог рейтинга настраивает только водитель.")
            conn.execute(
                "UPDATE users SET min_passenger_rating = ? WHERE id = ?",
                (min_rating, user["id"]),
            )

    def switch_role(self, tg_user_id: int, new_role: str, for_date: str) -> tuple[bool, str]:
        if new_role not in ("driver", "passenger"):
            return False, "Недопустимая роль."

        with self.db.transaction() as conn:
            user = conn.execute(
                "SELECT id, role, dl_series_number FROM users WHERE tg_user_id = ?", (tg_user_id,)
            ).fetchone()
            if not user:
                return False, "Сначала зарегистрируйся через /start."
            if user["role"] == new_role:
                return False, "У тебя уже выбрана эта роль."

            if new_role == "driver" and not user["dl_series_number"]:
                return (
                    False,
                    "Чтобы стать водителем, сначала укажи данные ВУ при регистрации "
                    "(роль «Водитель» после /start). Смена с пассажира на водителя "
                    "пока доступна только через новую регистрацию водителя.",
                )

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

            if new_role == "passenger":
                conn.execute(
                    "UPDATE users SET role = ?, dl_series_number = NULL, dl_valid_until = NULL WHERE id = ?",
                    (new_role, user["id"]),
                )
            else:
                conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user["id"]))
            return True, "Роль обновлена."


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
                "SELECT id, dl_series_number FROM users WHERE tg_user_id = ? AND role = 'driver'",
                (tg_driver_id,),
            ).fetchone()
            if not driver:
                raise ValueError("Только водитель может создавать поездку.")
            if not driver["dl_series_number"]:
                raise ValueError(
                    "В профиле нет данных действующего ВУ. Пройди регистрацию водителя заново через /start."
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

    def get_trip_public_card(self, trip_id: int) -> sqlite3.Row | None:
        with self.db.transaction() as conn:
            return conn.execute(
                """
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
                WHERE t.id = ?
                """,
                (trip_id,),
            ).fetchone()

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

    def cancel_trip_by_driver(self, tg_driver_id: int, trip_id: int) -> list[int]:
        """Отменяет открытую поездку и активные брони. Возвращает tg_user_id пассажиров для уведомлений."""
        with self.db.transaction() as conn:
            trip = conn.execute(
                """
                SELECT t.id, t.status, u.tg_user_id
                FROM trips t
                JOIN users u ON u.id = t.driver_id
                WHERE t.id = ? AND u.tg_user_id = ?
                """,
                (trip_id, tg_driver_id),
            ).fetchone()
            if not trip:
                raise ValueError("Поездка не найдена.")
            if trip["status"] != "open":
                raise ValueError("Можно отменить только открытую поездку.")

            rows = conn.execute(
                """
                SELECT u.tg_user_id
                FROM bookings b
                JOIN users u ON u.id = b.passenger_id
                WHERE b.trip_id = ? AND b.status = 'active'
                """,
                (trip_id,),
            ).fetchall()
            notify_ids = [int(r["tg_user_id"]) for r in rows]

            conn.execute(
                """
                UPDATE bookings
                SET status = 'cancelled_by_driver',
                    cancel_reason = 'Поездка отменена водителем',
                    cancelled_at = CURRENT_TIMESTAMP
                WHERE trip_id = ? AND status = 'active'
                """,
                (trip_id,),
            )
            conn.execute(
                "UPDATE trips SET status = 'cancelled', seats_booked = 0 WHERE id = ?",
                (trip_id,),
            )
            return notify_ids


class BookingRepository(_BaseRepository):
    def create_booking(self, tg_passenger_id: int, trip_id: int) -> int:
        with self.db.transaction() as conn:
            passenger_id = self._get_internal_user_id(conn, tg_passenger_id)
            trip = conn.execute(
                """
                SELECT t.*, d.tg_user_id AS driver_tg_user_id, d.min_passenger_rating AS driver_min_rating
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

            passenger = conn.execute(
                "SELECT rating_avg, rating_count FROM users WHERE id = ?",
                (passenger_id,),
            ).fetchone()
            if passenger is None:
                raise ValueError("Профиль пассажира не найден.")
            min_r = trip["driver_min_rating"]
            if min_r is not None and float(min_r) > 0:
                rc = int(passenger["rating_count"] or 0)
                ra = float(passenger["rating_avg"] or 0.0)
                if rc >= 1 and ra + 1e-9 < float(min_r):
                    raise ValueError(
                        f"Водитель принимает пассажиров с рейтингом не ниже {float(min_r):.1f}. "
                        f"У тебя {ra:.1f} (оценок: {rc})."
                    )

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

    def list_bookings_for_driver_trip(self, tg_driver_id: int, trip_id: int) -> list[sqlite3.Row]:
        with self.db.transaction() as conn:
            return conn.execute(
                """
                SELECT
                    b.id AS booking_id,
                    b.status,
                    p.name AS passenger_name,
                    p.tg_user_id AS passenger_tg_user_id,
                    p.rating_avg,
                    p.rating_count
                FROM bookings b
                JOIN trips t ON t.id = b.trip_id
                JOIN users dr ON dr.id = t.driver_id
                JOIN users p ON p.id = b.passenger_id
                WHERE t.id = ? AND dr.tg_user_id = ? AND b.status = 'active'
                ORDER BY b.id
                """,
                (trip_id, tg_driver_id),
            ).fetchall()

    def reject_booking_by_driver(self, tg_driver_id: int, booking_id: int) -> dict[str, object]:
        with self.db.transaction() as conn:
            booking = conn.execute(
                """
                SELECT
                    b.id,
                    b.trip_id,
                    b.status,
                    p.tg_user_id AS passenger_tg_user_id,
                    sp.title AS start_title,
                    ep.title AS end_title,
                    t.trip_date,
                    t.departure_time,
                    t.time_slot
                FROM bookings b
                JOIN trips t ON t.id = b.trip_id
                JOIN users dr ON dr.id = t.driver_id
                JOIN users p ON p.id = b.passenger_id
                JOIN route_points sp ON sp.id = t.start_point_id
                JOIN route_points ep ON ep.id = t.end_point_id
                WHERE b.id = ? AND dr.tg_user_id = ?
                """,
                (booking_id, tg_driver_id),
            ).fetchone()
            if not booking:
                raise ValueError("Бронь не найдена или нет доступа.")
            if booking["status"] != "active":
                raise ValueError("Бронь уже не активна.")

            conn.execute(
                """
                UPDATE bookings
                SET status = 'cancelled_by_driver',
                    cancel_reason = 'Отклонено водителем',
                    cancelled_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (booking_id,),
            )
            conn.execute(
                """
                UPDATE trips
                SET seats_booked = CASE WHEN seats_booked > 0 THEN seats_booked - 1 ELSE 0 END
                WHERE id = ?
                """,
                (booking["trip_id"],),
            )
            return {
                "passenger_tg_user_id": int(booking["passenger_tg_user_id"]),
                "trip_id": int(booking["trip_id"]),
                "start_title": booking["start_title"],
                "end_title": booking["end_title"],
                "trip_date": booking["trip_date"],
                "departure_time": booking["departure_time"],
                "time_slot": booking["time_slot"],
            }


@dataclass(frozen=True)
class PendingRatingPrompt:
    trip_id: int
    rater_user_id: int
    rated_user_id: int
    rater_tg_user_id: int
    rated_tg_user_id: int
    rated_name: str
    prompt_text: str


class FavoriteRouteRepository(_BaseRepository):
    def add_favorite_route(self, tg_user_id: int, start_point_id: int, end_point_id: int) -> bool:
        """True если добавлено, False если маршрут уже был в избранном."""
        with self.db.transaction() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO favorite_routes(tg_user_id, start_point_id, end_point_id)
                    VALUES (?, ?, ?)
                    """,
                    (tg_user_id, start_point_id, end_point_id),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def add_favorite_from_trip(self, tg_user_id: int, trip_id: int) -> bool:
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT start_point_id, end_point_id FROM trips WHERE id = ?",
                (trip_id,),
            ).fetchone()
            if not row:
                raise ValueError("Поездка не найдена.")
            try:
                conn.execute(
                    """
                    INSERT INTO favorite_routes(tg_user_id, start_point_id, end_point_id)
                    VALUES (?, ?, ?)
                    """,
                    (tg_user_id, int(row["start_point_id"]), int(row["end_point_id"])),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def list_favorites(self, tg_user_id: int) -> list[sqlite3.Row]:
        with self.db.transaction() as conn:
            return conn.execute(
                """
                SELECT f.id, f.start_point_id, f.end_point_id,
                       sp.title AS start_title, ep.title AS end_title
                FROM favorite_routes f
                JOIN route_points sp ON sp.id = f.start_point_id
                JOIN route_points ep ON ep.id = f.end_point_id
                WHERE f.tg_user_id = ?
                ORDER BY f.id DESC
                """,
                (tg_user_id,),
            ).fetchall()

    def get_favorite_owned(self, tg_user_id: int, favorite_id: int) -> sqlite3.Row | None:
        with self.db.transaction() as conn:
            return conn.execute(
                """
                SELECT f.id, f.start_point_id, f.end_point_id,
                       sp.title AS start_title, ep.title AS end_title
                FROM favorite_routes f
                JOIN route_points sp ON sp.id = f.start_point_id
                JOIN route_points ep ON ep.id = f.end_point_id
                WHERE f.id = ? AND f.tg_user_id = ?
                """,
                (favorite_id, tg_user_id),
            ).fetchone()


class RatingRepository(_BaseRepository):
    def _refresh_user_rating(self, conn: sqlite3.Connection, rated_user_id: int) -> None:
        row = conn.execute(
            "SELECT AVG(stars) AS a, COUNT(*) AS c FROM trip_ratings WHERE rated_user_id = ?",
            (rated_user_id,),
        ).fetchone()
        avg = float(row["a"] or 0.0)
        cnt = int(row["c"] or 0)
        conn.execute(
            "UPDATE users SET rating_avg = ?, rating_count = ? WHERE id = ?",
            (avg, cnt, rated_user_id),
        )

    def submit_rating(
        self,
        rater_tg_user_id: int,
        trip_id: int,
        rated_tg_user_id: int,
        stars: int,
        *,
        review_text: str | None = None,
    ) -> None:
        if stars < 1 or stars > 5:
            raise ValueError("Оценка от 1 до 5.")
        with self.db.transaction() as conn:
            rater_id = self._get_internal_user_id(conn, rater_tg_user_id)
            rated_row = conn.execute("SELECT id FROM users WHERE tg_user_id = ?", (rated_tg_user_id,)).fetchone()
            if not rated_row:
                raise ValueError("Пользователь не найден.")
            rated_id = int(rated_row["id"])

            trip = conn.execute(
                """
                SELECT t.driver_id, t.status, t.trip_date, t.departure_time
                FROM trips t WHERE t.id = ?
                """,
                (trip_id,),
            ).fetchone()
            if not trip:
                raise ValueError("Поездка не найдена.")
            if trip["status"] == "cancelled":
                raise ValueError("Поездка отменена, оценка недоступна.")

            trip_dt = self._trip_start_dt(trip["trip_date"], trip["departure_time"])
            if trip_dt is None:
                raise ValueError("Некорректные дата или время поездки.")
            if datetime.now() < trip_dt + timedelta(hours=3):
                raise ValueError("Оценку можно поставить не раньше чем через 3 часа после времени отправления.")

            driver_id = int(trip["driver_id"])

            bookings = conn.execute(
                """
                SELECT b.passenger_id
                FROM bookings b
                WHERE b.trip_id = ? AND b.status = 'active'
                """,
                (trip_id,),
            ).fetchall()
            passenger_ids = {int(r["passenger_id"]) for r in bookings}

            valid_pair = False
            if rater_id == driver_id and rated_id in passenger_ids:
                valid_pair = True
            elif rated_id == driver_id and rater_id in passenger_ids:
                valid_pair = True

            if not valid_pair:
                raise ValueError("Оценку может ставить только участник этой поездки.")

            try:
                conn.execute(
                    """
                    INSERT INTO trip_ratings(trip_id, rater_user_id, rated_user_id, stars, review_text)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (trip_id, rater_id, rated_id, stars, review_text),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("Эта оценка уже была сохранена.") from exc
            self._refresh_user_rating(conn, rated_id)

    def list_ratings_received(self, tg_user_id: int) -> list[sqlite3.Row]:
        """Оценки, которые получил пользователь (имя оценившего, звёзды, поездка)."""
        with self.db.transaction() as conn:
            uid = self._get_internal_user_id(conn, tg_user_id)
            return conn.execute(
                """
                SELECT tr.stars, tr.created_at, tr.trip_id, tr.review_text,
                       rater.name AS rater_name,
                       t.trip_date, t.departure_time
                FROM trip_ratings tr
                JOIN users rater ON rater.id = tr.rater_user_id
                JOIN trips t ON t.id = tr.trip_id
                WHERE tr.rated_user_id = ?
                ORDER BY tr.id DESC
                LIMIT 40
                """,
                (uid,),
            ).fetchall()

    def mark_rating_prompt_sent(self, trip_id: int, rater_user_id: int, rated_user_id: int) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO rating_prompts_sent(trip_id, rater_user_id, rated_user_id)
                VALUES (?, ?, ?)
                """,
                (trip_id, rater_user_id, rated_user_id),
            )

    def list_pending_rating_prompts(self, now: datetime | None = None) -> list[PendingRatingPrompt]:
        """Поездки с активной бронью: время отправления + 3 ч уже прошло, оценки ещё нет, напоминание не отправляли."""
        now = now or datetime.now()
        out: list[PendingRatingPrompt] = []
        with self.db.transaction() as conn:
            trips = conn.execute(
                """
                SELECT t.id, t.trip_date, t.departure_time, t.driver_id, t.status,
                       dr.tg_user_id AS driver_tg, dr.name AS driver_name
                FROM trips t
                JOIN users dr ON dr.id = t.driver_id
                WHERE t.status != 'cancelled'
                """,
            ).fetchall()

            for t in trips:
                trip_id = int(t["id"])
                trip_dt = self._trip_start_dt(t["trip_date"], t["departure_time"])
                if trip_dt is None:
                    continue
                if now < trip_dt + timedelta(hours=3):
                    continue

                driver_id = int(t["driver_id"])
                driver_tg = int(t["driver_tg"])
                driver_name = str(t["driver_name"] or "")

                bookings = conn.execute(
                    """
                    SELECT b.passenger_id, p.tg_user_id AS passenger_tg, p.name AS passenger_name
                    FROM bookings b
                    JOIN users p ON p.id = b.passenger_id
                    WHERE b.trip_id = ? AND b.status = 'active'
                    """,
                    (trip_id,),
                ).fetchall()

                for b in bookings:
                    passenger_id = int(b["passenger_id"])
                    passenger_tg = int(b["passenger_tg"])
                    passenger_name = str(b["passenger_name"] or "")

                    has_p2d = conn.execute(
                        """
                        SELECT 1 FROM trip_ratings
                        WHERE trip_id = ? AND rater_user_id = ? AND rated_user_id = ?
                        """,
                        (trip_id, passenger_id, driver_id),
                    ).fetchone()
                    sent_p2d = conn.execute(
                        """
                        SELECT 1 FROM rating_prompts_sent
                        WHERE trip_id = ? AND rater_user_id = ? AND rated_user_id = ?
                        """,
                        (trip_id, passenger_id, driver_id),
                    ).fetchone()
                    if not has_p2d and not sent_p2d:
                        out.append(
                            PendingRatingPrompt(
                                trip_id=trip_id,
                                rater_user_id=passenger_id,
                                rated_user_id=driver_id,
                                rater_tg_user_id=passenger_tg,
                                rated_tg_user_id=driver_tg,
                                rated_name=driver_name,
                                prompt_text=(
                                    f"Поездка #{trip_id} состоялась. Оцените водителя «{driver_name}» "
                                    f"(от 1 до 5):"
                                ),
                            )
                        )

                    has_d2p = conn.execute(
                        """
                        SELECT 1 FROM trip_ratings
                        WHERE trip_id = ? AND rater_user_id = ? AND rated_user_id = ?
                        """,
                        (trip_id, driver_id, passenger_id),
                    ).fetchone()
                    sent_d2p = conn.execute(
                        """
                        SELECT 1 FROM rating_prompts_sent
                        WHERE trip_id = ? AND rater_user_id = ? AND rated_user_id = ?
                        """,
                        (trip_id, driver_id, passenger_id),
                    ).fetchone()
                    if not has_d2p and not sent_d2p:
                        out.append(
                            PendingRatingPrompt(
                                trip_id=trip_id,
                                rater_user_id=driver_id,
                                rated_user_id=passenger_id,
                                rater_tg_user_id=driver_tg,
                                rated_tg_user_id=passenger_tg,
                                rated_name=passenger_name,
                                prompt_text=(
                                    f"Поездка #{trip_id}. Оцените пассажира «{passenger_name}» "
                                    f"(от 1 до 5):"
                                ),
                            )
                        )

        return out


class Repo:
    """Facade for bot handlers; delegates to focused OOP repositories."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.routes = RouteRepository(db)
        self.trips = TripRepository(db)
        self.bookings = BookingRepository(db)
        self.favorites = FavoriteRouteRepository(db)
        self.ratings = RatingRepository(db)

    def upsert_user(
        self,
        tg_user_id: int,
        name: str,
        username: str | None,
        role: str,
        *,
        dl_series_number: str | None = None,
        dl_valid_until: str | None = None,
    ) -> None:
        self.users.upsert_user(
            tg_user_id,
            name,
            username,
            role,
            dl_series_number=dl_series_number,
            dl_valid_until=dl_valid_until,
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

    def get_trip_public_card(self, trip_id: int) -> sqlite3.Row | None:
        return self.trips.get_trip_public_card(trip_id)

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

    def set_driver_min_passenger_rating(self, tg_user_id: int, min_rating: float | None) -> None:
        self.users.set_driver_min_passenger_rating(tg_user_id, min_rating)

    def list_bookings_for_driver_trip(self, tg_driver_id: int, trip_id: int) -> list[sqlite3.Row]:
        return self.bookings.list_bookings_for_driver_trip(tg_driver_id, trip_id)

    def reject_booking_by_driver(self, tg_driver_id: int, booking_id: int) -> dict[str, object]:
        return self.bookings.reject_booking_by_driver(tg_driver_id, booking_id)

    def cancel_trip_by_driver(self, tg_driver_id: int, trip_id: int) -> list[int]:
        return self.trips.cancel_trip_by_driver(tg_driver_id, trip_id)

    def list_driver_trips(self, tg_driver_id: int) -> list[sqlite3.Row]:
        return self.trips.list_driver_trips(tg_driver_id)

    def switch_role(self, tg_user_id: int, new_role: str, for_date: str) -> tuple[bool, str]:
        return self.users.switch_role(tg_user_id, new_role, for_date)

    def add_favorite_from_trip(self, tg_user_id: int, trip_id: int) -> bool:
        return self.favorites.add_favorite_from_trip(tg_user_id, trip_id)

    def list_favorite_routes(self, tg_user_id: int) -> list[sqlite3.Row]:
        return self.favorites.list_favorites(tg_user_id)

    def get_favorite_route_owned(self, tg_user_id: int, favorite_id: int) -> sqlite3.Row | None:
        return self.favorites.get_favorite_owned(tg_user_id, favorite_id)

    def submit_trip_rating(
        self,
        rater_tg_user_id: int,
        trip_id: int,
        rated_tg_user_id: int,
        stars: int,
        *,
        review_text: str | None = None,
    ) -> None:
        self.ratings.submit_rating(
            rater_tg_user_id,
            trip_id,
            rated_tg_user_id,
            stars,
            review_text=review_text,
        )

    def list_ratings_received(self, tg_user_id: int) -> list[sqlite3.Row]:
        return self.ratings.list_ratings_received(tg_user_id)

    def list_pending_rating_prompts(self, now: datetime | None = None) -> list[PendingRatingPrompt]:
        return self.ratings.list_pending_rating_prompts(now)

    def mark_rating_prompt_sent(self, trip_id: int, rater_user_id: int, rated_user_id: int) -> None:
        self.ratings.mark_rating_prompt_sent(trip_id, rater_user_id, rated_user_id)

    @staticmethod
    def default_date() -> str:
        return date.today().isoformat()

    @staticmethod
    def chunk_rows(rows: Iterable[sqlite3.Row], size: int = 10) -> list[list[sqlite3.Row]]:
        rows_list = list(rows)
        return [rows_list[i : i + size] for i in range(0, len(rows_list), size)]
