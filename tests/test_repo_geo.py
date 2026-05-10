from __future__ import annotations

from contextlib import contextmanager
from unittest import TestCase

from app.repo import RouteRepository


class _FakeConn:
    def __init__(self, stops_rows: list[dict], locality_rows: list[dict] | None = None) -> None:
        self._stops_rows = stops_rows
        self._locality_rows = locality_rows if locality_rows is not None else stops_rows

    def execute(self, query: str, *args, **kwargs):
        class _R:
            def __init__(self, rows):
                self._rows = rows

            def fetchall(self):
                return self._rows

        q = query.strip()
        if "SELECT * FROM route_points" in q:
            return _R(self._stops_rows)
        if "SELECT locality, latitude, longitude FROM route_points" in q:
            return _R(self._locality_rows)
        return _R([])


class _FakeDatabase:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    @contextmanager
    def transaction(self):
        yield self._conn


class RouteRepositoryGeoTests(TestCase):
    def test_nearest_stops_ranked_skips_null_coords_and_sorts(self) -> None:
        routes = RouteRepository.__new__(RouteRepository)
        rows = [
            {"latitude": None, "longitude": 39.87, "id": 1},
            {"latitude": 57.70, "longitude": 39.87, "id": 2},
            {"latitude": 57.62, "longitude": 39.87, "id": 3},
        ]
        out = RouteRepository.nearest_stops_ranked(routes, 57.62, 39.87, rows, limit=5)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0][1], 0.0)
        self.assertEqual(int(out[0][0]["id"]), 3)

    def test_nearest_stops_global_filters_by_max_km(self) -> None:
        rows = [
            {"id": 1, "kind": "stop", "latitude": 57.62, "longitude": 39.87, "title": "Near"},
            {"id": 2, "kind": "stop", "latitude": 41.0, "longitude": 39.87, "title": "Far"},
        ]
        repo = RouteRepository(_FakeDatabase(_FakeConn(rows)))
        out = repo.nearest_stops_global(57.62, 39.87, limit=5, max_km=85.0)
        self.assertEqual(len(out), 1)
        self.assertEqual(int(out[0][0]["id"]), 1)

    def test_nearest_locality_from_geo_returns_closest(self) -> None:
        rows = [
            {"locality": "Ярославль", "latitude": 57.62, "longitude": 39.87},
            {"locality": "Рыбинск", "latitude": 58.05, "longitude": 38.85},
        ]
        repo = RouteRepository(_FakeDatabase(_FakeConn(rows, locality_rows=rows)))
        got = repo.nearest_locality_from_geo(57.62, 39.87, max_km=500.0)
        self.assertIsNotNone(got)
        assert got is not None
        self.assertEqual(got[0], "Ярославль")

    def test_nearest_locality_from_geo_returns_none_when_too_far(self) -> None:
        rows = [{"locality": "Дальний", "latitude": 41.0, "longitude": 39.87}]
        repo = RouteRepository(_FakeDatabase(_FakeConn(rows, locality_rows=rows)))
        got = repo.nearest_locality_from_geo(57.62, 39.87, max_km=10.0)
        self.assertIsNone(got)
