"""Аутентификация админки: хэширование пароля и проверка по таблице admin_users."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

from admin.auth import authenticate, hash_password, verify_password
from app.db import Database
from app.repo import Repo


class AdminAuthTests(TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self._tmp.name) / "auth.db"))
        self.db.init_schema()
        self.repo = Repo(self.db)

    def tearDown(self) -> None:
        self.db.close()
        self._tmp.cleanup()

    def test_hash_roundtrip(self) -> None:
        h = hash_password("s3cret-pass")
        self.assertNotEqual(h, "s3cret-pass")
        self.assertTrue(verify_password("s3cret-pass", h))
        self.assertFalse(verify_password("wrong", h))

    def test_authenticate_success_and_failure(self) -> None:
        self.repo.admin.create_admin("root", hash_password("longpassword"))
        self.assertTrue(authenticate(self.repo, "root", "longpassword"))
        self.assertFalse(authenticate(self.repo, "root", "bad"))
        self.assertFalse(authenticate(self.repo, "nobody", "longpassword"))

    def test_duplicate_admin_rejected(self) -> None:
        self.repo.admin.create_admin("root", hash_password("longpassword"))
        with self.assertRaises(ValueError):
            self.repo.admin.create_admin("root", hash_password("other"))

    def test_last_login_recorded(self) -> None:
        self.repo.admin.create_admin("root", hash_password("longpassword"))
        self.assertIsNone(self.repo.admin.get_admin("root")["last_login_at"])
        authenticate(self.repo, "root", "longpassword")
        self.assertIsNotNone(self.repo.admin.get_admin("root")["last_login_at"])
