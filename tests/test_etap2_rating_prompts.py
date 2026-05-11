from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import app.db as app_db
from app.db import Database
from app.repo import Repo


class _CountingConnection(sqlite3.Connection):
    """Подсчёт вызовов execute() (в Python 3.14 execute нельзя присваивать на объекте Connection)."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.execute_calls = 0

    def execute(self, sql: str, parameters: tuple[object, ...] | list[object] = ()) -> sqlite3.Cursor:  # type: ignore[override]
        self.execute_calls += 1
        return super().execute(sql, parameters)


class RatingPromptsSqlTests(TestCase):
    """Сценарии из спецификации этапа 2 для list_pending_rating_prompts (один SQL)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        db_path = Path(self._tmp.name) / "t.db"
        self.db = Database(str(db_path))
        self.addCleanup(self.db.close)
        self.db.init_schema()
        self.repo = Repo(self.db)

        with self.db.transaction() as conn:
            rp = conn.execute("SELECT id FROM route_points ORDER BY id LIMIT 2").fetchall()
            self.assertGreaterEqual(len(rp), 2)
            self.start_id = int(rp[0]["id"])
            self.end_id = int(rp[1]["id"])

            conn.execute(
                """
                INSERT INTO users(tg_user_id, name, username, role)
                VALUES (910001, 'Водитель', NULL, 'driver'),
                       (910002, 'Пассажир', NULL, 'passenger')
                """
            )
            d = conn.execute("SELECT id FROM users WHERE tg_user_id = 910001").fetchone()
            p = conn.execute("SELECT id FROM users WHERE tg_user_id = 910002").fetchone()
            assert d and p
            self.driver_iid = int(d["id"])
            self.pass_iid = int(p["id"])

    def _insert_trip(
        self,
        *,
        trip_date: str,
        departure_time: str,
        status: str = "open",
        passenger_tg: int | None = None,
    ) -> int:
        if passenger_tg is None:
            passenger_tg = 910002
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO trips(
                    driver_id, start_point_id, end_point_id,
                    trip_date, departure_time, time_slot,
                    price_rub, seats_total, seats_booked, status
                )
                VALUES (?, ?, ?, ?, ?, ?, 100, 2, 1, ?)
                """,
                (
                    self.driver_iid,
                    self.start_id,
                    self.end_id,
                    trip_date,
                    departure_time,
                    departure_time,
                    status,
                ),
            )
            tid = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            pid_row = conn.execute(
                "SELECT id FROM users WHERE tg_user_id = ?",
                (passenger_tg,),
            ).fetchone()
            assert pid_row
            pid = int(pid_row["id"])
            conn.execute(
                "INSERT INTO bookings(trip_id, passenger_id, status) VALUES (?, ?, 'active')",
                (tid, pid),
            )
            return tid

    def test_cancelled_trip_yields_no_prompts(self) -> None:
        self._insert_trip(
            trip_date="2026-06-01",
            departure_time="08:00",
            status="cancelled",
        )
        now = datetime(2026, 6, 1, 20, 0, 0)
        self.assertEqual(len(self.repo.list_pending_rating_prompts(now)), 0)

    def test_trip_within_three_hours_after_start_yields_no_prompts(self) -> None:
        """Отправление 17:00, сейчас 18:00 — до «отправление+3ч» ещё не прошло."""
        self._insert_trip(trip_date="2026-06-01", departure_time="17:00")
        now = datetime(2026, 6, 1, 18, 0, 0)
        self.assertEqual(len(self.repo.list_pending_rating_prompts(now)), 0)

    def test_eligible_trip_two_prompts_passenger_and_driver(self) -> None:
        self._insert_trip(trip_date="2026-06-01", departure_time="08:00")
        now = datetime(2026, 6, 1, 20, 0, 0)
        prompts = self.repo.list_pending_rating_prompts(now)
        self.assertEqual(len(prompts), 2)
        kinds = {(p.rater_user_id, p.rated_user_id) for p in prompts}
        self.assertIn((self.pass_iid, self.driver_iid), kinds)
        self.assertIn((self.driver_iid, self.pass_iid), kinds)

    def test_only_driver_prompt_when_passenger_already_rated(self) -> None:
        tid = self._insert_trip(trip_date="2026-06-01", departure_time="08:00")
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO trip_ratings(trip_id, rater_user_id, rated_user_id, stars)
                VALUES (?, ?, ?, 5)
                """,
                (tid, self.pass_iid, self.driver_iid),
            )
        now = datetime(2026, 6, 1, 20, 0, 0)
        prompts = self.repo.list_pending_rating_prompts(now)
        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0].rater_user_id, self.driver_iid)
        self.assertEqual(prompts[0].rated_user_id, self.pass_iid)

    def test_no_prompts_when_rating_prompt_already_sent(self) -> None:
        tid = self._insert_trip(trip_date="2026-06-01", departure_time="08:00")
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO rating_prompts_sent(trip_id, rater_user_id, rated_user_id)
                VALUES (?, ?, ?)
                """,
                (tid, self.pass_iid, self.driver_iid),
            )
            conn.execute(
                """
                INSERT INTO rating_prompts_sent(trip_id, rater_user_id, rated_user_id)
                VALUES (?, ?, ?)
                """,
                (tid, self.driver_iid, self.pass_iid),
            )
        now = datetime(2026, 6, 1, 20, 0, 0)
        self.assertEqual(len(self.repo.list_pending_rating_prompts(now)), 0)

    def test_second_passenger_one_prompt_when_first_finished_mutual_ratings(self) -> None:
        """Два пассажира: первый и водитель полностью обменялись оценками; у второго только p→d — один prompt (d→p)."""
        tid = self._insert_trip(trip_date="2026-06-01", departure_time="08:00")
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO users(tg_user_id, name, username, role)
                VALUES (910003, 'Пассажир2', NULL, 'passenger')
                """
            )
            p2 = conn.execute("SELECT id FROM users WHERE tg_user_id = 910003").fetchone()
            assert p2
            p2_iid = int(p2["id"])
            conn.execute(
                "INSERT INTO bookings(trip_id, passenger_id, status) VALUES (?, ?, 'active')",
                (tid, p2_iid),
            )
            conn.execute(
                """
                INSERT INTO trip_ratings(trip_id, rater_user_id, rated_user_id, stars)
                VALUES (?, ?, ?, 5)
                """,
                (tid, self.pass_iid, self.driver_iid),
            )
            conn.execute(
                """
                INSERT INTO trip_ratings(trip_id, rater_user_id, rated_user_id, stars)
                VALUES (?, ?, ?, 4)
                """,
                (tid, self.driver_iid, self.pass_iid),
            )
            conn.execute(
                """
                INSERT INTO trip_ratings(trip_id, rater_user_id, rated_user_id, stars)
                VALUES (?, ?, ?, 5)
                """,
                (tid, p2_iid, self.driver_iid),
            )
        now = datetime(2026, 6, 1, 20, 0, 0)
        prompts = self.repo.list_pending_rating_prompts(now)
        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0].rater_user_id, self.driver_iid)
        self.assertEqual(prompts[0].rated_user_id, p2_iid)

    def test_list_pending_rating_prompts_single_select_under_three_executes(self) -> None:
        """Один SELECT в методе; вместе с BEGIN транзакции — не более трёх вызовов execute()."""
        orig_connect = app_db.sqlite3.connect

        def connect_counting(database: str, **kwargs: object) -> sqlite3.Connection:
            kwargs = dict(kwargs)
            kwargs["factory"] = _CountingConnection
            return orig_connect(database, **kwargs)

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db_path = Path(tmp.name) / "count.db"

        with patch.object(app_db.sqlite3, "connect", connect_counting):
            db = Database(str(db_path))
            self.addCleanup(db.close)
            db.init_schema()
            repo = Repo(db)
            rp = db.connect().execute("SELECT id FROM route_points ORDER BY id LIMIT 2").fetchall()
            start_id = int(rp[0]["id"])
            end_id = int(rp[1]["id"])
            with db.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO users(tg_user_id, name, username, role)
                    VALUES (910001, 'Водитель', NULL, 'driver'),
                           (910002, 'Пассажир', NULL, 'passenger')
                    """
                )
                d = conn.execute("SELECT id FROM users WHERE tg_user_id = 910001").fetchone()
                p = conn.execute("SELECT id FROM users WHERE tg_user_id = 910002").fetchone()
                assert d and p
                driver_iid = int(d["id"])
                conn.execute(
                    """
                    INSERT INTO trips(
                        driver_id, start_point_id, end_point_id,
                        trip_date, departure_time, time_slot,
                        price_rub, seats_total, seats_booked, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 100, 2, 1, 'open')
                    """,
                    (driver_iid, start_id, end_id, "2026-06-01", "08:00", "08:00"),
                )
                tid = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
                conn.execute(
                    "INSERT INTO bookings(trip_id, passenger_id, status) VALUES (?, ?, 'active')",
                    (tid, int(p["id"])),
                )

            raw = db.connect()
            assert isinstance(raw, _CountingConnection)
            raw.execute_calls = 0

            now = datetime(2026, 6, 1, 20, 0, 0)
            repo.list_pending_rating_prompts(now)
            self.assertLessEqual(raw.execute_calls, 3)
