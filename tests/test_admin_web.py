"""HTTP-уровень админки через Starlette TestClient. Пропускается, если httpx не установлен."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.db import Database
from app.repo import Repo

try:
    import httpx  # noqa: F401  (TestClient требует httpx)
    from fastapi.testclient import TestClient

    _HAS_CLIENT = True
except Exception:
    _HAS_CLIENT = False


@unittest.skipUnless(_HAS_CLIENT, "httpx не установлен — пропускаем HTTP-тесты админки")
class AdminWebTests(unittest.TestCase):
    def setUp(self) -> None:
        from admin.app import create_app
        from admin.auth import hash_password
        from admin.config import AdminSettings

        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "web.db")
        seed_db = Database(self.db_path)
        seed_db.init_schema()
        repo = Repo(seed_db)
        repo.admin.create_admin("root", hash_password("longpassword"))
        with seed_db.transaction() as conn:
            conn.execute("INSERT INTO users(tg_user_id, name, role) VALUES (7001, 'Иван', 'passenger')")
            self.user_id = int(conn.execute("SELECT id FROM users WHERE tg_user_id = 7001").fetchone()["id"])
        seed_db.close()

        settings = AdminSettings(
            db_path=self.db_path,
            session_secret="x" * 32,
            host="127.0.0.1",
            port=8000,
            bot_token=None,
            notify_enabled=False,
        )
        self.app = create_app(settings)
        # Контекст-менеджер запускает lifespan (инициализация app.state.repo/service/notifier).
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        self._tmp.cleanup()

    def test_dashboard_requires_login(self) -> None:
        resp = self.client.get("/", follow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertEqual(resp.headers["location"], "/login")

    def test_login_and_access_dashboard(self) -> None:
        resp = self.client.post(
            "/login",
            data={"username": "root", "password": "longpassword"},
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 303)
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Сводка", page.text)

    def _login(self) -> None:
        self.client.post(
            "/login",
            data={"username": "root", "password": "longpassword"},
            follow_redirects=False,
        )

    def test_ban_user_through_form_writes_audit(self) -> None:
        self._login()
        resp = self.client.post(
            f"/users/{self.user_id}/ban",
            data={"banned": "1"},
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 303)
        repo = self.app.state.repo
        self.assertTrue(repo.users.is_banned(7001))
        audit = repo.admin.list_audit()
        self.assertTrue(any(e["action"] == "ban" and e["entity"] == "user" for e in audit))

    def test_bad_login_rejected(self) -> None:
        resp = self.client.post(
            "/login",
            data={"username": "root", "password": "nope"},
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 303)
        self.assertIn("error", resp.headers["location"])

    def test_points_map_and_patch_coordinates(self) -> None:
        self._login()
        repo = self.app.state.repo
        point_id = int(
            repo.routes.list_points_admin(limit=1)[0]["id"]
        )
        page = self.client.get("/points/map")
        self.assertEqual(page.status_code, 200)
        self.assertIn("points-map.js", page.text)
        self.assertIn("initBulkMap", page.text)

        resp = self.client.patch(
            f"/points/{point_id}/coordinates",
            json={"latitude": 57.625, "longitude": 39.875},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        point = repo.routes.get_point(point_id)
        self.assertAlmostEqual(float(point["latitude"]), 57.625, places=3)
        audit = repo.admin.list_audit()
        self.assertTrue(
            any(e["action"] == "patch_coords" and int(e["entity_id"]) == point_id for e in audit)
        )


if __name__ == "__main__":
    unittest.main()
