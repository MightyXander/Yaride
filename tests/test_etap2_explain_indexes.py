"""EXPLAIN QUERY PLAN: типовые запросы используют индексы этапа 2 (USING INDEX …)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

from app.db import Database


def _plan_details(conn: Database, sql: str, params: tuple[object, ...] = ()) -> list[str]:
    with conn.transaction() as c:
        rows = c.execute(f"EXPLAIN QUERY PLAN {sql}", params).fetchall()
    return [str(r["detail"]) for r in rows]


class Etap2ExplainIndexesTests(TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        path = Path(self._tmp.name) / "explain.db"
        self.db = Database(str(path))
        self.addCleanup(self.db.close)
        self.db.init_schema()

    def test_idx_trips_status_date_route_used_for_find_open_trips(self) -> None:
        sql = """
            SELECT t.id
            FROM trips t
            JOIN route_points sp ON sp.id = t.start_point_id
            JOIN route_points ep ON ep.id = t.end_point_id
            JOIN users u ON u.id = t.driver_id
            WHERE t.status = 'open'
              AND t.start_point_id = ?
              AND t.end_point_id = ?
              AND t.trip_date = ?
            ORDER BY t.id DESC LIMIT 25
        """
        details = _plan_details(self.db, sql, (1, 2, "2026-06-01"))
        joined = "\n".join(details)
        self.assertIn("idx_trips_status_date_route", joined)

    def test_idx_bookings_passenger_status_used(self) -> None:
        sql = """
            SELECT b.id
            FROM bookings b
            JOIN trips t ON t.id = b.trip_id
            WHERE b.passenger_id = ?
            ORDER BY b.id DESC
        """
        details = _plan_details(self.db, sql, (1,))
        joined = "\n".join(details)
        self.assertIn("idx_bookings_passenger_status", joined)

    def test_idx_bookings_trip_status_used_for_driver_trip_bookings(self) -> None:
        sql = """
            SELECT b.id
            FROM bookings b
            JOIN trips t ON t.id = b.trip_id
            JOIN users dr ON dr.id = t.driver_id
            JOIN users p ON p.id = b.passenger_id
            WHERE t.id = ? AND dr.tg_user_id = ? AND b.status = 'active'
            ORDER BY b.id
        """
        details = _plan_details(self.db, sql, (1, 910001))
        joined = "\n".join(details)
        self.assertIn("idx_bookings_trip_status", joined)

    def test_idx_trip_ratings_rated_used_for_avg_by_rated_user(self) -> None:
        sql = "SELECT AVG(stars) FROM trip_ratings WHERE rated_user_id = ?"
        details = _plan_details(self.db, sql, (1,))
        joined = "\n".join(details)
        self.assertIn("idx_trip_ratings_rated", joined)

    def test_idx_trip_ratings_trip_rater_rated_used_for_prefix_lookup(self) -> None:
        sql = "SELECT id FROM trip_ratings WHERE trip_id = ? AND rater_user_id = ?"
        details = _plan_details(self.db, sql, (1, 2))
        joined = "\n".join(details)
        self.assertIn("idx_trip_ratings_trip_rater_rated", joined)

    def test_idx_rating_prompts_trip_rater_rated_used_for_prefix_lookup(self) -> None:
        # Двухколоночный префикс — не покрывается implicit PK, план выбирает явный индекс этапа 2.
        sql = "SELECT 1 FROM rating_prompts_sent WHERE trip_id = ? AND rater_user_id = ?"
        details = _plan_details(self.db, sql, (1, 2))
        joined = "\n".join(details)
        self.assertIn("idx_rating_prompts_trip_rater_rated", joined)
