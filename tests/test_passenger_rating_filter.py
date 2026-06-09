"""Фильтр по рейтингу пассажиров: по умолчанию выключен (NULL / <= 0)."""

from __future__ import annotations

import gc
import os
import sqlite3
import tempfile
import unittest

from app.db import CURRENT_SCHEMA_VERSION, Database
from app.formatting import effective_min_passenger_rating


def _cleanup(path: str) -> None:
    for ext in ("", "-wal", "-shm", "-journal"):
        try:
            os.unlink(path + ext)
        except OSError:
            pass


class EffectiveMinPassengerRatingTests(unittest.TestCase):
    def test_none_and_zero_mean_off(self) -> None:
        self.assertIsNone(effective_min_passenger_rating(None))
        self.assertIsNone(effective_min_passenger_rating(0))
        self.assertIsNone(effective_min_passenger_rating(-1))
        self.assertIsNone(effective_min_passenger_rating("0"))

    def test_positive_rounded(self) -> None:
        self.assertEqual(effective_min_passenger_rating(4.5), 4.5)
        self.assertEqual(effective_min_passenger_rating(4.49), 4.5)


class PassengerRatingFilterMigrationTests(unittest.TestCase):
    def test_current_schema_version_at_least_11(self) -> None:
        self.assertGreaterEqual(CURRENT_SCHEMA_VERSION, 11)

    def test_fresh_user_has_no_threshold(self) -> None:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db = Database(path)
        try:
            db.init_schema()
            with sqlite3.connect(path) as conn:
                conn.row_factory = sqlite3.Row
                cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
                self.assertIn("min_passenger_rating", cols)
                conn.execute(
                    "INSERT INTO users(tg_user_id, name, role) VALUES (1, 'U', 'driver')"
                )
                conn.commit()
                row = conn.execute(
                    "SELECT min_passenger_rating FROM users WHERE tg_user_id = 1"
                ).fetchone()
                self.assertIsNone(row["min_passenger_rating"])
        finally:
            db.close()
            gc.collect()
            _cleanup(path)

    def test_v10_to_v11_clears_thresholds(self) -> None:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            seed_conn = sqlite3.connect(path)
            try:
                seed_conn.executescript(
                    """
                    CREATE TABLE schema_version (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        version INTEGER NOT NULL
                    );
                    INSERT INTO schema_version(id, version) VALUES (1, 10);
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tg_user_id INTEGER UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        role TEXT NOT NULL,
                        min_passenger_rating REAL,
                        driver_moderation_status TEXT NOT NULL DEFAULT 'approved'
                    );
                    INSERT INTO users(tg_user_id, name, role, min_passenger_rating)
                    VALUES (111, 'Водитель', 'driver', 4.5);
                    """
                )
                seed_conn.commit()
            finally:
                seed_conn.close()

            db = Database(path)
            try:
                db.init_schema()
                with sqlite3.connect(path) as conn:
                    conn.row_factory = sqlite3.Row
                    ver = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[
                        "version"
                    ]
                    self.assertGreaterEqual(int(ver), 11)
                    row = conn.execute(
                        "SELECT min_passenger_rating FROM users WHERE tg_user_id = 111"
                    ).fetchone()
                    self.assertIsNone(row["min_passenger_rating"])
            finally:
                db.close()
        finally:
            gc.collect()
            _cleanup(path)


if __name__ == "__main__":
    unittest.main()
