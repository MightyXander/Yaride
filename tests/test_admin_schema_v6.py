"""Админка: миграция v5→v6 — users.is_banned, таблицы admin_users и admin_audit_log."""

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


class AdminSchemaV6MigrationTests(unittest.TestCase):
    def test_current_schema_version_at_least_6(self) -> None:
        self.assertGreaterEqual(CURRENT_SCHEMA_VERSION, 6)

    def test_fresh_db_has_admin_objects(self) -> None:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db = Database(path)
        try:
            db.init_schema()
            with sqlite3.connect(path) as conn:
                conn.row_factory = sqlite3.Row
                user_cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
                self.assertIn("is_banned", user_cols)

                tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertIn("admin_users", tables)
                self.assertIn("admin_audit_log", tables)
        finally:
            db.close()
            gc.collect()
            _cleanup(path)

    def test_v5_db_migrates_to_v6(self) -> None:
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
                    INSERT INTO schema_version(id, version) VALUES (1, 5);
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tg_user_id INTEGER UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        role TEXT NOT NULL
                    );
                    INSERT INTO users(tg_user_id, name, role) VALUES (111, 'Тест', 'passenger');
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
                    self.assertGreaterEqual(int(ver), 6)

                    user_cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
                    self.assertIn("is_banned", user_cols)
                    # Существующие строки получают дефолт 0 (не забанены).
                    row = conn.execute("SELECT is_banned FROM users WHERE tg_user_id = 111").fetchone()
                    self.assertEqual(int(row["is_banned"]), 0)

                    tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    self.assertIn("admin_users", tables)
                    self.assertIn("admin_audit_log", tables)
            finally:
                db.close()
        finally:
            gc.collect()
            _cleanup(path)


if __name__ == "__main__":
    unittest.main()
