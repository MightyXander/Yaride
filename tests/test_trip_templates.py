from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

from app.db import Database
from app.repo import Repo


def _make_db(tmp: str) -> Database:
    db = Database(str(Path(tmp) / "templates.db"))
    db.init_schema()
    return db


def _setup_driver(repo: Repo, tg_user_id: int = 999) -> int:
    """Создаёт одобренного водителя и возвращает его tg_user_id."""
    repo.users.upsert_user(
        tg_user_id,
        name="Test Driver",
        username="testdriver",
        role="driver",
        dl_series_number="1234567890",
        dl_valid_until="2030-12-31",
    )
    with repo.db.transaction() as conn:
        conn.execute(
            "UPDATE users SET driver_moderation_status = 'approved' WHERE tg_user_id = ?",
            (tg_user_id,),
        )
    return tg_user_id


def _setup_route(repo: Repo) -> tuple[int, int]:
    """Создаёт две точки маршрута и возвращает их id."""
    with repo.db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO route_points(locality, district, admin_area, title, latitude, longitude, kind)
            VALUES ('Ярославль', 'Дзержинский', '', 'Тестовый район A', 57.6298, 39.8737, 'stop')
            """
        )
        start_id = int(conn.execute("SELECT id FROM route_points WHERE title = 'Тестовый район A'").fetchone()["id"])

        conn.execute(
            """
            INSERT INTO route_points(locality, district, admin_area, title, latitude, longitude, kind)
            VALUES ('Ярославль', 'Фрунзенский', '', 'Тестовый район B', 57.6190, 39.8730, 'stop')
            """
        )
        end_id = int(conn.execute("SELECT id FROM route_points WHERE title = 'Тестовый район B'").fetchone()["id"])

    return start_id, end_id


class TripTemplateTests(TestCase):
    def test_create_template_with_schedule(self) -> None:
        """Шаблон с расписанием (дни недели и время) успешно создаётся."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            try:
                repo = Repo(db)
                driver_id = _setup_driver(repo)
                start_id, end_id = _setup_route(repo)

                template_id = repo.templates.create_template(
                    driver_id,
                    start_point_id=start_id,
                    end_point_id=end_id,
                    price_rub=150,
                    seats_total=3,
                    comment="Ежедневная поездка на работу",
                    schedule_days="Mon,Tue,Wed,Thu,Fri",
                    schedule_time="08:00",
                )

                self.assertIsNotNone(template_id)
                self.assertGreater(template_id, 0)

                template = repo.templates.get_template(driver_id, template_id)
                self.assertIsNotNone(template)
                self.assertEqual(template["schedule_days"], "Mon,Tue,Wed,Thu,Fri")
                self.assertEqual(template["schedule_time"], "08:00")
                self.assertEqual(template["price_rub"], 150)
                self.assertEqual(template["seats_total"], 3)
                self.assertEqual(template["comment"], "Ежедневная поездка на работу")
            finally:
                db.close()

    def test_create_template_without_schedule(self) -> None:
        """Шаблон без расписания (только маршрут/цена/места) тоже работает."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            try:
                repo = Repo(db)
                driver_id = _setup_driver(repo)
                start_id, end_id = _setup_route(repo)

                template_id = repo.templates.create_template(
                    driver_id,
                    start_point_id=start_id,
                    end_point_id=end_id,
                    price_rub=200,
                    seats_total=4,
                )

                template = repo.templates.get_template(driver_id, template_id)
                self.assertIsNotNone(template)
                self.assertIsNone(template["schedule_days"])
                self.assertIsNone(template["schedule_time"])
                self.assertEqual(template["price_rub"], 200)
            finally:
                db.close()

    def test_list_templates_includes_schedule_fields(self) -> None:
        """Список шаблонов возвращает поля schedule_days и schedule_time."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            try:
                repo = Repo(db)
                driver_id = _setup_driver(repo)
                start_id, end_id = _setup_route(repo)

                repo.templates.create_template(
                    driver_id,
                    start_point_id=start_id,
                    end_point_id=end_id,
                    price_rub=100,
                    seats_total=2,
                    schedule_days="Mon,Wed,Fri",
                    schedule_time="07:30",
                )

                templates = repo.templates.list_templates(driver_id)
                self.assertEqual(len(templates), 1)
                self.assertEqual(templates[0]["schedule_days"], "Mon,Wed,Fri")
                self.assertEqual(templates[0]["schedule_time"], "07:30")
                self.assertIn("start_title", templates[0].keys())
                self.assertIn("end_title", templates[0].keys())
            finally:
                db.close()

    def test_create_trip_from_template_uses_template_data(self) -> None:
        """Создание поездки из шаблона копирует маршрут, цену, места."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            try:
                repo = Repo(db)
                driver_id = _setup_driver(repo)
                start_id, end_id = _setup_route(repo)

                template_id = repo.templates.create_template(
                    driver_id,
                    start_point_id=start_id,
                    end_point_id=end_id,
                    price_rub=180,
                    seats_total=3,
                    comment="Регулярная поездка",
                    schedule_time="09:00",
                )

                trip_id = repo.templates.create_trip_from_template(
                    driver_id,
                    template_id,
                    trip_date="2099-06-20",
                )

                trip = repo.trips.get_trip_public_card(trip_id)
                self.assertIsNotNone(trip)
                self.assertEqual(trip["price_rub"], 180)
                self.assertEqual(trip["seats_total"], 3)
                self.assertEqual(trip["departure_time"], "09:00")
                self.assertEqual(trip["trip_date"], "2099-06-20")
            finally:
                db.close()

    def test_create_trip_from_template_override_departure_time(self) -> None:
        """Можно переопределить время отправления при создании поездки из шаблона."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            try:
                repo = Repo(db)
                driver_id = _setup_driver(repo)
                start_id, end_id = _setup_route(repo)

                template_id = repo.templates.create_template(
                    driver_id,
                    start_point_id=start_id,
                    end_point_id=end_id,
                    price_rub=150,
                    seats_total=2,
                    schedule_time="08:00",
                )

                trip_id = repo.templates.create_trip_from_template(
                    driver_id,
                    template_id,
                    trip_date="2099-07-15",
                    departure_time="10:30",
                )

                trip = repo.trips.get_trip_public_card(trip_id)
                self.assertEqual(trip["departure_time"], "10:30")
            finally:
                db.close()

    def test_create_trip_from_template_without_time_raises(self) -> None:
        """Ошибка, если нет времени ни в шаблоне, ни в параметрах."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            try:
                repo = Repo(db)
                driver_id = _setup_driver(repo)
                start_id, end_id = _setup_route(repo)

                template_id = repo.templates.create_template(
                    driver_id,
                    start_point_id=start_id,
                    end_point_id=end_id,
                    price_rub=120,
                    seats_total=4,
                )

                with self.assertRaisesRegex(ValueError, "Не указано время отправления"):
                    repo.templates.create_trip_from_template(
                        driver_id,
                        template_id,
                        trip_date="2099-08-01",
                    )
            finally:
                db.close()

    def test_create_trip_from_nonexistent_template_raises(self) -> None:
        """Ошибка при попытке создать поездку из несуществующего шаблона."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            try:
                repo = Repo(db)
                driver_id = _setup_driver(repo)

                with self.assertRaisesRegex(ValueError, "Шаблон не найден"):
                    repo.templates.create_trip_from_template(
                        driver_id,
                        9999,
                        trip_date="2099-09-01",
                        departure_time="12:00",
                    )
            finally:
                db.close()

    def test_delete_template(self) -> None:
        """Удаление шаблона работает корректно."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            try:
                repo = Repo(db)
                driver_id = _setup_driver(repo)
                start_id, end_id = _setup_route(repo)

                template_id = repo.templates.create_template(
                    driver_id,
                    start_point_id=start_id,
                    end_point_id=end_id,
                    price_rub=100,
                    seats_total=2,
                )

                deleted = repo.templates.delete_template(driver_id, template_id)
                self.assertTrue(deleted)

                template = repo.templates.get_template(driver_id, template_id)
                self.assertIsNone(template)
            finally:
                db.close()
