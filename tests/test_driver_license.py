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
                ("Ярославль", "Кировский", "Центр", "Старт"),
            )
            conn.execute(
                "INSERT INTO route_points(locality, district, admin_area, title, kind) VALUES (?, ?, ?, ?, 'stop')",
                ("Ярославль", "Фрунзенский", "Суздалка", "Финиш"),
            )

    def test_register_driver_requires_license_and_trip_allowed(self) -> None:
        self.repo.register_driver_with_license(
            10,
            "Иван",
            "ivan",
            "77 77 123456",
            date.today() + timedelta(days=400),
        )
        trip_id = self.repo.create_trip(
            tg_driver_id=10,
            start_point_id=1,
            end_point_id=2,
            trip_date=(date.today() + timedelta(days=3)).isoformat(),
            departure_time="12:00",
            price_rub=150,
            seats_total=3,
        )
        self.assertGreater(trip_id, 0)

    def test_create_trip_without_license_row_fails(self) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO users(tg_user_id, name, username, role)
                VALUES (11, 'Водитель', 'drv', 'driver')
                """
            )
        with self.assertRaisesRegex(ValueError, "водительском удостоверении"):
            self.repo.create_trip(
                tg_driver_id=11,
                start_point_id=1,
                end_point_id=2,
                trip_date=(date.today() + timedelta(days=3)).isoformat(),
                departure_time="12:00",
                price_rub=150,
                seats_total=3,
            )

    def test_identity_row_created_for_new_user(self) -> None:
        self.repo.upsert_user(12, "Пассажир", "pas", "passenger")
        with self.db.transaction() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c FROM user_identities
                WHERE provider = 'telegram' AND external_uid = '12'
                """
            ).fetchone()
        self.assertEqual(int(row["c"]), 1)
