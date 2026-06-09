"""Сервисный слой админки: правки/удаления через repo с записью в аудит и подготовкой уведомлений.

Сервис намеренно синхронный (как и repo) и НЕ обращается к Telegram сам: методы, затрагивающие
пользователей, возвращают список уведомлений, а отправку через Bot API делает веб-слой. Это
сохраняет тестируемость без сети и не связывает доменную логику с aiogram.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.repo import Repo


@dataclass(frozen=True)
class AdminNotification:
    """Сообщение, которое веб-слой должен отправить пользователю после действия админа."""

    tg_user_id: int
    text: str


class AdminService:
    def __init__(self, repo: Repo) -> None:
        self._repo = repo

    def _audit(
        self,
        admin_username: str,
        action: str,
        entity: str,
        entity_id: int | str | None,
        details: str | None = None,
    ) -> None:
        self._repo.admin.add_audit(
            admin_username=admin_username,
            action=action,
            entity=entity,
            entity_id=None if entity_id is None else str(entity_id),
            details=details,
        )

    # ── поездки ──────────────────────────────────────────────────────────────

    def update_trip(
        self,
        admin_username: str,
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
        self._repo.trips.admin_update_trip(
            trip_id,
            start_point_id=start_point_id,
            end_point_id=end_point_id,
            price_rub=price_rub,
            seats_total=seats_total,
            trip_date=trip_date,
            departure_time=departure_time,
            status=status,
        )
        self._audit(
            admin_username,
            "update",
            "trip",
            trip_id,
            (
                f"start={start_point_id}, end={end_point_id}, price={price_rub}, "
                f"seats={seats_total}, date={trip_date} {departure_time}, status={status}"
            ),
        )

    def cancel_trip(self, admin_username: str, trip_id: int) -> list[AdminNotification]:
        notify_ids = self._repo.trips.admin_cancel_trip(trip_id)
        self._audit(admin_username, "cancel", "trip", trip_id, f"notified={len(notify_ids)}")
        text = f"Поездка #{trip_id} отменена администратором. Твоя бронь аннулирована."
        return [AdminNotification(tg_user_id=tg, text=text) for tg in notify_ids]

    # ── пользователи ───────────────────────────────────────────────────────────

    def update_user(
        self,
        admin_username: str,
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
        self._repo.users.admin_update_user(
            user_id,
            name=name,
            role=role,
            min_passenger_rating=min_passenger_rating,
            dl_series_number=dl_series_number,
            dl_valid_until=dl_valid_until,
            car_model=car_model,
            car_color=car_color,
            car_plate=car_plate,
        )
        self._audit(
            admin_username,
            "update",
            "user",
            user_id,
            f"name={name}, role={role}, min_rating={min_passenger_rating}",
        )

    def set_user_ban(self, admin_username: str, user_id: int, banned: bool) -> list[AdminNotification]:
        tg_user_id = self._repo.users.set_banned(user_id, banned)
        self._audit(admin_username, "ban" if banned else "unban", "user", user_id, None)
        if banned:
            return [AdminNotification(tg_user_id=tg_user_id, text="Доступ к боту ограничен администратором.")]
        return [AdminNotification(tg_user_id=tg_user_id, text="Доступ к боту восстановлен.")]

    def approve_driver(self, admin_username: str, user_id: int) -> list[AdminNotification]:
        tg_user_id = self._repo.users.approve_driver(user_id)
        self._audit(admin_username, "approve_driver", "user", user_id, None)
        return [
            AdminNotification(
                tg_user_id=tg_user_id,
                text="Заявка водителя одобрена. Теперь можно создавать поездки в Yaride.",
            )
        ]

    def reject_driver(self, admin_username: str, user_id: int) -> list[AdminNotification]:
        tg_user_id = self._repo.users.reject_driver(user_id)
        self._audit(admin_username, "reject_driver", "user", user_id, None)
        return [
            AdminNotification(
                tg_user_id=tg_user_id,
                text="Заявка водителя отклонена. Проверь данные ВУ и подай заявку заново через профиль.",
            )
        ]

    # ── оценки ─────────────────────────────────────────────────────────────────

    def delete_rating(self, admin_username: str, rating_id: int) -> None:
        rated_id = self._repo.ratings.delete_rating(rating_id)
        self._audit(admin_username, "delete", "rating", rating_id, f"rated_user_id={rated_id}")

    def moderate_review(self, admin_username: str, rating_id: int, review_text: str | None) -> None:
        self._repo.ratings.set_review_text(rating_id, review_text)
        action = "clear_review" if review_text is None else "edit_review"
        self._audit(admin_username, action, "rating", rating_id, None)

    # ── точки маршрута ───────────────────────────────────────────────────────────

    def create_point(
        self,
        admin_username: str,
        *,
        locality: str,
        district: str,
        admin_area: str,
        title: str,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> int:
        point_id = self._repo.routes.admin_create_point(
            locality=locality,
            district=district,
            admin_area=admin_area,
            title=title,
            latitude=latitude,
            longitude=longitude,
        )
        self._audit(admin_username, "create", "route_point", point_id, f"{locality}/{title}")
        return point_id

    def update_point(
        self,
        admin_username: str,
        point_id: int,
        *,
        locality: str,
        district: str,
        admin_area: str,
        title: str,
        latitude: float | None,
        longitude: float | None,
    ) -> None:
        self._repo.routes.admin_update_point(
            point_id,
            locality=locality,
            district=district,
            admin_area=admin_area,
            title=title,
            latitude=latitude,
            longitude=longitude,
        )
        self._audit(admin_username, "update", "route_point", point_id, f"{locality}/{title}")

    def patch_point_coordinates(
        self,
        admin_username: str,
        point_id: int,
        *,
        latitude: float,
        longitude: float,
    ) -> None:
        self._repo.routes.admin_patch_point_coordinates(
            point_id,
            latitude=latitude,
            longitude=longitude,
        )
        self._audit(
            admin_username,
            "patch_coords",
            "route_point",
            point_id,
            f"{latitude:.6f},{longitude:.6f}",
        )

    def delete_point(self, admin_username: str, point_id: int) -> None:
        self._repo.routes.admin_delete_point(point_id)
        self._audit(admin_username, "delete", "route_point", point_id, None)
