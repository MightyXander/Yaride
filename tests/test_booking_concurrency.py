from __future__ import annotations

import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest import TestCase

from app.db import Database
from app.repo import Repo


class BookingConcurrencyTests(TestCase):
    def test_last_seat_single_winner_under_parallel_booking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "race.db"
            db = Database(str(db_path))
            try:
                db.init_schema()
                repo = Repo(db)

                with db.transaction() as conn:
                    rp = conn.execute(
                        "SELECT id FROM route_points ORDER BY id LIMIT 2"
                    ).fetchall()
                    self.assertGreaterEqual(len(rp), 2, "need two route points")
                    start_id = int(rp[0]["id"])
                    end_id = int(rp[1]["id"])

                    conn.execute(
                        """
                        INSERT INTO users(tg_user_id, name, username, role)
                        VALUES (910001, 'Driver', NULL, 'driver')
                        """
                    )
                    driver_row = conn.execute(
                        "SELECT id FROM users WHERE tg_user_id = 910001"
                    ).fetchone()
                    assert driver_row is not None
                    driver_internal = int(driver_row["id"])

                    passenger_tg_start = 910100
                    for i in range(25):
                        tg = passenger_tg_start + i
                        conn.execute(
                            """
                            INSERT INTO users(tg_user_id, name, username, role)
                            VALUES (?, ?, NULL, 'passenger')
                            """,
                            (tg, f"P{i}"),
                        )

                    conn.execute(
                        """
                        INSERT INTO trips(
                            driver_id, start_point_id, end_point_id,
                            trip_date, departure_time, time_slot,
                            price_rub, seats_total, seats_booked, status
                        )
                        VALUES (?, ?, ?, '2099-01-15', '18:00', '18:00', 100, 1, 0, 'open')
                        """,
                        (driver_internal, start_id, end_id),
                    )
                    trip_row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
                    trip_id = int(trip_row["id"])

                passenger_ids = list(range(passenger_tg_start, passenger_tg_start + 25))

                def try_book(tg: int) -> tuple[int, str | None]:
                    try:
                        bid = repo.create_booking(tg, trip_id)
                        return bid, None
                    except ValueError as exc:
                        return -1, str(exc)

                successes = 0
                no_seat_msgs = 0
                with ThreadPoolExecutor(max_workers=20) as pool:
                    futures = [pool.submit(try_book, tg) for tg in passenger_ids]
                    for fut in as_completed(futures):
                        _bid, err = fut.result()
                        if err is None:
                            successes += 1
                        elif "Свободных мест нет" in (err or ""):
                            no_seat_msgs += 1

                self.assertEqual(successes, 1, "exactly one booking must succeed")
                self.assertGreater(no_seat_msgs, 0)

                with db.transaction() as conn:
                    row = conn.execute(
                        "SELECT seats_booked, seats_total FROM trips WHERE id = ?",
                        (trip_id,),
                    ).fetchone()
                    self.assertIsNotNone(row)
                    self.assertEqual(int(row["seats_booked"]), 1)
                    self.assertEqual(int(row["seats_total"]), 1)
            finally:
                db.close()
