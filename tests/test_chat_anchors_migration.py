"""Миграция v3 → v4: появление таблицы chat_anchors."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

from app.db import CURRENT_SCHEMA_VERSION, Database


def _table_exists(db: Database, name: str) -> bool:
    with db.transaction() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (name,),
        ).fetchone()
    return row is not None


class ChatAnchorsMigrationTests(TestCase):
    def test_current_schema_version_is_at_least_4(self) -> None:
        self.assertGreaterEqual(CURRENT_SCHEMA_VERSION, 4)

    def test_fresh_db_has_chat_anchors_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "fresh.db"
            db = Database(str(db_path))
            try:
                db.init_schema()
                self.assertTrue(_table_exists(db, "chat_anchors"))
            finally:
                db.close()

    def test_existing_v3_db_migrates_to_v4_chat_anchors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "legacy_v3.db"

            db = Database(str(db_path))
            try:
                db.init_schema()
                with db.transaction() as conn:
                    conn.execute("DROP TABLE IF EXISTS chat_anchors")
                    conn.execute("UPDATE schema_version SET version = 3 WHERE id = 1")
            finally:
                db.close()

            db2 = Database(str(db_path))
            try:
                db2.init_schema()
                self.assertTrue(_table_exists(db2, "chat_anchors"))
                with db2.transaction() as conn:
                    row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
                self.assertEqual(int(row["version"]), CURRENT_SCHEMA_VERSION)
            finally:
                db2.close()

    def test_chat_anchors_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cols.db"
            db = Database(str(db_path))
            try:
                db.init_schema()
                with db.transaction() as conn:
                    cols = {row["name"] for row in conn.execute("PRAGMA table_info(chat_anchors)").fetchall()}
                self.assertIn("chat_id", cols)
                self.assertIn("anchor_message_id", cols)
                self.assertIn("flow_kind", cols)
                self.assertIn("updated_at", cols)
            finally:
                db.close()
