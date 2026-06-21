"""Репозитории данных: пользователи, маршруты, поездки, брони, избранное, рейтинги.

Все репозитории — тонкий слой над SQLite: бизнес-правила (проверка мест, порог рейтинга,
запрет самобронирования) живут здесь, а не в хендлерах, чтобы их можно было проверить
без Telegram-контекста.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.analytics import (
    EVENT_BOOKING_CANCELLED,
    EVENT_BOOKING_CREATED,
    EVENT_SEARCH,
    EVENT_TRIP_CREATED,
    record_event,
)
from app.database import DbHandle, is_unique_violation
from app.driver_access import (
    DRIVER_MOD_APPROVED,
    DRIVER_MOD_PENDING,
    DRIVER_MOD_REJECTED,
    driver_moderation_status,
    is_approved_driver,
)
from app.formatting import effective_min_passenger_rating
from app.geo_stops import haversine_km
from app.seeds import ROUTE_HIERARCHY

logger = logging.getLogger(__name__)


class _BaseRepository:
    def __init__(self, db: DbHandle) -> None:
        self.db = db

    @property
    def _dialect(self):
        return self.db.dialect

    @staticmethod
    def _trip_start_dt(trip_date: str | None, departure_time: str | None) -> datetime | None:
        """Строки из БД → datetime для сравнения с «сейчас»; None если данные отсутствуют или некорректны."""
        if not trip_date or not departure_time:
            return None
        try:
            return datetime.strptime(f"{trip_date.strip()} {departure_time.strip()}", "%Y-%m-%d %H:%M")
        except ValueError:
            return None

    @staticmethod
    def _get_internal_user_id(conn: sqlite3.Connection, tg_user_id: int) -> int:
        """Получить внутренний id пользователя в рамках открытой транзакции; исключение если не зарегистрирован."""
        row = conn.execute("SELECT id FROM users WHERE tg_user_id = ?", (tg_user_id,)).fetchone()
        if not row:
            raise ValueError("Пользователь не зарегистрирован.")
        return int(row["id"])


class UserRepository(_BaseRepository):
    @staticmethod
    def _driver_moderation_for_upsert(
        existing: sqlite3.Row | None,
        role: str,
    ) -> str:
        if role != "driver":
            return DRIVER_MOD_APPROVED
        if existing is None:
            return DRIVER_MOD_PENDING
        prev_role = existing["role"]
        prev_status = (
            existing["driver_moderation_status"]
            if "driver_moderation_status" in existing.keys()
            else DRIVER_MOD_APPROVED
        )
        if prev_role != "driver" or prev_status == DRIVER_MOD_REJECTED:
            return DRIVER_MOD_PENDING
        if prev_status == DRIVER_MOD_APPROVED:
            return DRIVER_MOD_APPROVED
        return DRIVER_MOD_PENDING

    def is_active_driver(self, tg_user_id: int) -> bool:
        return is_approved_driver(self.get_user(tg_user_id))

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
            existing = conn.execute("SELECT * FROM users WHERE tg_user_id = ?", (tg_user_id,)).fetchone()
            moderation_status = self._driver_moderation_for_upsert(existing, role)
            try:
                if existing:
                    conn.execute(
                        """
                        UPDATE users
                        SET name = ?, username = ?, role = ?, dl_series_number = ?, dl_valid_until = ?,
                            driver_moderation_status = ?
                        WHERE tg_user_id = ?
                        """,
                        (
                            name,
                            username,
                            role,
                            dl_series_number,
                            dl_valid_until,
                            moderation_status,
                            tg_user_id,
                        ),
                    )
                    return

                conn.execute(
                    """
                    INSERT INTO users(
                        tg_user_id, name, username, role, dl_series_number, dl_valid_until,
                        driver_moderation_status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tg_user_id,
                        name,
                        username,
                        role,
                        dl_series_number,
                        dl_valid_until,
                        moderation_status,
                    ),
                )
            except Exception as exc:
                if is_unique_violation(exc) and (
                    "uq_users_dl_series" in str(exc) or "dl_series_number" in str(exc).lower()
                ):
                    raise ValueError("Это водительское удостоверение уже привязано к другому аккаунту.") from exc
                raise

    def update_car(
        self,
        tg_user_id: int,
        *,
        car_model: str | None,
        car_color: str | None,
        car_plate: str | None,
    ) -> None:
        """Сохранить данные автомобиля водителя (поля под Mini App; схема v8)."""
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE users SET car_model = ?, car_color = ?, car_plate = ? WHERE tg_user_id = ?",
                (car_model, car_color, car_plate, tg_user_id),
            )

    def get_user(self, tg_user_id: int) -> sqlite3.Row | None:
        with self.db.transaction() as conn:
            return conn.execute("SELECT * FROM users WHERE tg_user_id = ?", (tg_user_id,)).fetchone()

    def list_all_tg_user_ids(self) -> list[int]:
        with self.db.transaction() as conn:
            rows = conn.execute("SELECT tg_user_id FROM users ORDER BY id").fetchall()
        return [int(r["tg_user_id"]) for r in rows]

    def get_user_by_id(self, user_id: int) -> sqlite3.Row | None:
        """Поиск по внутреннему id (админка работает с id строки, а не с tg_user_id)."""
        with self.db.transaction() as conn:
            return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def list_all_users(
        self,
        *,
        query: str | None = None,
        role: str | None = None,
        driver_moderation_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        """Список пользователей для админки с поиском по имени/username/tg_id и фильтром по роли."""
        sql = "SELECT * FROM users WHERE 1=1"
        params: list[object] = []
        if query:
            like = f"%{query.strip()}%"
            sql += " AND (name LIKE ? OR COALESCE(username,'') LIKE ? OR CAST(tg_user_id AS TEXT) LIKE ?)"
            params.extend([like, like, like])
        if role:
            sql += " AND role = ?"
            params.append(role)
        if driver_moderation_status:
            sql += " AND driver_moderation_status = ?"
            params.append(driver_moderation_status)
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self.db.transaction() as conn:
            return conn.execute(sql, tuple(params)).fetchall()

    def count_pending_drivers(self) -> int:
        with self.db.transaction() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c FROM users
                WHERE role = 'driver' AND driver_moderation_status = ?
                """,
                (DRIVER_MOD_PENDING,),
            ).fetchone()
            return int(row["c"])

    def approve_driver(self, user_id: int) -> int:
        """Одобрить заявку водителя. Возвращает tg_user_id для уведомления."""
        with self.db.transaction() as conn:
            user = conn.execute(
                "SELECT id, tg_user_id, role, dl_series_number FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if not user:
                raise ValueError("Пользователь не найден.")
            if user["role"] != "driver":
                raise ValueError("Одобрение доступно только для роли водителя.")
            if not user["dl_series_number"]:
                raise ValueError("Нельзя одобрить водителя без данных ВУ.")
            conn.execute(
                "UPDATE users SET driver_moderation_status = ? WHERE id = ?",
                (DRIVER_MOD_APPROVED, user_id),
            )
            return int(user["tg_user_id"])

    def reject_driver(self, user_id: int) -> int:
        """Отклонить заявку водителя. Возвращает tg_user_id для уведомления."""
        with self.db.transaction() as conn:
            user = conn.execute("SELECT id, tg_user_id, role FROM users WHERE id = ?", (user_id,)).fetchone()
            if not user:
                raise ValueError("Пользователь не найден.")
            if user["role"] != "driver":
                raise ValueError("Отклонение доступно только для роли водителя.")
            conn.execute(
                "UPDATE users SET driver_moderation_status = ? WHERE id = ?",
                (DRIVER_MOD_REJECTED, user_id),
            )
            return int(user["tg_user_id"])

    def count_users(self) -> int:
        with self.db.transaction() as conn:
            return int(conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"])

    def admin_update_user(
        self,
        user_id: int,
        *,
        name: str,
        role: str,
        min_passenger_rating: float | None,
        dl_series_number: str | None = None,
        dl_valid_until: str | None = None,
        car_model: str | None = None,
        car_color: str | None = None,
        car_plate: str | None = None,
    ) -> None:
        """Админ-правка профиля. Роль водителя требует данных ВУ в форме или в уже сохранённом профиле."""
        if role not in ("driver", "passenger"):
            raise ValueError("Недопустимая роль.")
        if not name.strip():
            raise ValueError("Имя не может быть пустым.")
        with self.db.transaction() as conn:
            user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if not user:
                raise ValueError("Пользователь не найден.")

            dl_series = (dl_series_number or "").strip() or user["dl_series_number"]
            dl_valid = (dl_valid_until or "").strip() or user["dl_valid_until"]
            car_model_val = (car_model or "").strip() or None
            car_color_val = (car_color or "").strip() or None
            car_plate_val = (car_plate or "").strip() or None
            if role == "passenger":
                dl_series = None
                dl_valid = None
                car_model_val = None
                car_color_val = None
                car_plate_val = None
                moderation_status = DRIVER_MOD_APPROVED
            else:
                if not dl_series or not dl_valid:
                    raise ValueError("Для роли водителя укажите серию/номер ВУ и срок действия.")
                moderation_status = DRIVER_MOD_APPROVED

            try:
                conn.execute(
                    """
                    UPDATE users
                    SET name = ?, role = ?, min_passenger_rating = ?, driver_moderation_status = ?,
                        dl_series_number = ?, dl_valid_until = ?,
                        car_model = ?, car_color = ?, car_plate = ?
                    WHERE id = ?
                    """,
                    (
                        name.strip(),
                        role,
                        min_passenger_rating,
                        moderation_status,
                        dl_series,
                        dl_valid,
                        car_model_val,
                        car_color_val,
                        car_plate_val,
                        user_id,
                    ),
                )
            except Exception as exc:
                if is_unique_violation(exc) and (
                    "uq_users_dl_series" in str(exc) or "dl_series_number" in str(exc).lower()
                ):
                    raise ValueError("Это водительское удостоверение уже привязано к другому аккаунту.") from exc
                raise

    def set_banned(self, user_id: int, banned: bool) -> int:
        """Мягкая блокировка/разблокировка. Возвращает tg_user_id для уведомления."""
        with self.db.transaction() as conn:
            user = conn.execute("SELECT tg_user_id FROM users WHERE id = ?", (user_id,)).fetchone()
            if not user:
                raise ValueError("Пользователь не найден.")
            conn.execute("UPDATE users SET is_banned = ? WHERE id = ?", (1 if banned else 0, user_id))
            return int(user["tg_user_id"])

    def is_banned(self, tg_user_id: int) -> bool:
        """Проверка бана по tg_user_id (для бота). Отсутствие колонки/строки трактуем как «не забанен»."""
        with self.db.transaction() as conn:
            row = conn.execute("SELECT is_banned FROM users WHERE tg_user_id = ?", (tg_user_id,)).fetchone()
        if not row:
            return False
        keys = row.keys()
        return "is_banned" in keys and bool(row["is_banned"])

    def set_driver_min_passenger_rating(self, tg_user_id: int, min_rating: float | None) -> None:
        """Минимальный средний рейтинг пассажира для автоматического принятия брони; None — без ограничения."""
        with self.db.transaction() as conn:
            user = conn.execute("SELECT * FROM users WHERE tg_user_id = ?", (tg_user_id,)).fetchone()
            if not user:
                raise ValueError("Пользователь не зарегистрирован.")
            if not is_approved_driver(user):
                raise ValueError("Порог рейтинга настраивает только одобренный водитель.")
            normalized = effective_min_passenger_rating(min_rating)
            conn.execute(
                "UPDATE users SET min_passenger_rating = ? WHERE id = ?",
                (normalized, user["id"]),
            )

    def switch_role(self, tg_user_id: int, new_role: str, for_date: str) -> tuple[bool, str]:
        """Сменить роль пользователя. Роль можно менять в любой момент, независимо от активных поездок."""
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

            if new_role == "passenger":
                conn.execute(
                    """
                    UPDATE users
                    SET role = ?, dl_series_number = NULL, dl_valid_until = NULL,
                        driver_moderation_status = ?
                    WHERE id = ?
                    """,
                    (new_role, DRIVER_MOD_APPROVED, user["id"]),
                )
            else:
                conn.execute(
                    "UPDATE users SET role = ?, driver_moderation_status = ? WHERE id = ?",
                    (new_role, DRIVER_MOD_PENDING, user["id"]),
                )
            return True, "Роль обновлена. Заявка водителя отправлена на модерацию."


class RouteRepository(_BaseRepository):
    def route_points(self) -> list[sqlite3.Row]:
        with self.db.transaction() as conn:
            return conn.execute("SELECT * FROM route_points ORDER BY locality, district, title").fetchall()

    def list_points_admin(
        self,
        *,
        query: str | None = None,
        limit: int = 500,
    ) -> list[sqlite3.Row]:
        """Список остановок для админки с поиском по id/названию/району."""
        sql = "SELECT * FROM route_points WHERE kind = 'stop'"
        params: list[object] = []
        if query:
            like = f"%{query.strip()}%"
            sql += " AND (title LIKE ? OR COALESCE(district,'') LIKE ? OR COALESCE(admin_area,'') LIKE ? OR CAST(id AS TEXT) LIKE ?)"
            params.extend([like, like, like, like])
        sql += " ORDER BY locality, district, title LIMIT ?"
        params.append(limit)
        with self.db.transaction() as conn:
            return conn.execute(sql, tuple(params)).fetchall()

    def list_localities(self) -> list[str]:
        """Ярославль всегда первым — это основной город маршрутов."""
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
        """Порядок районов берётся из ROUTE_HIERARCHY, а не из алфавита — чтобы совпадал с привычным разбиением города."""
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
        """Аналогично list_districts: приоритет ROUTE_HIERARCHY, затем алфавитный порядок."""
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

    def list_all_stops_with_coords(self, locality: str) -> list[sqlite3.Row]:
        """Все остановки города с координатами — для отрисовки на карте Mini App.

        Точки без координат отбрасываем: на карте их не показать.
        """
        with self.db.transaction() as conn:
            return conn.execute(
                """
                SELECT id, title, COALESCE(district, '') AS district, COALESCE(admin_area, '') AS admin_area,
                       latitude, longitude
                FROM route_points
                WHERE locality = ? AND kind = 'stop'
                  AND latitude IS NOT NULL AND longitude IS NOT NULL
                ORDER BY title
                """,
                (locality,),
            ).fetchall()

    def get_point(self, point_id: int) -> sqlite3.Row | None:
        with self.db.transaction() as conn:
            return conn.execute("SELECT * FROM route_points WHERE id = ?", (point_id,)).fetchone()

    def admin_create_point(
        self,
        *,
        locality: str,
        district: str,
        admin_area: str,
        title: str,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> int:
        """Создать точку маршрута (kind='stop')."""
        if not locality.strip() or not title.strip():
            raise ValueError("Населённый пункт и название остановки обязательны.")
        with self.db.transaction() as conn:
            return self.db.insert_returning_id(
                conn,
                """
                INSERT INTO route_points(locality, district, admin_area, title, kind, latitude, longitude)
                VALUES (?, ?, ?, ?, 'stop', ?, ?)
                """,
                (locality.strip(), district.strip(), admin_area.strip(), title.strip(), latitude, longitude),
            )

    def admin_update_point(
        self,
        point_id: int,
        *,
        locality: str,
        district: str,
        admin_area: str,
        title: str,
        latitude: float | None,
        longitude: float | None,
    ) -> None:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT id FROM route_points WHERE id = ?", (point_id,)).fetchone()
            if not row:
                raise ValueError("Точка маршрута не найдена.")
            conn.execute(
                """
                UPDATE route_points
                SET locality = ?, district = ?, admin_area = ?, title = ?, latitude = ?, longitude = ?
                WHERE id = ?
                """,
                (locality.strip(), district.strip(), admin_area.strip(), title.strip(), latitude, longitude, point_id),
            )

    def admin_patch_point_coordinates(self, point_id: int, *, latitude: float, longitude: float) -> None:
        """Обновить только координаты остановки (drag-and-drop на карте админки)."""
        if not (57.0 <= latitude <= 58.5 and 38.5 <= longitude <= 41.0):
            raise ValueError("Координаты вне области Ярославля.")
        with self.db.transaction() as conn:
            row = conn.execute("SELECT id FROM route_points WHERE id = ?", (point_id,)).fetchone()
            if not row:
                raise ValueError("Точка маршрута не найдена.")
            conn.execute(
                "UPDATE route_points SET latitude = ?, longitude = ? WHERE id = ?",
                (round(latitude, 6), round(longitude, 6), point_id),
            )

    def admin_delete_point(self, point_id: int) -> None:
        """Удалить точку. Запрещено, если на неё ссылаются поездки (целостность FK)."""
        with self.db.transaction() as conn:
            row = conn.execute("SELECT id FROM route_points WHERE id = ?", (point_id,)).fetchone()
            if not row:
                raise ValueError("Точка маршрута не найдена.")
            refs = conn.execute(
                "SELECT COUNT(*) AS c FROM trips WHERE start_point_id = ? OR end_point_id = ?",
                (point_id, point_id),
            ).fetchone()
            if int(refs["c"]) > 0:
                raise ValueError("Нельзя удалить: на точку ссылаются поездки.")
            conn.execute(
                "DELETE FROM favorite_routes WHERE start_point_id = ? OR end_point_id = ?", (point_id, point_id)
            )
            conn.execute("DELETE FROM route_points WHERE id = ?", (point_id,))

    def nearest_stops_ranked(
        self,
        lat: float,
        lng: float,
        candidates: list[sqlite3.Row],
        *,
        limit: int = 5,
    ) -> list[tuple[sqlite3.Row, float]]:
        scored: list[tuple[sqlite3.Row, float]] = []
        for r in candidates:
            la, ln = r["latitude"], r["longitude"]
            if la is None or ln is None:
                continue
            d = haversine_km(lat, lng, float(la), float(ln))
            scored.append((r, d))
        scored.sort(key=lambda x: x[1])
        return scored[:limit]

    def nearest_locality_from_geo(
        self,
        lat: float,
        lng: float,
        *,
        max_km: float = 150.0,
    ) -> tuple[str, float] | None:
        """Возвращает ближайший населённый пункт к геопозиции пользователя и расстояние до него.

        max_km ограничивает поиск — за пределами разумного радиуса маршрут не имеет смысла.
        """
        with self.db.transaction() as conn:
            rows = conn.execute(
                """
                SELECT locality, latitude, longitude FROM route_points
                WHERE kind = 'stop' AND latitude IS NOT NULL AND longitude IS NOT NULL
                """
            ).fetchall()
        best_loc: str | None = None
        best_d: float | None = None
        for r in rows:
            d = haversine_km(lat, lng, float(r["latitude"]), float(r["longitude"]))
            if best_d is None or d < best_d:
                best_d = d
                best_loc = str(r["locality"])
        if best_loc is None or best_d is None or best_d > max_km:
            return None
        return best_loc, best_d

    def nearest_stops_global(
        self,
        lat: float,
        lng: float,
        *,
        limit: int = 5,
        max_km: float = 80.0,
    ) -> list[tuple[sqlite3.Row, float]]:
        """Топ-N ближайших остановок по всей БД (не в пределах одного района).

        Используется при геоподсказке посадки: показываем конкретные остановки, когда
        пользователь отправил своё местоположение.
        """
        with self.db.transaction() as conn:
            rows = conn.execute(
                """
                SELECT * FROM route_points
                WHERE kind = 'stop' AND latitude IS NOT NULL AND longitude IS NOT NULL
                """
            ).fetchall()
        scored: list[tuple[sqlite3.Row, float]] = []
        for r in rows:
            d = haversine_km(lat, lng, float(r["latitude"]), float(r["longitude"]))
            if d <= max_km:
                scored.append((r, d))
        scored.sort(key=lambda x: x[1])
        return scored[:limit]


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
            user = conn.execute(
                "SELECT * FROM users WHERE tg_user_id = ?",
                (tg_driver_id,),
            ).fetchone()
            if not user:
                raise ValueError("Пользователь не зарегистрирован.")

            # Роль — свойство поездки: создание поездки требует одобренного ВУ, независимо от поля role
            if not user["dl_series_number"]:
                raise ValueError(
                    "Для создания поездки нужны данные водительского удостоверения. Укажи их в профиле."
                )

            mod_status = driver_moderation_status(user)
            if mod_status == DRIVER_MOD_PENDING:
                raise ValueError("Заявка водителя на модерации. Создание поездок будет доступно после одобрения.")
            if mod_status == DRIVER_MOD_REJECTED:
                raise ValueError("Заявка водителя отклонена. Обратись в поддержку или подай заявку заново.")
            if mod_status != DRIVER_MOD_APPROVED:
                raise ValueError("Создание поездок доступно только после одобрения администратором.")

            trip_start = self._trip_start_dt(trip_date, departure_time)
            if trip_start is None:
                raise ValueError("Некорректные дата/время поездки.")
            if trip_start <= datetime.now():
                raise ValueError("Нельзя создать поездку на прошедшее время.")

            trip_id = self.db.insert_returning_id(
                conn,
                """
                INSERT INTO trips(
                    driver_id, start_point_id, end_point_id, trip_date, departure_time, time_slot, price_rub, seats_total
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user["id"],
                    start_point_id,
                    end_point_id,
                    trip_date,
                    departure_time,
                    f"{trip_date} {departure_time}",
                    price_rub,
                    seats_total,
                ),
            )
        record_event(self.db, EVENT_TRIP_CREATED, tg_user_id=tg_driver_id, props={"trip_id": trip_id})
        return trip_id

    def set_trip_comment(self, trip_id: int, comment: str | None) -> None:
        """Сохранить комментарий водителя к поездке (поле под Mini App; схема v8)."""
        with self.db.transaction() as conn:
            conn.execute("UPDATE trips SET comment = ? WHERE id = ?", (comment, trip_id))

    def disable_intermediate_pickup(self, trip_id: int) -> None:
        """Отключить промежуточные посадки для поездки (soft fail после ошибки API)."""
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE trips SET allow_intermediate_pickup = {self._dialect.bool_false()} WHERE id = ?",
                (trip_id,),
            )

    def save_route_compute(
        self,
        trip_id: int,
        polyline_json: str,
        intermediate_stops: list[dict],
    ) -> None:
        """Сохраняет polyline маршрута и промежуточные остановки (схема v12)."""
        insert_stop_sql = self._dialect.insert_ignore_trip_stop()
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE trips SET route_polyline = ? WHERE id = ?",
                (polyline_json, trip_id),
            )
            for stop in intermediate_stops:
                conn.execute(insert_stop_sql, (trip_id, stop["id"], stop["order_index"]))

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
                    sp.latitude AS start_lat,
                    sp.longitude AS start_lng,
                    ep.latitude AS end_lat,
                    ep.longitude AS end_lng,
                    u.name AS driver_name,
                    u.username AS driver_username,
                    u.rating_avg AS driver_rating,
                    u.rating_count AS driver_rating_count,
                    u.trips_driver_count AS driver_trips_count,
                    u.created_at AS driver_created_at
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
        start_district: str | None = None,
        end_district: str | None = None,
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
                u.rating_avg AS driver_rating,
                u.rating_count AS driver_rating_count,
                u.trips_driver_count AS driver_trips_count,
                u.created_at AS driver_created_at
            FROM trips t
            JOIN route_points sp ON sp.id = t.start_point_id
            JOIN route_points ep ON ep.id = t.end_point_id
            JOIN users u ON u.id = t.driver_id
            WHERE t.status = 'open'
        """
        params: list[object] = []
        if start_point_id:
            query += f"""
                AND (
                    t.start_point_id = ?
                    OR (
                        t.allow_intermediate_pickup = {self._dialect.bool_true()}
                        AND EXISTS (
                            SELECT 1 FROM trip_stops ts
                            WHERE ts.trip_id = t.id AND ts.stop_id = ?
                        )
                    )
                )
            """
            params.extend([start_point_id, start_point_id])
        if end_point_id:
            query += f"""
                AND (
                    t.end_point_id = ?
                    OR (
                        t.allow_intermediate_pickup = {self._dialect.bool_true()}
                        AND EXISTS (
                            SELECT 1 FROM trip_stops ts2
                            WHERE ts2.trip_id = t.id AND ts2.stop_id = ?
                        )
                    )
                )
            """
            params.extend([end_point_id, end_point_id])
        if start_district is not None:
            query += " AND COALESCE(sp.district, '') = ?"
            params.append(str(start_district).strip())
        if end_district is not None:
            query += " AND COALESCE(ep.district, '') = ?"
            params.append(str(end_district).strip())
        if trip_date:
            query += " AND t.trip_date = ?"
            params.append(trip_date)
        if departure_time:
            query += " AND t.departure_time = ?"
            params.append(departure_time)
        query += " ORDER BY t.id DESC LIMIT 25"

        with self.db.transaction() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        record_event(
            self.db,
            EVENT_SEARCH,
            props={
                "results": len(rows),
                "start_point_id": start_point_id,
                "end_point_id": end_point_id,
                "trip_date": trip_date,
            },
        )
        return rows

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
                    ep.title AS end_title,
                    sp.latitude AS start_lat,
                    sp.longitude AS start_lng,
                    ep.latitude AS end_lat,
                    ep.longitude AS end_lng,
                    u.name AS driver_name,
                    u.rating_avg AS driver_rating
                FROM trips t
                JOIN route_points sp ON sp.id = t.start_point_id
                JOIN route_points ep ON ep.id = t.end_point_id
                JOIN users u ON u.id = t.driver_id
                WHERE t.driver_id = ?
                ORDER BY t.id DESC
                """,
                (driver_id,),
            ).fetchall()

    def list_driver_history(self, tg_driver_id: int) -> list[sqlite3.Row]:
        """Прошлые/завершённые поездки водителя."""
        with self.db.transaction() as conn:
            driver_id = self._get_internal_user_id(conn, tg_driver_id)
            return conn.execute(
                f"""
                SELECT
                    t.id AS trip_id,
                    t.trip_date,
                    t.departure_time,
                    t.time_slot,
                    t.price_rub,
                    t.seats_total,
                    t.seats_booked,
                    t.status AS trip_status,
                    sp.title AS start_title,
                    ep.title AS end_title
                FROM trips t
                JOIN route_points sp ON sp.id = t.start_point_id
                JOIN route_points ep ON ep.id = t.end_point_id
                WHERE t.driver_id = ?
                  AND (
                    t.status IN ('completed', 'cancelled')
                    OR {self._dialect.trip_departure_lte_now()}
                  )
                ORDER BY t.trip_date DESC, t.departure_time DESC, t.id DESC
                """,
                (driver_id,),
            ).fetchall()

    def list_all_trips(
        self,
        *,
        status: str | None = None,
        trip_date: str | None = None,
        driver_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        """Список всех поездок для админки с фильтрами по статусу, дате и водителю (внутренний id)."""
        sql = """
            SELECT
                t.id, t.driver_id, t.trip_date, t.departure_time, t.time_slot,
                t.price_rub, t.seats_total, t.seats_booked, t.status, t.created_at,
                sp.title AS start_title, ep.title AS end_title,
                u.name AS driver_name, u.tg_user_id AS driver_tg_user_id
            FROM trips t
            JOIN route_points sp ON sp.id = t.start_point_id
            JOIN route_points ep ON ep.id = t.end_point_id
            JOIN users u ON u.id = t.driver_id
            WHERE 1=1
        """
        params: list[object] = []
        if status:
            sql += " AND t.status = ?"
            params.append(status)
        if trip_date:
            sql += " AND t.trip_date = ?"
            params.append(trip_date)
        if driver_id is not None:
            sql += " AND t.driver_id = ?"
            params.append(driver_id)
        sql += " ORDER BY t.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self.db.transaction() as conn:
            return conn.execute(sql, tuple(params)).fetchall()

    def get_trip_admin(self, trip_id: int) -> sqlite3.Row | None:
        """Поездка для экрана редактирования: поля trips + названия точек маршрута."""
        with self.db.transaction() as conn:
            return conn.execute(
                """
                SELECT
                    t.*,
                    sp.title AS start_title,
                    sp.district AS start_district,
                    ep.title AS end_title,
                    ep.district AS end_district
                FROM trips t
                JOIN route_points sp ON sp.id = t.start_point_id
                JOIN route_points ep ON ep.id = t.end_point_id
                WHERE t.id = ?
                """,
                (trip_id,),
            ).fetchone()

    def admin_update_trip(
        self,
        trip_id: int,
        *,
        start_point_id: int,
        end_point_id: int,
        price_rub: int,
        seats_total: int,
        trip_date: str,
        departure_time: str,
        status: str,
    ) -> None:
        """Админ-правка поездки. Инвариант: seats_total не может быть меньше уже занятых мест."""
        if status not in ("open", "cancelled", "completed"):
            raise ValueError("Недопустимый статус поездки.")
        if seats_total < 1:
            raise ValueError("Мест должно быть не меньше одного.")
        if price_rub < 0:
            raise ValueError("Цена не может быть отрицательной.")
        if start_point_id == end_point_id:
            raise ValueError("Точки отправления и назначения должны различаться.")
        with self.db.immediate_transaction() as conn:
            trip = conn.execute("SELECT seats_booked FROM trips WHERE id = ?", (trip_id,)).fetchone()
            if not trip:
                raise ValueError("Поездка не найдена.")
            if seats_total < int(trip["seats_booked"]):
                raise ValueError(f"Нельзя задать мест меньше уже забронированных ({int(trip['seats_booked'])}).")
            for point_id in (start_point_id, end_point_id):
                point = conn.execute(
                    "SELECT id FROM route_points WHERE id = ? AND kind = 'stop'",
                    (point_id,),
                ).fetchone()
                if not point:
                    raise ValueError(f"Остановка #{point_id} не найдена.")
            conn.execute(
                """
                UPDATE trips
                SET start_point_id = ?, end_point_id = ?, price_rub = ?, seats_total = ?,
                    trip_date = ?, departure_time = ?, time_slot = ?, status = ?
                WHERE id = ?
                """,
                (
                    start_point_id,
                    end_point_id,
                    price_rub,
                    seats_total,
                    trip_date,
                    departure_time,
                    f"{trip_date} {departure_time}",
                    status,
                    trip_id,
                ),
            )

    def admin_cancel_trip(self, trip_id: int) -> list[int]:
        """Принудительная отмена поездки администратором (без проверки владельца).

        Отменяет активные брони и обнуляет занятость. Возвращает tg_user_id пассажиров для уведомлений.
        """
        with self.db.immediate_transaction() as conn:
            trip = conn.execute("SELECT id, status FROM trips WHERE id = ?", (trip_id,)).fetchone()
            if not trip:
                raise ValueError("Поездка не найдена.")
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
                    cancel_reason = 'Поездка отменена администратором',
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

    def count_trips_by_status(self) -> dict[str, int]:
        """Счётчики поездок по статусам для дашборда."""
        with self.db.transaction() as conn:
            rows = conn.execute("SELECT status, COUNT(*) AS c FROM trips GROUP BY status").fetchall()
        return {str(r["status"]): int(r["c"]) for r in rows}

    def cancel_trip_by_driver(self, tg_driver_id: int, trip_id: int) -> list[int]:
        """Отменяет открытую поездку и активные брони. Возвращает tg_user_id пассажиров для уведомлений."""
        with self.db.immediate_transaction() as conn:
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
        with self.db.immediate_transaction() as conn:
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

            passenger = conn.execute(
                "SELECT rating_avg, rating_count FROM users WHERE id = ?",
                (passenger_id,),
            ).fetchone()
            if passenger is None:
                raise ValueError("Профиль пассажира не найден.")
            min_r = effective_min_passenger_rating(trip["driver_min_rating"])
            if min_r is not None:
                rc = int(passenger["rating_count"] or 0)
                ra = float(passenger["rating_avg"] or 0.0)
                if rc >= 1 and ra + 1e-9 < min_r:
                    raise ValueError(
                        f"Водитель принимает пассажиров с рейтингом не ниже {min_r:.1f}. "
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
                booking_id = self.db.insert_returning_id(
                    conn, "INSERT INTO bookings(trip_id, passenger_id) VALUES (?, ?)", (trip_id, passenger_id)
                )

            cur = conn.execute(
                """
                UPDATE trips
                SET seats_booked = seats_booked + 1
                WHERE id = ?
                  AND status = 'open'
                  AND seats_booked < seats_total
                """,
                (trip_id,),
            )
            if cur.rowcount != 1:
                raise ValueError("Свободных мест нет.")
        record_event(
            self.db,
            EVENT_BOOKING_CREATED,
            tg_user_id=tg_passenger_id,
            props={"trip_id": trip_id, "booking_id": booking_id},
        )
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
                    sp.latitude AS start_lat,
                    sp.longitude AS start_lng,
                    ep.latitude AS end_lat,
                    ep.longitude AS end_lng,
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

    def list_passenger_history(self, tg_passenger_id: int) -> list[sqlite3.Row]:
        """Прошлые/завершённые поездки пассажира (брони + данные поездки и контрагента)."""
        with self.db.transaction() as conn:
            passenger_id = self._get_internal_user_id(conn, tg_passenger_id)
            return conn.execute(
                f"""
                SELECT
                    b.id AS booking_id,
                    b.status AS booking_status,
                    b.cancel_reason,
                    t.id AS trip_id,
                    t.trip_date,
                    t.departure_time,
                    t.time_slot,
                    t.price_rub,
                    t.status AS trip_status,
                    t.seats_total,
                    t.seats_booked,
                    sp.title AS start_title,
                    ep.title AS end_title,
                    u.name AS driver_name,
                    u.tg_user_id AS driver_tg_user_id,
                    u.rating_avg AS driver_rating,
                    tr.stars AS my_rating_stars
                FROM bookings b
                JOIN trips t ON t.id = b.trip_id
                JOIN route_points sp ON sp.id = t.start_point_id
                JOIN route_points ep ON ep.id = t.end_point_id
                JOIN users u ON u.id = t.driver_id
                LEFT JOIN trip_ratings tr
                    ON tr.trip_id = t.id AND tr.rater_user_id = b.passenger_id
                WHERE b.passenger_id = ?
                  AND (
                    b.status != 'active'
                    OR t.status IN ('completed', 'cancelled')
                    OR {self._dialect.trip_departure_lte_now()}
                  )
                ORDER BY t.trip_date DESC, t.departure_time DESC, b.id DESC
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
        with self.db.immediate_transaction() as conn:
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
            cur = conn.execute(
                """
                UPDATE trips
                SET seats_booked = seats_booked - 1
                WHERE id = ? AND seats_booked > 0
                """,
                (booking["trip_id"],),
            )
            if cur.rowcount != 1:
                logger.error(
                    "invariant seats_booked decrement failed trip_id=%s booking_id=%s",
                    booking["trip_id"],
                    booking_id,
                )
                raise RuntimeError("Не удалось обновить занятость мест (несогласованное состояние).")

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
            cancelled_trip_id = int(booking["trip_id"])
        record_event(
            self.db,
            EVENT_BOOKING_CANCELLED,
            tg_user_id=tg_passenger_id,
            props={"trip_id": cancelled_trip_id, "booking_id": booking_id},
        )
        return cancelled_trip_id, payload

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

    def list_all_bookings(
        self,
        *,
        status: str | None = None,
        trip_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        """Список всех броней для админки с фильтрами по статусу и поездке."""
        sql = """
            SELECT
                b.id, b.status, b.cancel_reason, b.created_at, b.cancelled_at,
                b.trip_id, b.passenger_id,
                p.name AS passenger_name, p.tg_user_id AS passenger_tg_user_id,
                t.trip_date, t.departure_time, t.time_slot,
                sp.title AS start_title, ep.title AS end_title
            FROM bookings b
            JOIN trips t ON t.id = b.trip_id
            JOIN users p ON p.id = b.passenger_id
            JOIN route_points sp ON sp.id = t.start_point_id
            JOIN route_points ep ON ep.id = t.end_point_id
            WHERE 1=1
        """
        params: list[object] = []
        if status:
            sql += " AND b.status = ?"
            params.append(status)
        if trip_id is not None:
            sql += " AND b.trip_id = ?"
            params.append(trip_id)
        sql += " ORDER BY b.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self.db.transaction() as conn:
            return conn.execute(sql, tuple(params)).fetchall()

    def count_active_bookings(self) -> int:
        with self.db.transaction() as conn:
            return int(conn.execute("SELECT COUNT(*) AS c FROM bookings WHERE status = 'active'").fetchone()["c"])

    def reject_booking_by_driver(self, tg_driver_id: int, booking_id: int) -> dict[str, object]:
        with self.db.immediate_transaction() as conn:
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
            cur = conn.execute(
                """
                UPDATE trips
                SET seats_booked = seats_booked - 1
                WHERE id = ? AND seats_booked > 0
                """,
                (booking["trip_id"],),
            )
            if cur.rowcount != 1:
                logger.error(
                    "invariant seats_booked decrement failed trip_id=%s booking_id=%s",
                    booking["trip_id"],
                    booking_id,
                )
                raise RuntimeError("Не удалось обновить занятость мест (несогласованное состояние).")
            return {
                "passenger_tg_user_id": int(booking["passenger_tg_user_id"]),
                "trip_id": int(booking["trip_id"]),
                "start_title": booking["start_title"],
                "end_title": booking["end_title"],
                "trip_date": booking["trip_date"],
                "departure_time": booking["departure_time"],
                "time_slot": booking["time_slot"],
            }

    def list_driver_booking_notification_events(self, tg_driver_id: int, *, days: int = 14) -> list[sqlite3.Row]:
        """События броней для водителя: новые и отмены пассажиром."""
        with self.db.transaction() as conn:
            days_param = self._dialect.days_ago_param(days)
            created_filter = self._dialect.days_ago_sql("b.created_at")
            cancelled_filter = self._dialect.days_ago_sql("b.cancelled_at")
            return conn.execute(
                f"""
                SELECT
                    b.id AS booking_id,
                    b.status,
                    b.created_at,
                    b.cancelled_at,
                    b.cancel_reason,
                    t.id AS trip_id,
                    t.trip_date,
                    t.departure_time,
                    t.time_slot,
                    p.name AS passenger_name,
                    sp.title AS start_title,
                    ep.title AS end_title
                FROM bookings b
                JOIN trips t ON t.id = b.trip_id
                JOIN users dr ON dr.id = t.driver_id
                JOIN users p ON p.id = b.passenger_id
                JOIN route_points sp ON sp.id = t.start_point_id
                JOIN route_points ep ON ep.id = t.end_point_id
                WHERE dr.tg_user_id = ?
                  AND (
                    (
                      b.status = 'active'
                      AND {created_filter}
                    )
                    OR (
                      b.status = 'cancelled_by_passenger'
                      AND b.cancelled_at IS NOT NULL
                      AND {cancelled_filter}
                    )
                  )
                ORDER BY COALESCE(b.cancelled_at, b.created_at) DESC
                LIMIT 40
                """,
                (tg_driver_id, days_param, days_param),
            ).fetchall()

    def list_passenger_booking_notification_events(self, tg_passenger_id: int, *, days: int = 14) -> list[sqlite3.Row]:
        """События броней для пассажира: отмены водителем."""
        with self.db.transaction() as conn:
            passenger_id = self._get_internal_user_id(conn, tg_passenger_id)
            days_param = self._dialect.days_ago_param(days)
            cancelled_filter = self._dialect.days_ago_sql("b.cancelled_at")
            return conn.execute(
                f"""
                SELECT
                    b.id AS booking_id,
                    b.status,
                    b.cancelled_at,
                    b.cancel_reason,
                    t.id AS trip_id,
                    t.trip_date,
                    t.departure_time,
                    t.time_slot,
                    u.name AS driver_name,
                    sp.title AS start_title,
                    ep.title AS end_title
                FROM bookings b
                JOIN trips t ON t.id = b.trip_id
                JOIN users u ON u.id = t.driver_id
                JOIN route_points sp ON sp.id = t.start_point_id
                JOIN route_points ep ON ep.id = t.end_point_id
                WHERE b.passenger_id = ?
                  AND b.status = 'cancelled_by_driver'
                  AND b.cancelled_at IS NOT NULL
                  AND {cancelled_filter}
                ORDER BY b.cancelled_at DESC
                LIMIT 40
                """,
                (passenger_id, days_param),
            ).fetchall()


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
            except Exception as exc:
                if is_unique_violation(exc):
                    return False
                raise

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
            except Exception as exc:
                if is_unique_violation(exc):
                    return False
                raise

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

    def delete_favorite(self, tg_user_id: int, favorite_id: int) -> bool:
        """Удалить избранный маршрут пользователя. True если строка была удалена."""
        with self.db.transaction() as conn:
            cur = conn.execute(
                "DELETE FROM favorite_routes WHERE id = ? AND tg_user_id = ?",
                (favorite_id, tg_user_id),
            )
            return cur.rowcount > 0


class RatingRepository(_BaseRepository):
    def _refresh_user_rating(self, conn: sqlite3.Connection, rated_user_id: int) -> None:
        """Пересчитывает денормализованные rating_avg/rating_count в рамках текущей транзакции.

        Денормализация ускоряет read-запросы без JOIN на trip_ratings при каждом отображении профиля.
        """
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
        """Сохранить оценку и пересчитать рейтинг получателя.

        Оценивать можно только участников конкретной поездки — это предотвращает накрутку.
        Окно открывается через 3 ч после отправления, чтобы поездка успела завершиться.
        """
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
            except Exception as exc:
                if is_unique_violation(exc):
                    raise ValueError("Эта оценка уже была сохранена.") from exc
                raise
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

    def list_all_ratings(
        self,
        *,
        rated_user_id: int | None = None,
        only_with_review: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        """Список всех оценок для модерации; фильтр по получателю и наличию текстового отзыва."""
        sql = """
            SELECT
                tr.id, tr.trip_id, tr.stars, tr.review_text, tr.created_at,
                tr.rater_user_id, tr.rated_user_id,
                rater.name AS rater_name,
                rated.name AS rated_name
            FROM trip_ratings tr
            JOIN users rater ON rater.id = tr.rater_user_id
            JOIN users rated ON rated.id = tr.rated_user_id
            WHERE 1=1
        """
        params: list[object] = []
        if rated_user_id is not None:
            sql += " AND tr.rated_user_id = ?"
            params.append(rated_user_id)
        if only_with_review:
            sql += " AND tr.review_text IS NOT NULL AND trim(tr.review_text) != ''"
        sql += " ORDER BY tr.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self.db.transaction() as conn:
            return conn.execute(sql, tuple(params)).fetchall()

    def delete_rating(self, rating_id: int) -> int:
        """Удалить оценку и пересчитать рейтинг получателя. Возвращает rated_user_id."""
        with self.db.transaction() as conn:
            row = conn.execute("SELECT rated_user_id FROM trip_ratings WHERE id = ?", (rating_id,)).fetchone()
            if not row:
                raise ValueError("Оценка не найдена.")
            rated_id = int(row["rated_user_id"])
            conn.execute("DELETE FROM trip_ratings WHERE id = ?", (rating_id,))
            self._refresh_user_rating(conn, rated_id)
            return rated_id

    def set_review_text(self, rating_id: int, review_text: str | None) -> None:
        """Модерация текста отзыва: скрыть (None) или заменить. Звёзды не трогаем."""
        with self.db.transaction() as conn:
            row = conn.execute("SELECT id FROM trip_ratings WHERE id = ?", (rating_id,)).fetchone()
            if not row:
                raise ValueError("Оценка не найдена.")
            conn.execute("UPDATE trip_ratings SET review_text = ? WHERE id = ?", (review_text, rating_id))

    def mark_rating_prompt_sent(self, trip_id: int, rater_user_id: int, rated_user_id: int) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                self._dialect.insert_ignore_rating_prompt(),
                (trip_id, rater_user_id, rated_user_id),
            )

    def list_pending_rating_prompts(self, now: datetime | None = None) -> list[PendingRatingPrompt]:
        """Поездки с активной бронью: отправление + 3 ч в прошлом; нет оценки и не отправляли напоминание."""
        now = now or datetime.now()
        cutoff = now - timedelta(hours=3)
        cutoff_s = cutoff.strftime("%Y-%m-%d %H:%M:%S")

        trip_cutoff = self._dialect.trip_departure_lte_param()

        sql = f"""
            SELECT
                t.id AS trip_id,
                b.passenger_id AS rater_user_id,
                t.driver_id AS rated_user_id,
                p.tg_user_id AS rater_tg_user_id,
                dr.tg_user_id AS rated_tg_user_id,
                dr.name AS rated_display_name,
                'p2d' AS prompt_kind
            FROM trips t
            JOIN bookings b ON b.trip_id = t.id AND b.status = 'active'
            JOIN users p ON p.id = b.passenger_id
            JOIN users dr ON dr.id = t.driver_id
            LEFT JOIN trip_ratings tr
                ON tr.trip_id = t.id
                AND tr.rater_user_id = b.passenger_id
                AND tr.rated_user_id = t.driver_id
            LEFT JOIN rating_prompts_sent rs
                ON rs.trip_id = t.id
                AND rs.rater_user_id = b.passenger_id
                AND rs.rated_user_id = t.driver_id
            WHERE t.status != 'cancelled'
              AND trim(COALESCE(t.trip_date, '')) != ''
              AND trim(COALESCE(t.departure_time, '')) != ''
              AND {trip_cutoff}
              AND tr.id IS NULL
              AND rs.trip_id IS NULL

            UNION ALL

            SELECT
                t.id AS trip_id,
                t.driver_id AS rater_user_id,
                b.passenger_id AS rated_user_id,
                dr.tg_user_id AS rater_tg_user_id,
                p.tg_user_id AS rated_tg_user_id,
                p.name AS rated_display_name,
                'd2p' AS prompt_kind
            FROM trips t
            JOIN bookings b ON b.trip_id = t.id AND b.status = 'active'
            JOIN users p ON p.id = b.passenger_id
            JOIN users dr ON dr.id = t.driver_id
            LEFT JOIN trip_ratings tr
                ON tr.trip_id = t.id
                AND tr.rater_user_id = t.driver_id
                AND tr.rated_user_id = b.passenger_id
            LEFT JOIN rating_prompts_sent rs
                ON rs.trip_id = t.id
                AND rs.rater_user_id = t.driver_id
                AND rs.rated_user_id = b.passenger_id
            WHERE t.status != 'cancelled'
              AND trim(COALESCE(t.trip_date, '')) != ''
              AND trim(COALESCE(t.departure_time, '')) != ''
              AND {trip_cutoff}
              AND tr.id IS NULL
              AND rs.trip_id IS NULL
        """

        out: list[PendingRatingPrompt] = []
        with self.db.transaction() as conn:
            rows = conn.execute(sql, (cutoff_s, cutoff_s)).fetchall()

        for row in rows:
            trip_id = int(row["trip_id"])
            rated_name = str(row["rated_display_name"] or "")
            kind = str(row["prompt_kind"])
            if kind == "p2d":
                prompt_text = f"Поездка #{trip_id} состоялась. Оцените водителя «{rated_name}» (от 1 до 5):"
            else:
                prompt_text = f"Поездка #{trip_id}. Оцените пассажира «{rated_name}» (от 1 до 5):"

            out.append(
                PendingRatingPrompt(
                    trip_id=trip_id,
                    rater_user_id=int(row["rater_user_id"]),
                    rated_user_id=int(row["rated_user_id"]),
                    rater_tg_user_id=int(row["rater_tg_user_id"]),
                    rated_tg_user_id=int(row["rated_tg_user_id"]),
                    rated_name=rated_name,
                    prompt_text=prompt_text,
                )
            )

        return out


class AdminRepository(_BaseRepository):
    """Учётные записи администраторов и журнал их действий (таблицы admin_users, admin_audit_log)."""

    def get_admin(self, username: str) -> sqlite3.Row | None:
        with self.db.transaction() as conn:
            return conn.execute("SELECT * FROM admin_users WHERE username = ?", (username,)).fetchone()

    def list_admins(self) -> list[sqlite3.Row]:
        with self.db.transaction() as conn:
            return conn.execute(
                "SELECT id, username, created_at, last_login_at FROM admin_users ORDER BY id"
            ).fetchall()

    def create_admin(self, username: str, password_hash: str) -> int:
        if not username.strip():
            raise ValueError("Логин администратора не может быть пустым.")
        with self.db.transaction() as conn:
            try:
                return self.db.insert_returning_id(
                    conn,
                    "INSERT INTO admin_users(username, password_hash) VALUES (?, ?)",
                    (username.strip(), password_hash),
                )
            except Exception as exc:
                if is_unique_violation(exc):
                    raise ValueError("Администратор с таким логином уже существует.") from exc
                raise

    def set_password_hash(self, username: str, password_hash: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("UPDATE admin_users SET password_hash = ? WHERE username = ?", (password_hash, username))

    def touch_last_login(self, username: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE admin_users SET last_login_at = CURRENT_TIMESTAMP WHERE username = ?",
                (username,),
            )

    def add_audit(
        self,
        *,
        admin_username: str,
        action: str,
        entity: str,
        entity_id: str | None,
        details: str | None,
    ) -> None:
        """Запись действия админа. Не должна ломать основную операцию — вызывается после успешной правки."""
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO admin_audit_log(admin_username, action, entity, entity_id, details)
                VALUES (?, ?, ?, ?, ?)
                """,
                (admin_username, action, entity, entity_id, details),
            )

    def list_audit(self, *, limit: int = 100, offset: int = 0) -> list[sqlite3.Row]:
        with self.db.transaction() as conn:
            return conn.execute(
                "SELECT * FROM admin_audit_log ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()


class TripTemplateRepository(_BaseRepository):
    """Маршруты-шаблоны водителя (таблица trip_templates): постоянный маршрут + дефолты цены/мест/комментария."""

    def create_template(
        self,
        tg_driver_id: int,
        *,
        start_point_id: int,
        end_point_id: int,
        price_rub: int,
        seats_total: int,
        comment: str | None = None,
        schedule_days: str | None = None,
        schedule_time: str | None = None,
    ) -> int:
        with self.db.transaction() as conn:
            driver = conn.execute("SELECT * FROM users WHERE tg_user_id = ?", (tg_driver_id,)).fetchone()
            if not is_approved_driver(driver):
                raise ValueError("Маршруты-шаблоны доступны только одобренному водителю.")
            return self.db.insert_returning_id(
                conn,
                """
                INSERT INTO trip_templates(
                    driver_id, start_point_id, end_point_id, price_rub, seats_total, comment, schedule_days, schedule_time
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (int(driver["id"]), start_point_id, end_point_id, price_rub, seats_total, comment, schedule_days, schedule_time),
            )

    def list_templates(self, tg_driver_id: int) -> list[sqlite3.Row]:
        with self.db.transaction() as conn:
            driver_id = self._get_internal_user_id(conn, tg_driver_id)
            return conn.execute(
                """
                SELECT
                    tt.id, tt.start_point_id, tt.end_point_id, tt.price_rub, tt.seats_total, tt.comment,
                    tt.schedule_days, tt.schedule_time,
                    sp.title AS start_title, ep.title AS end_title
                FROM trip_templates tt
                JOIN route_points sp ON sp.id = tt.start_point_id
                JOIN route_points ep ON ep.id = tt.end_point_id
                WHERE tt.driver_id = ?
                ORDER BY tt.id DESC
                """,
                (driver_id,),
            ).fetchall()

    def get_template(self, tg_driver_id: int, template_id: int) -> sqlite3.Row | None:
        with self.db.transaction() as conn:
            driver_id = self._get_internal_user_id(conn, tg_driver_id)
            return conn.execute(
                "SELECT * FROM trip_templates WHERE id = ? AND driver_id = ?",
                (template_id, driver_id),
            ).fetchone()

    def delete_template(self, tg_driver_id: int, template_id: int) -> bool:
        with self.db.transaction() as conn:
            driver_id = self._get_internal_user_id(conn, tg_driver_id)
            cur = conn.execute(
                "DELETE FROM trip_templates WHERE id = ? AND driver_id = ?",
                (template_id, driver_id),
            )
            return cur.rowcount > 0

    def create_trip_from_template(
        self,
        tg_driver_id: int,
        template_id: int,
        trip_date: str,
        departure_time: str | None = None,
    ) -> int:
        """Создаёт поездку на основе шаблона. Если departure_time не указано, берётся из schedule_time шаблона."""
        template = self.get_template(tg_driver_id, template_id)
        if not template:
            raise ValueError("Шаблон не найден или не принадлежит водителю.")

        final_departure_time = departure_time or template["schedule_time"]
        if not final_departure_time:
            raise ValueError("Не указано время отправления (ни в параметрах, ни в шаблоне).")

        trip_repo = TripRepository(self.db)
        trip_id = trip_repo.create_trip(
            tg_driver_id,
            start_point_id=template["start_point_id"],
            end_point_id=template["end_point_id"],
            trip_date=trip_date,
            departure_time=final_departure_time,
            price_rub=template["price_rub"],
            seats_total=template["seats_total"],
        )

        if template["comment"]:
            trip_repo.set_trip_comment(trip_id, template["comment"])

        return trip_id


class RouteAlertRepository(_BaseRepository):
    """Подписки на маршрут: пассажир хочет узнать, когда появится поездка по направлению."""

    def create_alert(
        self,
        tg_user_id: int,
        from_point_id: int,
        to_point_id: int,
        desired_date: str,
        desired_time: str | None = None,
    ) -> int:
        """Создать подписку на маршрут при пустом поиске."""
        with self.db.transaction() as conn:
            passenger_id = self._get_internal_user_id(conn, tg_user_id)
            from app.database import insert_returning_id

            alert_id = insert_returning_id(
                self.db,
                conn,
                """
                INSERT INTO route_alerts (passenger_id, from_point_id, to_point_id, desired_date, desired_time, status)
                VALUES (?, ?, ?, ?, ?, 'active')
                """,
                (passenger_id, from_point_id, to_point_id, desired_date, desired_time),
            )
            return alert_id

    def find_matching_alerts(
        self,
        trip_start_point_id: int,
        trip_end_point_id: int,
        trip_date: str,
    ) -> list[sqlite3.Row]:
        """Найти активные подписки, которые соответствуют новой поездке."""
        with self.db.transaction() as conn:
            return conn.execute(
                """
                SELECT ra.id, ra.passenger_id, ra.desired_time, u.tg_user_id AS passenger_tg_user_id,
                       sp.title AS from_title, ep.title AS to_title
                FROM route_alerts ra
                JOIN users u ON u.id = ra.passenger_id
                JOIN route_points sp ON sp.id = ra.from_point_id
                JOIN route_points ep ON ep.id = ra.to_point_id
                WHERE ra.status = 'active'
                  AND ra.from_point_id = ?
                  AND ra.to_point_id = ?
                  AND ra.desired_date = ?
                """,
                (trip_start_point_id, trip_end_point_id, trip_date),
            ).fetchall()

    def mark_as_notified(self, alert_id: int) -> None:
        """Отметить подписку как обработанную после отправки уведомления."""
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE route_alerts SET status = 'notified' WHERE id = ?",
                (alert_id,),
            )

    def list_passenger_alerts(self, tg_user_id: int, status: str = "active") -> list[sqlite3.Row]:
        """Список подписок пассажира (для управления в профиле)."""
        with self.db.transaction() as conn:
            passenger_id = self._get_internal_user_id(conn, tg_user_id)
            return conn.execute(
                """
                SELECT ra.id, ra.desired_date, ra.desired_time, ra.status, ra.created_at,
                       sp.title AS from_title, ep.title AS to_title
                FROM route_alerts ra
                JOIN route_points sp ON sp.id = ra.from_point_id
                JOIN route_points ep ON ep.id = ra.to_point_id
                WHERE ra.passenger_id = ? AND ra.status = ?
                ORDER BY ra.created_at DESC
                """,
                (passenger_id, status),
            ).fetchall()


class Repo:
    """Тонкий контейнер под-репозиториев; вызовы идут через repo.users, repo.routes, …"""

    def __init__(self, db: DbHandle) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.routes = RouteRepository(db)
        self.trips = TripRepository(db)
        self.bookings = BookingRepository(db)
        self.favorites = FavoriteRouteRepository(db)
        self.ratings = RatingRepository(db)
        self.admin = AdminRepository(db)
        self.templates = TripTemplateRepository(db)
        self.alerts = RouteAlertRepository(db)

    @staticmethod
    def default_date() -> str:
        return date.today().isoformat()

    @staticmethod
    def chunk_rows(rows: Iterable[sqlite3.Row], size: int = 10) -> list[list[sqlite3.Row]]:
        rows_list = list(rows)
        return [rows_list[i : i + size] for i in range(0, len(rows_list), size)]
