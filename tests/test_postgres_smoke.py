"""Smoke-тесты PostgreSQL (опционально: TEST_DATABASE_URL в CI)."""

from __future__ import annotations

import os
import unittest

from app.database import open_database
from app.repo import Repo


def _postgres_url() -> str | None:
    return os.getenv("TEST_DATABASE_URL", "").strip() or None


@unittest.skipUnless(_postgres_url(), "TEST_DATABASE_URL не задан")
class PostgresSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        url = _postgres_url()
        assert url is not None
        cls._db = open_database(database_url=url)
        cls._db.init_schema()
        cls.repo = Repo(cls._db)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._db.close()

    def test_create_booking_on_postgres(self) -> None:
        with self._db.transaction() as conn:
            rp = conn.execute("SELECT id FROM route_points ORDER BY id LIMIT 2").fetchall()
            self.assertGreaterEqual(len(rp), 2)
            start_id = int(rp[0]["id"])
            end_id = int(rp[1]["id"])
            conn.execute(
                """
                INSERT INTO users(tg_user_id, name, username, role)
                VALUES (990001, 'PgDriver', NULL, 'driver')
                ON CONFLICT DO NOTHING
                """
            )
            conn.execute(
                """
                INSERT INTO users(tg_user_id, name, username, role)
                VALUES (990002, 'PgPassenger', NULL, 'passenger')
                ON CONFLICT DO NOTHING
                """
            )
            driver = conn.execute("SELECT id FROM users WHERE tg_user_id = 990001").fetchone()
            assert driver is not None
            trip_id = self.repo.trips.create_trip(
                990001,
                start_id,
                end_id,
                "2099-06-01",
                "10:00",
                150,
                2,
            )
            booking_id = self.repo.bookings.create_booking(990002, trip_id)
            self.assertGreater(booking_id, 0)

    def test_submit_rating_on_postgres(self) -> None:
        with self._db.transaction() as conn:
            rp = conn.execute("SELECT id FROM route_points ORDER BY id LIMIT 2").fetchall()
            start_id = int(rp[0]["id"])
            end_id = int(rp[1]["id"])
            conn.execute(
                """
                INSERT INTO users(tg_user_id, name, username, role)
                VALUES (990011, 'PgRateDriver', NULL, 'driver')
                ON CONFLICT DO NOTHING
                """
            )
            conn.execute(
                """
                INSERT INTO users(tg_user_id, name, username, role)
                VALUES (990012, 'PgRatePassenger', NULL, 'passenger')
                ON CONFLICT DO NOTHING
                """
            )
            driver = conn.execute("SELECT id FROM users WHERE tg_user_id = 990011").fetchone()
            passenger = conn.execute("SELECT id FROM users WHERE tg_user_id = 990012").fetchone()
            assert driver is not None and passenger is not None
            trip_id = self.repo.trips.create_trip(
                990011,
                start_id,
                end_id,
                "2020-01-01",
                "08:00",
                200,
                2,
            )
            self.repo.bookings.create_booking(990012, trip_id)

        self.repo.ratings.submit_rating(
            rater_tg_user_id=990012,
            trip_id=trip_id,
            rated_tg_user_id=990011,
            stars=5,
            review_text="Postgres smoke",
        )
        rows = self.repo.ratings.list_ratings_received(990011)
        self.assertTrue(any(int(r["stars"]) == 5 for r in rows))


if __name__ == "__main__":
    unittest.main()
