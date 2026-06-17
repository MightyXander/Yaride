from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import TestCase

from app.analytics import (
    EVENT_BOOKING_CREATED,
    EVENT_SEARCH,
    record_event,
)
from app.db import Database
from app.repo import TripRepository


def _make_db(tmp: str) -> Database:
    db = Database(str(Path(tmp) / "analytics.db"))
    db.init_schema()
    return db


class AnalyticsSchemaTests(TestCase):
    def test_analytics_events_table_exists_after_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            try:
                with db.transaction() as conn:
                    row = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'analytics_events'"
                    ).fetchone()
                self.assertIsNotNone(row, "таблица analytics_events должна создаваться при init_schema")
            finally:
                db.close()


class RecordEventTests(TestCase):
    def test_record_event_persists_row_with_props(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            try:
                record_event(db, EVENT_BOOKING_CREATED, tg_user_id=777, props={"trip_id": 5})
                with db.transaction() as conn:
                    row = conn.execute("SELECT event, tg_user_id, props FROM analytics_events").fetchone()
                self.assertEqual(row["event"], EVENT_BOOKING_CREATED)
                self.assertEqual(int(row["tg_user_id"]), 777)
                self.assertEqual(json.loads(row["props"]), {"trip_id": 5})
            finally:
                db.close()

    def test_record_event_is_best_effort_and_never_raises(self) -> None:
        """Сломанный db не должен пробрасывать исключение из record_event."""

        class BrokenDb:
            def transaction(self):  # noqa: ANN001
                raise RuntimeError("db down")

        # Не должно бросить — ошибка глотается.
        record_event(BrokenDb(), EVENT_SEARCH, props={"results": 0})


class SearchEventInstrumentationTests(TestCase):
    def test_find_open_trips_records_search_event_with_result_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            try:
                trips = TripRepository(db)
                result = trips.find_open_trips(trip_date="2099-01-01")
                self.assertEqual(result, [])  # пустая БД

                with db.transaction() as conn:
                    row = conn.execute(
                        "SELECT event, props FROM analytics_events WHERE event = ?",
                        (EVENT_SEARCH,),
                    ).fetchone()
                self.assertIsNotNone(row, "поиск должен записывать событие search")
                props = json.loads(row["props"])
                self.assertEqual(props["results"], 0)  # пустой поиск (search_empty)
            finally:
                db.close()


class FunnelQueryTests(TestCase):
    def test_can_build_search_to_booking_funnel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            try:
                record_event(db, EVENT_SEARCH, props={"results": 3})
                record_event(db, EVENT_SEARCH, props={"results": 0})
                record_event(db, EVENT_BOOKING_CREATED, tg_user_id=1, props={"trip_id": 2})

                with db.transaction() as conn:
                    counts = {
                        r["event"]: int(r["cnt"])
                        for r in conn.execute(
                            "SELECT event, COUNT(*) AS cnt FROM analytics_events GROUP BY event"
                        ).fetchall()
                    }
                self.assertEqual(counts.get(EVENT_SEARCH), 2)
                self.assertEqual(counts.get(EVENT_BOOKING_CREATED), 1)
            finally:
                db.close()
