"""Карта остановок в админке: сериализация маркеров."""

from __future__ import annotations

import sqlite3
import unittest

from admin.geo_map import map_center_for_point, stops_for_admin_map


def _fake_stop_row(**fields) -> sqlite3.Row:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE route_points (
            id INTEGER, locality TEXT, district TEXT, admin_area TEXT,
            title TEXT, latitude REAL, longitude REAL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO route_points(id, locality, district, admin_area, title, latitude, longitude)
        VALUES (:id, :locality, :district, :admin_area, :title, :latitude, :longitude)
        """,
        {
            "id": fields.get("id", 1),
            "locality": fields.get("locality", "Ярославль"),
            "district": fields.get("district", "Ленинский район"),
            "admin_area": fields.get("admin_area", "Центр"),
            "title": fields.get("title", "Тест"),
            "latitude": fields.get("latitude"),
            "longitude": fields.get("longitude"),
        },
    )
    row = conn.execute("SELECT * FROM route_points").fetchone()
    conn.close()
    assert row is not None
    return row


class AdminGeoMapTests(unittest.TestCase):
    def test_stops_for_admin_map_uses_saved_coords(self) -> None:
        row = _fake_stop_row(id=7, latitude=57.63, longitude=39.87)
        out = stops_for_admin_map([row])
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["saved"])
        self.assertEqual(out[0]["latitude"], 57.63)

    def test_stops_for_admin_map_estimates_missing_coords(self) -> None:
        row = _fake_stop_row(id=8, latitude=None, longitude=None)
        out = stops_for_admin_map([row])
        self.assertFalse(out[0]["saved"])
        self.assertGreater(out[0]["latitude"], 57.0)
        self.assertGreater(out[0]["longitude"], 39.0)

    def test_map_center_for_point(self) -> None:
        lat, lng, saved = map_center_for_point(latitude=57.1, longitude=39.2)
        self.assertTrue(saved)
        self.assertEqual(lat, 57.1)


if __name__ == "__main__":
    unittest.main()
