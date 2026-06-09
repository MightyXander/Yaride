"""Админ-сервис: чтение списков, правки с инвариантами, бан, удаление оценок, аудит."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

from app.db import Database
from app.repo import Repo
from app.services.admin_service import AdminService


class AdminServiceTests(TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        db_path = Path(self._tmp.name) / "admin.db"
        self.db = Database(str(db_path))
        self.db.init_schema()
        self.repo = Repo(self.db)
        self.service = AdminService(self.repo)
        self._seed()

    def tearDown(self) -> None:
        self.db.close()
        self._tmp.cleanup()

    def _seed(self) -> None:
        with self.db.transaction() as conn:
            rp = conn.execute("SELECT id FROM route_points ORDER BY id LIMIT 2").fetchall()
            self.start_id = int(rp[0]["id"])
            self.end_id = int(rp[1]["id"])
            conn.execute(
                "INSERT INTO users(tg_user_id, name, username, role, dl_series_number) "
                "VALUES (5001, 'Водитель', 'drv', 'driver', '9916АВ123456')"
            )
            self.driver_id = int(conn.execute("SELECT id FROM users WHERE tg_user_id = 5001").fetchone()["id"])
            conn.execute("INSERT INTO users(tg_user_id, name, role) VALUES (5002, 'Пассажир', 'passenger')")
            self.passenger_id = int(conn.execute("SELECT id FROM users WHERE tg_user_id = 5002").fetchone()["id"])
            conn.execute(
                """
                INSERT INTO trips(driver_id, start_point_id, end_point_id, trip_date, departure_time,
                                  time_slot, price_rub, seats_total, seats_booked, status)
                VALUES (?, ?, ?, '2099-06-01', '10:00', '2099-06-01 10:00', 150, 3, 1, 'open')
                """,
                (self.driver_id, self.start_id, self.end_id),
            )
            self.trip_id = int(conn.execute("SELECT id FROM trips ORDER BY id DESC LIMIT 1").fetchone()["id"])
            conn.execute(
                "INSERT INTO bookings(trip_id, passenger_id, status) VALUES (?, ?, 'active')",
                (self.trip_id, self.passenger_id),
            )

    def test_list_all_trips_and_users(self) -> None:
        trips = self.repo.trips.list_all_trips()
        self.assertEqual(len(trips), 1)
        self.assertEqual(trips[0]["driver_name"], "Водитель")

        users = self.repo.users.list_all_users(query="Пассаж")
        self.assertEqual(len(users), 1)
        self.assertEqual(int(users[0]["tg_user_id"]), 5002)

    def test_update_trip_rejects_seats_below_booked(self) -> None:
        with self.assertRaises(ValueError):
            self.service.update_trip(
                "admin",
                self.trip_id,
                start_point_id=self.start_id,
                end_point_id=self.end_id,
                price_rub=150,
                seats_total=0,
                trip_date="2099-06-01",
                departure_time="10:00",
                status="open",
            )

    def test_update_trip_writes_audit(self) -> None:
        self.service.update_trip(
            "admin",
            self.trip_id,
            start_point_id=self.start_id,
            end_point_id=self.end_id,
            price_rub=200,
            seats_total=4,
            trip_date="2099-06-02",
            departure_time="12:00",
            status="open",
        )
        row = self.repo.trips.get_trip_admin(self.trip_id)
        self.assertEqual(int(row["price_rub"]), 200)
        self.assertEqual(int(row["seats_total"]), 4)

    def test_update_trip_changes_route_points(self) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO route_points(locality, district, admin_area, title, kind)
                VALUES ('Ярославль', 'Тест', '', 'Новая отправная', 'stop')
                """
            )
            new_start_id = int(conn.execute("SELECT id FROM route_points ORDER BY id DESC LIMIT 1").fetchone()["id"])
        self.service.update_trip(
            "admin",
            self.trip_id,
            start_point_id=new_start_id,
            end_point_id=self.end_id,
            price_rub=150,
            seats_total=3,
            trip_date="2099-06-01",
            departure_time="10:00",
            status="open",
        )
        row = self.repo.trips.get_trip_admin(self.trip_id)
        self.assertEqual(int(row["start_point_id"]), new_start_id)
        self.assertEqual(row["start_title"], "Новая отправная")

    def test_update_point_changes_stop_fields(self) -> None:
        point_id = self.start_id
        self.service.update_point(
            "admin",
            point_id,
            locality="Ярославль",
            district="Обновлённый район",
            admin_area="",
            title="Обновлённая остановка",
            latitude=57.6,
            longitude=39.8,
        )
        point = self.repo.routes.get_point(point_id)
        self.assertEqual(point["district"], "Обновлённый район")
        self.assertEqual(point["title"], "Обновлённая остановка")
        audit = self.repo.admin.list_audit()
        point_audit = [row for row in audit if row["entity"] == "route_point" and row["action"] == "update"]
        self.assertTrue(any(str(row["entity_id"]) == str(point_id) for row in point_audit))

    def test_cancel_trip_frees_bookings_and_notifies(self) -> None:
        notifications = self.service.cancel_trip("admin", self.trip_id)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].tg_user_id, 5002)
        trip = self.repo.trips.get_trip_admin(self.trip_id)
        self.assertEqual(trip["status"], "cancelled")
        self.assertEqual(int(trip["seats_booked"]), 0)

    def test_ban_and_unban_user(self) -> None:
        notifs = self.service.set_user_ban("admin", self.passenger_id, True)
        self.assertEqual(notifs[0].tg_user_id, 5002)
        self.assertTrue(self.repo.users.is_banned(5002))
        self.service.set_user_ban("admin", self.passenger_id, False)
        self.assertFalse(self.repo.users.is_banned(5002))

    def test_delete_rating_recalculates(self) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO trip_ratings(trip_id, rater_user_id, rated_user_id, stars) VALUES (?, ?, ?, 4)",
                (self.trip_id, self.passenger_id, self.driver_id),
            )
            self.repo.ratings._refresh_user_rating(conn, self.driver_id)
        rating_id = int(self.repo.ratings.list_all_ratings()[0]["id"])
        self.service.delete_rating("admin", rating_id)
        driver = self.repo.users.get_user_by_id(self.driver_id)
        self.assertEqual(int(driver["rating_count"]), 0)
        self.assertEqual(float(driver["rating_avg"]), 0.0)

    def test_delete_point_blocked_when_referenced(self) -> None:
        with self.assertRaises(ValueError):
            self.service.delete_point("admin", self.start_id)

    def test_admin_can_promote_passenger_to_driver_with_dl(self) -> None:
        self.service.update_user(
            "admin",
            self.passenger_id,
            name="Пассажир",
            role="driver",
            min_passenger_rating=None,
            dl_series_number="9916АВ999999",
            dl_valid_until="2031-12-31",
            car_model="VW Polo",
            car_color="Серый",
            car_plate="А111АА",
        )
        user = self.repo.users.get_user_by_id(self.passenger_id)
        self.assertEqual(user["role"], "driver")
        self.assertEqual(user["dl_series_number"], "9916АВ999999")
        self.assertEqual(user["driver_moderation_status"], "approved")
        self.assertEqual(user["car_model"], "VW Polo")

    def test_admin_promote_to_driver_requires_dl(self) -> None:
        with self.assertRaises(ValueError):
            self.service.update_user(
                "admin",
                self.passenger_id,
                name="Пассажир",
                role="driver",
                min_passenger_rating=None,
            )

    def test_driver_moderation_approve_and_reject(self) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO users(tg_user_id, name, role, dl_series_number, dl_valid_until, driver_moderation_status)
                VALUES (5003, 'Новый водитель', 'driver', '9916АВ654321', '2031-01-01', 'pending')
                """
            )
            pending_id = int(
                conn.execute("SELECT id FROM users WHERE tg_user_id = 5003").fetchone()["id"]
            )

        notifs = self.service.approve_driver("admin", pending_id)
        self.assertEqual(notifs[0].tg_user_id, 5003)
        user = self.repo.users.get_user_by_id(pending_id)
        self.assertEqual(user["driver_moderation_status"], "approved")

        self.service.reject_driver("admin", pending_id)
        user = self.repo.users.get_user_by_id(pending_id)
        self.assertEqual(user["driver_moderation_status"], "rejected")
        audit = self.repo.admin.list_audit()
        actions = [row["action"] for row in audit if row["entity"] == "user"]
        self.assertIn("approve_driver", actions)
        self.assertIn("reject_driver", actions)

    def test_patch_point_coordinates(self) -> None:
        self.service.patch_point_coordinates("admin", self.start_id, latitude=57.626, longitude=39.876)
        point = self.repo.routes.get_point(self.start_id)
        self.assertAlmostEqual(float(point["latitude"]), 57.626, places=3)
        audit = self.repo.admin.list_audit()
        self.assertTrue(any(e["action"] == "patch_coords" for e in audit))
