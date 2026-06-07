"""Интеграционные тесты Mini App API (FastAPI TestClient, dev-пользователь без Telegram)."""

from __future__ import annotations

import gc
import os
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient

    _HAS_HTTPX = True
except Exception:  # pragma: no cover - httpx может отсутствовать локально
    _HAS_HTTPX = False

from app.db import Database
from webapp_api.app import create_app
from webapp_api.config import WebAppSettings


def _cleanup(path: str) -> None:
    for ext in ("", "-wal", "-shm", "-journal"):
        try:
            os.unlink(path + ext)
        except OSError:
            pass


@unittest.skipUnless(_HAS_HTTPX, "httpx (TestClient) недоступен")
class WebAppApiTests(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        Database(self.path).close()  # bootstrap schema
        self.settings = WebAppSettings(
            bot_token="test-token",
            db_path=self.path,
            dev_user_id=900001,
        )
        self.app = create_app(self.settings)
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        gc.collect()
        _cleanup(self.path)

    def test_health(self) -> None:
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_me_unregistered_then_register_passenger(self) -> None:
        r = self.client.get("/api/me")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["registered"])

        r = self.client.post("/api/register", json={"name": "Тест", "role": "passenger"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["registered"])
        self.assertEqual(r.json()["user"]["role"], "passenger")

        r = self.client.get("/api/me")
        self.assertTrue(r.json()["registered"])

    def test_register_driver_with_car_and_districts(self) -> None:
        r = self.client.post(
            "/api/register",
            json={
                "name": "Водитель",
                "role": "driver",
                "dl_series_number": "9916АВ123456",
                "dl_valid_until": "2030-01-01",
                "car_model": "Kia Rio",
                "car_color": "Белый",
                "car_plate": "У723КВ",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        user = r.json()["user"]
        self.assertEqual(user["carModel"], "Kia Rio")
        self.assertEqual(user["carPlate"], "У723КВ")

        r = self.client.get("/api/catalog/districts")
        self.assertEqual(r.status_code, 200)
        districts = r.json()["districts"]
        self.assertIn("Кировский район", districts)

    def test_search_empty(self) -> None:
        r = self.client.get("/api/trips")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["trips"], [])

    def _register_driver(self) -> None:
        r = self.client.post(
            "/api/register",
            json={
                "name": "Водитель",
                "role": "driver",
                "dl_series_number": "9916АВ123456",
                "dl_valid_until": "2030-01-01",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)

    def _first_two_stop_ids(self) -> tuple[int, int]:
        districts = self.client.get("/api/catalog/districts").json()["districts"]
        stops = self.client.get(f"/api/catalog/stops?district={districts[0]}").json()["stops"]
        return stops[0]["id"], stops[1]["id"]

    def test_create_trip_then_search_finds_it(self) -> None:
        self._register_driver()
        a, b = self._first_two_stop_ids()
        r = self.client.post(
            "/api/trips",
            json={
                "start_point_id": a,
                "end_point_id": b,
                "trip_date": "2099-01-01",
                "departure_time": "08:00",
                "price_rub": 150,
                "seats_total": 3,
                "comment": "Тестовый комментарий",
            },
        )
        self.assertEqual(r.status_code, 201, r.text)
        trip_id = r.json()["id"]

        found = self.client.get(f"/api/trips?start_point={a}&end_point={b}").json()["trips"]
        self.assertTrue(any(t["id"] == trip_id for t in found))

        details = self.client.get(f"/api/trips/{trip_id}").json()
        self.assertEqual(details["comment"], "Тестовый комментарий")

    def test_template_create_list_publish_delete(self) -> None:
        self._register_driver()
        a, b = self._first_two_stop_ids()
        r = self.client.post(
            "/api/templates",
            json={"start_point_id": a, "end_point_id": b, "price_rub": 150, "seats_total": 3, "comment": "Коммьют"},
        )
        self.assertEqual(r.status_code, 201, r.text)
        tpl_id = r.json()["id"]

        tpls = self.client.get("/api/templates").json()["templates"]
        self.assertEqual(len(tpls), 1)
        self.assertEqual(tpls[0]["priceRub"], 150)

        r = self.client.post(
            f"/api/templates/{tpl_id}/publish",
            json={"trip_date": "2099-02-02", "departure_time": "09:00"},
        )
        self.assertEqual(r.status_code, 201, r.text)
        trip_id = r.json()["id"]
        details = self.client.get(f"/api/trips/{trip_id}").json()
        self.assertEqual(details["priceRub"], 150)
        self.assertEqual(details["comment"], "Коммьют")

        r = self.client.delete(f"/api/templates/{tpl_id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/api/templates").json()["templates"], [])

    def test_favorites_add_list_delete(self) -> None:
        self._register_driver()
        a, b = self._first_two_stop_ids()
        r = self.client.post("/api/favorites", json={"start_point_id": a, "end_point_id": b})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertTrue(r.json()["added"])

        favs = self.client.get("/api/favorites").json()["favorites"]
        self.assertEqual(len(favs), 1)

        fav_id = favs[0]["id"]
        r = self.client.delete(f"/api/favorites/{fav_id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/api/favorites").json()["favorites"], [])


if __name__ == "__main__":
    unittest.main()
