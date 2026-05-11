"""Репозиторий верхнего уровня без прокси-методов — только под-репозитории и утилиты."""

from __future__ import annotations

from unittest import TestCase

from app.db import Database
from app.repo import Repo


class RepoThinTests(TestCase):
    def test_no_legacy_facade_methods_on_repo(self) -> None:
        self.assertFalse(hasattr(Repo, "get_user"))
        self.assertFalse(hasattr(Repo, "create_booking"))

    def test_sub_repositories_exposed(self) -> None:
        db = Database(":memory:")
        db.init_schema()
        repo = Repo(db)
        self.assertTrue(hasattr(repo, "users"))
        self.assertTrue(hasattr(repo, "routes"))
        self.assertTrue(hasattr(repo, "trips"))
        self.assertTrue(hasattr(repo, "bookings"))
        self.assertTrue(hasattr(repo, "favorites"))
        self.assertTrue(hasattr(repo, "ratings"))
        self.assertTrue(callable(repo.users.get_user))
        self.assertTrue(callable(repo.trips.find_open_trips))
