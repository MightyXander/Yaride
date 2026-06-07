"""Миграция v7: удаление городов кроме Ярославля и связанных данных."""

from __future__ import annotations

import gc
import os
import sqlite3
import tempfile
import unittest

from app.db import CURRENT_SCHEMA_VERSION, Database


def _cleanup(path: str) -> None:
    for ext in ("", "-wal", "-shm", "-journal"):
        try:
            os.unlink(path + ext)
        except OSError:
            pass


class YaroslavlOnlyMigrationTests(unittest.TestCase):
    def test_current_schema_version_at_least_7(self) -> None:
        self.assertGreaterEqual(CURRENT_SCHEMA_VERSION, 7)

    def test_fresh_db_has_only_yaroslavl_points(self) -> None:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db = Database(path)
        try:
            db.init_schema()
            with sqlite3.connect(path) as conn:
                conn.row_factory = sqlite3.Row
                localities = {r["locality"] for r in conn.execute("SELECT DISTINCT locality FROM route_points")}
                self.assertEqual(localities, {"Ярославль"})
        finally:
            db.close()
            gc.collect()
            _cleanup(path)

    def test_v6_db_migrates_to_v7_removes_non_yaroslavl(self) -> None:
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
                    INSERT INTO schema_version(id, version) VALUES (1, 6);
                    CREATE TABLE route_points (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        locality TEXT NOT NULL,
                        district TEXT,
                        admin_area TEXT,
                        title TEXT NOT NULL,
                        kind TEXT NOT NULL DEFAULT 'stop',
                        latitude REAL,
                        longitude REAL
                    );
                    INSERT INTO route_points(locality, district, admin_area, title)
                        VALUES ('Ярославль', 'Кировский район', 'Центр', 'Площадь Труда');
                    INSERT INTO route_points(locality, district, admin_area, title)
                        VALUES ('Рыбинск', 'Город', 'Центр', 'Автовокзал');
                    INSERT INTO route_points(locality, district, admin_area, title)
                        VALUES ('Тутаев', 'Город', 'Центр', 'Центр');

                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tg_user_id INTEGER UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        role TEXT NOT NULL,
                        is_banned INTEGER NOT NULL DEFAULT 0
                    );
                    INSERT INTO users(tg_user_id, name, role) VALUES (111, 'Водитель', 'driver');

                    CREATE TABLE trips (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        driver_id INTEGER NOT NULL,
                        start_point_id INTEGER NOT NULL,
                        end_point_id INTEGER NOT NULL,
                        trip_date TEXT NOT NULL,
                        departure_time TEXT,
                        time_slot TEXT,
                        price_rub INTEGER,
                        seats_total INTEGER,
                        seats_booked INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'open'
                    );
                    INSERT INTO trips(driver_id, start_point_id, end_point_id, trip_date)
                        VALUES (1, 2, 3, '2099-01-01');

                    CREATE TABLE bookings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trip_id INTEGER NOT NULL,
                        passenger_id INTEGER,
                        status TEXT DEFAULT 'active'
                    );
                    INSERT INTO bookings(trip_id, passenger_id) VALUES (1, 1);

                    CREATE TABLE trip_ratings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trip_id INTEGER NOT NULL,
                        rater_user_id INTEGER NOT NULL,
                        rated_user_id INTEGER NOT NULL,
                        stars INTEGER NOT NULL
                    );
                    INSERT INTO trip_ratings(trip_id, rater_user_id, rated_user_id, stars) VALUES (1, 1, 1, 5);

                    CREATE TABLE favorite_routes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        start_point_id INTEGER NOT NULL,
                        end_point_id INTEGER NOT NULL
                    );
                    INSERT INTO favorite_routes(user_id, start_point_id, end_point_id) VALUES (1, 2, 3);
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
                    ver = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()["version"]
                    self.assertGreaterEqual(int(ver), 7)

                    localities = {r["locality"] for r in conn.execute("SELECT DISTINCT locality FROM route_points")}
                    self.assertEqual(localities, {"Ярославль"})

                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0], 0)
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0], 0)
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM trip_ratings").fetchone()[0], 0)
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM favorite_routes").fetchone()[0], 0)
            finally:
                db.close()
        finally:
            gc.collect()
            _cleanup(path)


if __name__ == "__main__":
    unittest.main()
