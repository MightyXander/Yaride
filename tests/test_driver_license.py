from __future__ import annotations

from datetime import date, timedelta
from tempfile import NamedTemporaryFile
from unittest import TestCase

from app.db import Database
from app.repo import Repo


class DriverKycRulesTests(TestCase):
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

    def test_upsert_driver_rejects_without_approved_didit(self) -> None:
        with self.assertRaisesRegex(ValueError, "KYC в Didit"):
            self.repo.upsert_user(1, "Driver", "driver1", "driver")

    def test_upsert_driver_allows_approved_didit(self) -> None:
        self.repo.upsert_user(
            2,
            "Verified Driver",
            "driver2",
            "driver",
            didit_session_id="didit_sess_1",
            didit_verification_status="Approved",
        )
        user = self.repo.get_user(2)
        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user["didit_verification_status"], "Approved")

    def test_create_trip_requires_approved_didit(self) -> None:
        self.repo.upsert_user(4, "Passenger", "passenger4", "passenger")
        ok, _ = self.repo.switch_role(4, "driver", date.today().isoformat())
        self.assertFalse(ok)

    def test_create_trip_allows_approved_didit(self) -> None:
        self.repo.upsert_user(
            3,
            "Valid Driver",
            "driver3",
            "driver",
            didit_session_id="didit_sess_2",
            didit_verification_status="Approved",
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
