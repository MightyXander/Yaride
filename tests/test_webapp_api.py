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
        self.assertEqual(user["driverModerationStatus"], "pending")
        self.assertFalse(user["isActiveDriver"])

        r = self.client.get("/api/catalog/districts")
        self.assertEqual(r.status_code, 200)
        districts = r.json()["districts"]
        self.assertIn("Кировский район", districts)

    def test_search_empty(self) -> None:
        r = self.client.get("/api/trips")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["trips"], [])
        self.assertEqual(body["searchScope"], "exact")

    def _stops_pair_in_two_districts(self) -> tuple[str, str, int, int, int, int]:
        districts = self.client.get("/api/catalog/districts").json()["districts"]
        self.assertGreaterEqual(len(districts), 2)
        d1, d2 = districts[0], districts[1]
        s1a = self.client.get(f"/api/catalog/stops?district={d1}").json()["stops"]
        s2a = self.client.get(f"/api/catalog/stops?district={d2}").json()["stops"]
        self.assertGreaterEqual(len(s1a), 2)
        self.assertGreaterEqual(len(s2a), 2)
        return d1, d2, s1a[0]["id"], s1a[1]["id"], s2a[0]["id"], s2a[1]["id"]

    def test_search_district_fallback_finds_trip(self) -> None:
        self._register_driver()
        d1, d2, start_id, alt_start_id, end_id, alt_end_id = self._stops_pair_in_two_districts()
        r = self.client.post(
            "/api/trips",
            json={
                "start_point_id": start_id,
                "end_point_id": end_id,
                "trip_date": "2099-03-03",
                "departure_time": "10:00",
                "price_rub": 200,
                "seats_total": 2,
            },
        )
        self.assertEqual(r.status_code, 201, r.text)
        trip_id = r.json()["id"]

        exact = self.client.get(f"/api/trips?start_point={alt_start_id}&end_point={alt_end_id}").json()
        self.assertEqual(exact["trips"], [])
        self.assertEqual(exact["districtFallback"], {"startDistrict": d1, "endDistrict": d2})

        by_district = self.client.get(f"/api/trips?start_district={d1}&end_district={d2}").json()
        self.assertEqual(by_district["searchScope"], "district")
        self.assertTrue(any(t["id"] == trip_id for t in by_district["trips"]))

    def _approve_driver(self) -> None:
        db = Database(self.path)
        with db.transaction() as conn:
            conn.execute(
                "UPDATE users SET driver_moderation_status = 'approved' WHERE tg_user_id = ?",
                (self.settings.dev_user_id,),
            )
        db.close()

    def _register_driver(self, *, approve: bool = True) -> None:
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
        if approve:
            self._approve_driver()

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

        manage = self.client.get("/api/manage/trips").json()["trips"]
        row = next(t for t in manage if t["id"] == trip_id)
        self.assertIn("startLat", row)
        self.assertIn("endLng", row)
        self.assertIsNotNone(row["startLat"])
        self.assertIsNotNone(row["endLng"])

        found = self.client.get(f"/api/trips?start_point={a}&end_point={b}").json()["trips"]
        self.assertTrue(any(t["id"] == trip_id for t in found))

        details = self.client.get(f"/api/trips/{trip_id}").json()
        self.assertEqual(details["comment"], "Тестовый комментарий")
        self.assertIsNotNone(details.get("startLat"))
        self.assertIsNotNone(details.get("endLng"))

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

    def test_all_stops_have_coords(self) -> None:
        r = self.client.get("/api/catalog/stops/all")
        self.assertEqual(r.status_code, 200, r.text)
        stops = r.json()["stops"]
        self.assertGreater(len(stops), 0)
        first = stops[0]
        for key in ("id", "title", "lat", "lng"):
            self.assertIn(key, first)
        self.assertIsInstance(first["lat"], (int, float))
        self.assertIsInstance(first["lng"], (int, float))

    def test_nearby_stops_by_geo(self) -> None:
        r = self.client.get("/api/trips/nearby/by-geo?lat=57.6261&lng=39.8845")
        self.assertEqual(r.status_code, 200, r.text)
        stops = r.json()["stops"]
        self.assertGreater(len(stops), 0)
        first = stops[0]
        self.assertIn("id", first)
        self.assertIn("title", first)
        self.assertIn("distanceKm", first)
        self.assertIsInstance(first["distanceKm"], (int, float))

    def test_driver_pending_cannot_create_trip_until_approved(self) -> None:
        self._register_driver(approve=False)
        me = self.client.get("/api/me").json()["user"]
        self.assertEqual(me["driverModerationStatus"], "pending")
        self.assertFalse(me["isActiveDriver"])

        a, b = self._first_two_stop_ids()
        r = self.client.post(
            "/api/trips",
            json={
                "start_point_id": a,
                "end_point_id": b,
                "trip_date": "2099-04-04",
                "departure_time": "09:00",
                "price_rub": 200,
                "seats_total": 2,
            },
        )
        self.assertEqual(r.status_code, 400, r.text)
        self.assertIn("модерации", r.json()["detail"])

        self._approve_driver()
        me = self.client.get("/api/me").json()["user"]
        self.assertTrue(me["isActiveDriver"])
        r = self.client.post(
            "/api/trips",
            json={
                "start_point_id": a,
                "end_point_id": b,
                "trip_date": "2099-04-04",
                "departure_time": "09:00",
                "price_rub": 200,
                "seats_total": 2,
            },
        )
        self.assertEqual(r.status_code, 201, r.text)

    def test_passenger_rating_threshold_persists(self) -> None:
        self._register_driver()
        me = self.client.get("/api/me").json()["user"]
        self.assertIsNone(me.get("minPassengerRating"))

        r = self.client.put("/api/manage/passenger-rating-threshold", json={"threshold": "4.5"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["minPassengerRating"], 4.5)

        me = self.client.get("/api/me").json()["user"]
        self.assertEqual(me["minPassengerRating"], 4.5)

        r = self.client.put("/api/manage/passenger-rating-threshold", json={"threshold": "off"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsNone(r.json()["minPassengerRating"])

        me = self.client.get("/api/me").json()["user"]
        self.assertIsNone(me.get("minPassengerRating"))

    def test_history_and_dl_fields_in_me(self) -> None:
        self.client.post("/api/register", json={"name": "Hist", "role": "passenger"})
        r = self.client.get("/api/me")
        self.assertEqual(r.status_code, 200)
        user = r.json()["user"]
        self.assertIn("dlSeriesNumber", user)

        r = self.client.get("/api/history?role=passenger")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["role"], "passenger")
        self.assertIsInstance(r.json()["items"], list)

        r = self.client.get("/api/ratings/pending")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json()["pending"], list)

        r = self.client.get("/api/notifications")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json()["notifications"], list)


if __name__ == "__main__":
    unittest.main()
