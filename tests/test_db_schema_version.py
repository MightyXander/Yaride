from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

from app.db import SCHEMA_VERSION, Database


class SchemaVersionTests(TestCase):
    def test_fresh_db_records_current_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "fresh.db"
            db = Database(str(db_path))
            try:
                db.init_schema()

                with db.transaction() as conn:
                    row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
                self.assertIsNotNone(row, "schema_version row must exist after init_schema")
                self.assertEqual(int(row["version"]), SCHEMA_VERSION)

                with db.transaction() as c2:
                    mode = c2.execute("PRAGMA journal_mode").fetchone()[0]
                self.assertEqual(str(mode).lower(), "wal")
            finally:
                db.close()

    def test_init_schema_is_idempotent_for_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "twice.db"
            db = Database(str(db_path))
            try:
                db.init_schema()
                db.init_schema()

                with db.transaction() as conn:
                    rows = conn.execute("SELECT COUNT(*) AS cnt FROM schema_version").fetchall()
                self.assertEqual(int(rows[0]["cnt"]), 1)
            finally:
                db.close()

    def test_existing_db_without_schema_version_gets_marked_at_current(self) -> None:
        """БД уже полной схемы, но строка версии удалена — повторный init ставит SCHEMA_VERSION."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "legacy.db"
            db = Database(str(db_path))
            try:
                db.init_schema()
                with db.transaction() as conn:
                    conn.execute("DELETE FROM schema_version WHERE id = 1")
            finally:
                db.close()

            db2 = Database(str(db_path))
            try:
                db2.init_schema()

                with db2.transaction() as conn:
                    row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(int(row["version"]), SCHEMA_VERSION)
            finally:
                db2.close()
