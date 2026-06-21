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
            bot_token=None,  # отключаем уведомления в тестах
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
        self._approve_driver_by_id(self.settings.dev_user_id)

    def _approve_driver_by_id(self, tg_user_id: int) -> None:
        db = Database(self.path)
        with db.transaction() as conn:
            conn.execute(
                "UPDATE users SET driver_moderation_status = 'approved' WHERE tg_user_id = ?",
                (tg_user_id,),
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

    def _register_passenger(self) -> None:
        """Регистрация пассажира для тестов бронирования."""
        r = self.client.post("/api/register", json={"name": "Пассажир", "role": "passenger"})
        self.assertEqual(r.status_code, 200, r.text)

    def test_booking_create_and_cancel_with_reason(self) -> None:
        """
        Gap test #33: POST /api/bookings (создание брони) и cancel с причиной.
        """
        self._register_driver()
        a, b = self._first_two_stop_ids()

        # Создаем поездку
        r = self.client.post(
            "/api/trips",
            json={
                "start_point_id": a,
                "end_point_id": b,
                "trip_date": "2099-05-05",
                "departure_time": "12:00",
                "price_rub": 100,
                "seats_total": 2,
            },
        )
        self.assertEqual(r.status_code, 201, r.text)
        trip_id = r.json()["id"]

        # Переключаемся на пассажира (создаем нового клиента с другим dev_user_id)
        # bot_token=None отключает уведомления (BotNotifier.enabled = False)
        passenger_settings = WebAppSettings(
            bot_token=None,
            db_path=self.path,
            dev_user_id=900002,
        )
        passenger_app = create_app(passenger_settings)
        passenger_client = TestClient(passenger_app)
        passenger_client.__enter__()

        # Регистрируем пассажира
        r = passenger_client.post("/api/register", json={"name": "Пассажир", "role": "passenger"})
        self.assertEqual(r.status_code, 200, r.text)

        # POST /api/bookings — создание брони
        r = passenger_client.post("/api/bookings", json={"trip_id": trip_id})
        self.assertEqual(r.status_code, 201, r.text)
        booking_id = r.json()["id"]

        # Проверяем, что бронь появилась
        bookings = passenger_client.get("/api/bookings").json()["bookings"]
        self.assertTrue(any(b["id"] == booking_id for b in bookings))

        # Отмена брони с причиной
        r = passenger_client.post(
            f"/api/bookings/{booking_id}/cancel", json={"reason": "Изменились планы"}
        )
        self.assertEqual(r.status_code, 200, r.text)

        # Проверяем, что бронь отменена
        bookings = passenger_client.get("/api/bookings").json()["bookings"]
        cancelled = next(b for b in bookings if b["id"] == booking_id)
        self.assertEqual(cancelled["status"], "cancelled_by_passenger")
        self.assertEqual(cancelled["cancelReason"], "Изменились планы")

        passenger_client.__exit__(None, None, None)

    def test_rating_create_and_pending_list(self) -> None:
        """
        Gap test #33: POST /api/ratings (создание оценки) и GET /api/ratings/pending (список ожидающих).
        """
        self._register_driver()
        a, b = self._first_two_stop_ids()

        # Создаем завершённую поездку в прошлом напрямую в БД (обходим валидацию)
        db = Database(self.path)
        with db.transaction() as conn:
            driver_id = conn.execute(
                "SELECT id FROM users WHERE tg_user_id = ?", (self.settings.dev_user_id,)
            ).fetchone()["id"]
            trip_id = conn.execute(
                """INSERT INTO trips(driver_id, start_point_id, end_point_id, trip_date, departure_time, time_slot, price_rub, seats_total, status)
                   VALUES (?, ?, ?, '2020-06-06', '14:00', '2020-06-06 14:00', 120, 2, 'completed')""",
                (driver_id, a, b),
            ).lastrowid
        db.close()

        # Пассажир бронирует и завершает поездку
        # bot_token=None отключает уведомления
        passenger_settings = WebAppSettings(
            bot_token=None,
            db_path=self.path,
            dev_user_id=900003,
        )
        passenger_app = create_app(passenger_settings)
        passenger_client = TestClient(passenger_app)
        passenger_client.__enter__()

        r = passenger_client.post("/api/register", json={"name": "Пассажир2", "role": "passenger"})
        self.assertEqual(r.status_code, 200, r.text)

        # Создаем бронь напрямую в БД
        db = Database(self.path)
        with db.transaction() as conn:
            passenger_id = conn.execute(
                "SELECT id FROM users WHERE tg_user_id = ?", (900003,)
            ).fetchone()["id"]
            conn.execute(
                "INSERT INTO bookings(trip_id, passenger_id, status) VALUES (?, ?, 'active')",
                (trip_id, passenger_id),
            )
        db.close()

        # Проверяем GET /api/ratings/pending
        r = passenger_client.get("/api/ratings/pending")
        self.assertEqual(r.status_code, 200)
        pending = r.json()["pending"]
        self.assertIsInstance(pending, list)

        # POST /api/ratings — создание оценки
        driver_tg_id = self.settings.dev_user_id
        r = passenger_client.post(
            "/api/ratings",
            json={"trip_id": trip_id, "rated_tg_user_id": driver_tg_id, "stars": 5, "review_text": "Отличная поездка!"},
        )
        self.assertEqual(r.status_code, 201, r.text)
        self.assertTrue(r.json()["ok"])

        passenger_client.__exit__(None, None, None)

    def test_user_can_be_driver_and_passenger_simultaneously(self) -> None:
        """Тест Issue #41: пользователь может одновременно быть водителем (создать поездку) и пассажиром (забронировать чужую поездку)."""
        # Создаём app с отключёнными уведомлениями (bot_token=None)
        no_notify_settings = WebAppSettings(bot_token=None, db_path=self.path, dev_user_id=self.settings.dev_user_id)
        no_notify_app = create_app(no_notify_settings)
        no_notify_client = TestClient(no_notify_app)
        no_notify_client.__enter__()

        # Регистрируем первого пользователя как водителя
        r = no_notify_client.post(
            "/api/register",
            json={
                "name": "Водитель",
                "role": "driver",
                "dl_series_number": "9916АВ123456",
                "dl_valid_until": "2030-01-01",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        self._approve_driver()

        a, b = self._first_two_stop_ids()

        # Создаём поездку как водитель
        r = no_notify_client.post(
            "/api/trips",
            json={
                "start_point_id": a,
                "end_point_id": b,
                "trip_date": "2099-03-03",
                "departure_time": "10:00",
                "price_rub": 200,
                "seats_total": 3,
            },
        )
        self.assertEqual(r.status_code, 201, r.text)
        own_trip_id = r.json()["id"]

        # Создаём второго водителя (отдельного пользователя)
        db = Database(self.path)
        with db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO users(tg_user_id, name, username, role, dl_series_number, dl_valid_until, driver_moderation_status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (900002, "Второй водитель", "driver2", "driver", "1234АБ567890", "2030-01-01", "approved"),
            )
            driver2_id = conn.execute("SELECT id FROM users WHERE tg_user_id = ?", (900002,)).fetchone()["id"]
            # Создаём поездку второго водителя
            cur = conn.execute(
                """
                INSERT INTO trips(driver_id, start_point_id, end_point_id, trip_date, departure_time, time_slot, price_rub, seats_total, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (driver2_id, a, b, "2099-03-03", "11:00", "2099-03-03 11:00", 250, 2, "open"),
            )
            other_trip_id = cur.lastrowid
        db.close()

        # Первый пользователь (водитель) бронирует место в поездке второго водителя
        r = no_notify_client.post("/api/bookings", json={"trip_id": other_trip_id})
        self.assertEqual(r.status_code, 201, r.text)
        booking_id = r.json()["id"]

        # Проверяем, что бронь создана
        bookings = no_notify_client.get("/api/bookings").json()["bookings"]
        self.assertTrue(any(b["id"] == booking_id for b in bookings))

        # Проверяем, что своя поездка всё ещё активна
        manage = no_notify_client.get("/api/manage/trips").json()["trips"]
        self.assertTrue(any(t["id"] == own_trip_id and t["status"] == "open" for t in manage))

        no_notify_client.__exit__(None, None, None)

    def test_driver_can_switch_to_passenger_with_active_trips(self) -> None:
        """Тест Issue #41: водитель может сменить роль на пассажира даже при активных поездках (ограничение снято)."""
        self._register_driver()
        a, b = self._first_two_stop_ids()

        # Создаём поездку
        r = self.client.post(
            "/api/trips",
            json={
                "start_point_id": a,
                "end_point_id": b,
                "trip_date": "2099-03-03",
                "departure_time": "10:00",
                "price_rub": 200,
                "seats_total": 3,
            },
        )
        self.assertEqual(r.status_code, 201, r.text)
        trip_id = r.json()["id"]

        # Пытаемся сменить роль на пассажира (раньше было нельзя при активных поездках)
        db = Database(self.path)
        from app.repo import Repo
        repo = Repo(db)
        success, msg = repo.users.switch_role(self.settings.dev_user_id, "passenger", "2099-03-03")
        db.close()

        # ДОЛЖНО ПРОЙТИ (Issue #41 снимает ограничение)
        self.assertTrue(success, msg)

        # Проверяем, что роль изменилась
        user = self.client.get("/api/me").json()["user"]
        self.assertEqual(user["role"], "passenger")

        # Поездка остаётся активной
        r = self.client.get(f"/api/trips/{trip_id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "open")

    def test_search_without_registration_booking_requires_profile(self) -> None:
        """Just-in-time регистрация: поиск без профиля, бронь требует регистрации (#42)."""
        # Незарегистрированный пользователь может выполнять поиск
        r = self.client.get("/api/me")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["registered"])

        # Создаём поездку (второй клиент = водитель)
        from fastapi.testclient import TestClient
        driver_settings = WebAppSettings(
            bot_token=None,
            db_path=self.path,
            dev_user_id=900002,
        )
        driver_app = create_app(driver_settings)
        driver_client = TestClient(driver_app)
        driver_client.__enter__()

        driver_client.post("/api/register", json={
            "name": "Водитель",
            "role": "driver",
            "dl_series_number": "9916АВ123456",
            "dl_valid_until": "2030-01-01",
        })
        self._approve_driver_by_id(900002)

        a, b = self._first_two_stop_ids()
        r = driver_client.post("/api/trips", json={
            "start_point_id": a,
            "end_point_id": b,
            "trip_date": "2099-06-06",
            "departure_time": "10:00",
            "price_rub": 250,
            "seats_total": 3,
        })
        self.assertEqual(r.status_code, 201, r.text)
        trip_id = r.json()["id"]
        driver_client.__exit__(None, None, None)

        # Незарегистрированный пользователь ищет поездки — должно работать
        r = self.client.get("/api/trips", params={"start_point": a, "end_point": b, "date": "2099-06-06"})
        self.assertEqual(r.status_code, 200, r.text)
        trips = r.json()["trips"]
        self.assertEqual(len(trips), 1)
        self.assertEqual(trips[0]["id"], trip_id)

        # Детали поездки доступны без регистрации
        r = self.client.get(f"/api/trips/{trip_id}")
        self.assertEqual(r.status_code, 200, r.text)

        # Попытка бронирования БЕЗ регистрации — должна вернуть ошибку
        r = self.client.post("/api/bookings", json={"trip_id": trip_id})
        self.assertEqual(r.status_code, 400, r.text)
        self.assertIn("не зарегистрирован", r.json()["detail"].lower())

        # Регистрация
        r = self.client.post("/api/register", json={"name": "Пассажир", "role": "passenger"})
        self.assertEqual(r.status_code, 200, r.text)

        # Бронирование после регистрации — успех
        r = self.client.post("/api/bookings", json={"trip_id": trip_id})
        self.assertEqual(r.status_code, 201, r.text)
        booking_id = r.json()["id"]
        self.assertIsInstance(booking_id, int)

        # Проверяем список броней
        r = self.client.get("/api/bookings")
        self.assertEqual(r.status_code, 200)
        bookings = r.json()["bookings"]
        self.assertEqual(len(bookings), 1)
        self.assertEqual(bookings[0]["tripId"], trip_id)
        self.assertEqual(bookings[0]["status"], "active")

    def test_trip_card_has_driver_profile_fields(self) -> None:
        """Issue #21: профиль водителя виден до брони (рейтинг, число поездок, дата регистрации)."""
        self._register_driver()
        a, b = self._first_two_stop_ids()
        r = self.client.post(
            "/api/trips",
            json={
                "start_point_id": a,
                "end_point_id": b,
                "trip_date": "2099-03-03",
                "departure_time": "10:00",
                "price_rub": 200,
                "seats_total": 4,
            },
        )
        self.assertEqual(r.status_code, 201, r.text)
        trip_id = r.json()["id"]

        # Проверка в списке поездок (search)
        found = self.client.get(f"/api/trips?start_point={a}&end_point={b}").json()["trips"]
        trip = next(t for t in found if t["id"] == trip_id)
        self.assertIn("driverName", trip)
        self.assertIn("driverRating", trip)
        self.assertIn("driverRatingCount", trip)
        self.assertIn("driverTripsCount", trip)
        self.assertIn("driverCreatedAt", trip)
        self.assertIsInstance(trip["driverRating"], (int, float))
        self.assertIsInstance(trip["driverRatingCount"], int)
        self.assertIsInstance(trip["driverTripsCount"], int)
        self.assertIsNotNone(trip["driverCreatedAt"])

        # Проверка на детальной странице
        details = self.client.get(f"/api/trips/{trip_id}").json()
        self.assertIn("driverName", details)
        self.assertIn("driverRating", details)
        self.assertIn("driverRatingCount", details)
        self.assertIn("driverTripsCount", details)
        self.assertIn("driverCreatedAt", details)

    def test_trip_card_shows_new_driver_without_rating(self) -> None:
        """Issue #21: новичок без рейтинга не отсекается и показывается как 'новый водитель'."""
        self._register_driver()
        a, b = self._first_two_stop_ids()
        r = self.client.post(
            "/api/trips",
            json={
                "start_point_id": a,
                "end_point_id": b,
                "trip_date": "2099-04-04",
                "departure_time": "11:00",
                "price_rub": 180,
                "seats_total": 3,
            },
        )
        self.assertEqual(r.status_code, 201, r.text)
        trip_id = r.json()["id"]

        details = self.client.get(f"/api/trips/{trip_id}").json()
        # Новый водитель: rating_avg = 0.0, rating_count = 0
        self.assertEqual(details["driverRating"], 0.0)
        self.assertEqual(details["driverRatingCount"], 0)
        # Но поездка показывается в результатах поиска
        found = self.client.get(f"/api/trips?start_point={a}&end_point={b}").json()["trips"]
        self.assertTrue(any(t["id"] == trip_id for t in found))


if __name__ == "__main__":
    unittest.main()
