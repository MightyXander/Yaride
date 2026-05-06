from __future__ import annotations

from datetime import date, timedelta
from tempfile import NamedTemporaryFile
from unittest import TestCase

from app.db import Database
from app.repo import Repo


class DriverLicenseRulesTests(TestCase):
    def setUp(self) -> None:
        self.db_file = NamedTemporaryFile(suffix=".db", delete=False)
        self.db_file.close()
        self.db = Database(self.db_file.name)
        self.db.init_schema()
        self.repo = Repo(self.db)
        self._seed_route_points()

    def tearDown(self) -> None:
        import os

        os.unlink(self.db_file.name)

    def _seed_route_points(self) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO route_points(locality, district, admin_area, title, kind) VALUES (?, ?, ?, ?, 'stop')",
                ("Ярославль", "Кировский", "Центр", "Старт",),
            )
            conn.execute(
                "INSERT INTO route_points(locality, district, admin_area, title, kind) VALUES (?, ?, ?, ?, 'stop')",
                ("Ярославль", "Фрунзенский", "Суздалка", "Финиш",),
            )

    def test_create_trip_rejects_driver_without_license_data(self) -> None:
        self.repo.upsert_user(1, "Driver", "driver1", "driver")
        with self.assertRaisesRegex(ValueError, "заполнить данные прав"):
            self.repo.create_trip(
                tg_driver_id=1,
                start_point_id=1,
                end_point_id=2,
                trip_date=(date.today() + timedelta(days=1)).isoformat(),
                departure_time="10:00",
                price_rub=100,
                seats_total=2,
            )

    def test_create_trip_rejects_expired_license(self) -> None:
        self.repo.upsert_user(
            2,
            "Expired Driver",
            "driver2",
            "driver",
            driver_license_number="77 77 123456",
            driver_license_valid_until=(date.today() - timedelta(days=1)).isoformat(),
        )
        with self.assertRaisesRegex(ValueError, "срок действия прав уже истёк"):
            self.repo.create_trip(
                tg_driver_id=2,
                start_point_id=1,
                end_point_id=2,
                trip_date=(date.today() + timedelta(days=1)).isoformat(),
                departure_time="10:00",
                price_rub=100,
                seats_total=2,
            )

    def test_create_trip_allows_valid_license(self) -> None:
        self.repo.upsert_user(
            3,
            "Valid Driver",
            "driver3",
            "driver",
            driver_license_number="77 77 123456",
            driver_license_valid_until=(date.today() + timedelta(days=365)).isoformat(),
        )
        trip_id = self.repo.create_trip(
            tg_driver_id=3,
            start_point_id=1,
            end_point_id=2,
            trip_date=(date.today() + timedelta(days=2)).isoformat(),
            departure_time="10:00",
            price_rub=150,
            seats_total=3,
        )
        self.assertGreater(trip_id, 0)
