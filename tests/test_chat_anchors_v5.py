"""Этап 4 (завершение): миграция v4→v5 — reply_aux_message_id и drop bot_chat_messages."""

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


class ChatAnchorsV5MigrationTests(unittest.TestCase):
    def test_current_schema_version_at_least_5(self) -> None:
        self.assertGreaterEqual(CURRENT_SCHEMA_VERSION, 5)

    def test_fresh_db_has_reply_aux_column_and_no_bot_chat_messages(self) -> None:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db = Database(path)
        try:
            db.init_schema()
            with sqlite3.connect(path) as conn:
                conn.row_factory = sqlite3.Row
                cols = {r["name"] for r in conn.execute("PRAGMA table_info(chat_anchors)")}
                self.assertIn("reply_aux_message_id", cols)
                self.assertIn("anchor_message_id", cols)
                self.assertIn("flow_kind", cols)

                tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertNotIn("bot_chat_messages", tables)
        finally:
            db.close()
            gc.collect()
            _cleanup(path)

    def test_v4_db_migrates_to_v5_drops_bot_chat_messages_and_adds_column(self) -> None:
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
                    INSERT INTO schema_version(id, version) VALUES (1, 4);
                    CREATE TABLE chat_anchors (
                        chat_id INTEGER PRIMARY KEY,
                        anchor_message_id INTEGER NOT NULL,
                        flow_kind TEXT NOT NULL,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE bot_chat_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id INTEGER NOT NULL,
                        message_id INTEGER NOT NULL
                    );
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
                    self.assertGreaterEqual(int(ver), 5)
                    cols = {r["name"] for r in conn.execute("PRAGMA table_info(chat_anchors)")}
                    self.assertIn("reply_aux_message_id", cols)
                    tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    self.assertNotIn("bot_chat_messages", tables)
            finally:
                db.close()
        finally:
            gc.collect()
            _cleanup(path)


if __name__ == "__main__":
    unittest.main()
