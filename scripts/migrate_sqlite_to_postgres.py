#!/usr/bin/env python3
"""Перенос данных из SQLite (yaride.db) в PostgreSQL (DATABASE_URL).

Примеры:
  py -3 scripts/migrate_sqlite_to_postgres.py --source yaride.db
  py -3 scripts/migrate_sqlite_to_postgres.py --source backups/check-core.db --target $DATABASE_URL
  py -3 scripts/migrate_sqlite_to_postgres.py --source yaride.db --wipe
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Порядок вставки с учётом внешних ключей.
_TABLES = (
    "users",
    "route_points",
    "trips",
    "bookings",
    "favorite_routes",
    "trip_ratings",
    "rating_prompts_sent",
    "chat_anchors",
    "admin_users",
    "admin_audit_log",
    "trip_templates",
    "schema_version",
)


def _checkpoint_sqlite(path: Path) -> None:
    wal = Path(f"{path}-wal")
    shm = Path(f"{path}-shm")
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()
    for sidecar in (wal, shm):
        if sidecar.is_file():
            sidecar.unlink()


def _sqlite_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [str(r[1]) for r in rows]


def _pg_columns(pg_conn, table: str) -> list[str]:  # noqa: ANN001
    rows = pg_conn.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table,),
    ).fetchall()
    return [str(r["column_name"]) for r in rows]


def _wipe_postgres(pg_conn) -> None:  # noqa: ANN001
    tables = ", ".join(_TABLES)
    pg_conn.execute(f"TRUNCATE {tables} RESTART IDENTITY CASCADE")


def _copy_table(
    sqlite_conn: sqlite3.Connection,
    pg_conn,  # noqa: ANN001
    table: str,
) -> int:
    sqlite_cols = _sqlite_columns(sqlite_conn, table)
    pg_cols = _pg_columns(pg_conn, table)
    cols = [c for c in sqlite_cols if c in pg_cols]
    if not cols:
        return 0
    col_list = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))
    rows = sqlite_conn.execute(f"SELECT {col_list} FROM {table}").fetchall()
    if not rows:
        return 0
    sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    count = 0
    for row in rows:
        values = tuple(row[c] for c in cols)
        pg_conn.execute(sql, values)
        count += 1
    return count


_SERIAL_TABLES = tuple(
    t
    for t in _TABLES
    if t not in ("rating_prompts_sent", "chat_anchors", "schema_version")
)


def _reset_sequences(pg_conn) -> None:  # noqa: ANN001
    for table in _SERIAL_TABLES:
        pg_conn.execute(
            f"""
            SELECT setval(
                pg_get_serial_sequence('{table}', 'id'),
                COALESCE((SELECT MAX(id) FROM {table}), 1),
                true
            )
            """
        )


def migrate(source: Path, target_url: str, *, wipe: bool) -> None:
    if not source.is_file():
        raise RuntimeError(f"SQLite файл не найден: {source}")

    _checkpoint_sqlite(source)

    import psycopg
    from psycopg.rows import dict_row

    from app.db_postgres import PostgresDatabase

    pg_boot = PostgresDatabase(target_url)
    pg_boot.init_schema()

    sqlite_conn = sqlite3.connect(str(source))
    sqlite_conn.row_factory = sqlite3.Row

    with psycopg.connect(target_url, row_factory=dict_row, autocommit=False) as pg_conn:
        if wipe:
            print("Очистка целевых таблиц…")
            _wipe_postgres(pg_conn)

        total = 0
        for table in _TABLES:
            if table == "schema_version":
                continue
            n = _copy_table(sqlite_conn, pg_conn, table)
            if n:
                print(f"  {table}: {n} строк")
            total += n

        pg_conn.execute(
            "INSERT INTO schema_version(id, version) VALUES (1, %s) ON CONFLICT (id) DO UPDATE SET version = EXCLUDED.version",
            (11,),
        )
        try:
            _reset_sequences(pg_conn)
        except Exception as exc:
            print(f"  (предупреждение: reset sequences: {exc})")
        pg_conn.commit()

    sqlite_conn.close()
    print(f"Готово. Перенесено строк: {total}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Миграция yaride.db → PostgreSQL")
    parser.add_argument("--source", default="yaride.db", help="Путь к SQLite")
    parser.add_argument("--target", help="DATABASE_URL (по умолчанию из окружения)")
    parser.add_argument("--wipe", action="store_true", help="Очистить Postgres перед импортом")
    args = parser.parse_args(argv)

    target = (args.target or os.getenv("DATABASE_URL", "")).strip()
    if not target:
        print("Ошибка: укажите --target или DATABASE_URL", file=sys.stderr)
        return 1

    source = Path(args.source)
    if not source.is_absolute():
        source = ROOT / source

    try:
        migrate(source, target, wipe=args.wipe)
    except Exception as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
