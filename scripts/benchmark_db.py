"""
Синтетическая нагрузка для оценки запросов с индексами этапа 2.
Запуск из корня репозитория: py -3 scripts/benchmark_db.py
Результаты дописываются в scripts/benchmark_baseline.txt
"""

from __future__ import annotations

import argparse
import random
import sys
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

N_USERS = 1000
N_TRIPS = 1000
N_BOOKINGS = 5000
N_RATINGS = 1000
ROUTE_PAIRS = 200


def _drop_etap2_indexes(conn) -> None:
    for name in (
        "idx_trips_status_date_route",
        "idx_bookings_passenger_status",
        "idx_bookings_trip_status",
        "idx_trip_ratings_rated",
        "idx_trip_ratings_trip_rater_rated",
        "idx_rating_prompts_trip_rater_rated",
    ):
        conn.execute(f"DROP INDEX IF EXISTS {name}")


def _run_benchmark(db_path: str, *, with_indexes: bool) -> dict[str, float]:
    from app.db import Database
    from app.repo import Repo

    if Path(db_path).exists():
        Path(db_path).unlink()
    db = Database(db_path)
    db.init_schema()
    repo = Repo(db)
    rng = random.Random(42)

    with db.transaction() as conn:
        rps = conn.execute("SELECT id FROM route_points ORDER BY id").fetchall()
        point_ids = [int(r["id"]) for r in rps]
        if len(point_ids) < 2:
            raise RuntimeError("Нужно ≥2 route_points из схемы.")
        pair_list: list[tuple[int, int]] = []
        for _ in range(ROUTE_PAIRS):
            a, b = rng.sample(point_ids, 2)
            pair_list.append((a, b))

        for i in range(N_USERS):
            role = "driver" if i % 2 == 0 else "passenger"
            tg = 10_000 + i
            if role == "driver":
                conn.execute(
                    """
                    INSERT INTO users(tg_user_id, name, username, role, dl_series_number, dl_valid_until)
                    VALUES (?, ?, NULL, 'driver', ?, '2030-01-01')
                    """,
                    (tg, f"u{i}", f"AB{i % 900000:06d}"),
                )
            else:
                conn.execute(
                    "INSERT INTO users(tg_user_id, name, username, role) VALUES (?, ?, NULL, 'passenger')",
                    (tg, f"u{i}"),
                )

        drivers = conn.execute(
            "SELECT id FROM users WHERE role = 'driver' ORDER BY id"
        ).fetchall()
        passenger_rows = conn.execute(
            "SELECT id FROM users WHERE role = 'passenger' ORDER BY id"
        ).fetchall()
        driver_ids = [int(r["id"]) for r in drivers]
        passenger_ids = [int(r["id"]) for r in passenger_rows]

        trip_ids: list[int] = []
        base_date = date(2026, 6, 1)
        for j in range(N_TRIPS):
            sp, ep = pair_list[j % len(pair_list)]
            dr = driver_ids[j % len(driver_ids)]
            conn.execute(
                """
                INSERT INTO trips(
                    driver_id, start_point_id, end_point_id,
                    trip_date, departure_time, time_slot,
                    price_rub, seats_total, seats_booked, status
                )
                VALUES (?, ?, ?, ?, ?, ?, 100, 4, 0, 'open')
                """,
                (
                    dr,
                    sp,
                    ep,
                    base_date.isoformat(),
                    f"{8 + (j % 10):02d}:00",
                    f"{8 + (j % 10):02d}:00",
                ),
            )
            tid = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            trip_ids.append(tid)

        added = 0
        t_idx = 0
        attempts = 0
        max_attempts = N_BOOKINGS * 50
        while added < N_BOOKINGS and attempts < max_attempts:
            attempts += 1
            tid = trip_ids[t_idx % len(trip_ids)]
            t_idx += 1
            pid = passenger_ids[rng.randrange(len(passenger_ids))]
            try:
                conn.execute(
                    "INSERT INTO bookings(trip_id, passenger_id, status) VALUES (?, ?, 'active')",
                    (tid, pid),
                )
                conn.execute(
                    "UPDATE trips SET seats_booked = seats_booked + 1 WHERE id = ? AND seats_booked < seats_total",
                    (tid,),
                )
                added += 1
            except Exception:
                continue

        for _ in range(N_RATINGS):
            tid = trip_ids[rng.randrange(len(trip_ids))]
            tr = conn.execute(
                "SELECT driver_id FROM trips WHERE id = ?",
                (tid,),
            ).fetchone()
            if not tr:
                continue
            dr_id = int(tr["driver_id"])
            b = conn.execute(
                "SELECT passenger_id FROM bookings WHERE trip_id = ? AND status = 'active' LIMIT 1",
                (tid,),
            ).fetchone()
            if not b:
                continue
            p_id = int(b["passenger_id"])
            if rng.random() < 0.5:
                ra, rd = p_id, dr_id
            else:
                ra, rd = dr_id, p_id
            try:
                conn.execute(
                    """
                    INSERT INTO trip_ratings(trip_id, rater_user_id, rated_user_id, stars)
                    VALUES (?, ?, ?, ?)
                    """,
                    (tid, ra, rd, 1 + rng.randint(0, 4)),
                )
            except Exception:
                pass

    if not with_indexes:
        with db.transaction() as conn:
            _drop_etap2_indexes(conn)

    sp0, ep0 = pair_list[0]
    trip_date = base_date.isoformat()
    dep = "08:00"
    now = datetime.combine(base_date, datetime.min.time()) + timedelta(days=1)

    t0 = time.perf_counter()
    repo.trips.find_open_trips(sp0, ep0, trip_date, dep)
    find_open_ms = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    repo.ratings.list_pending_rating_prompts(now)
    prompts_ms = (time.perf_counter() - t1) * 1000

    db.close()

    return {"find_open_trips_ms": find_open_ms, "list_pending_rating_prompts_ms": prompts_ms}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--compare-no-indexes",
        action="store_true",
        help="Дополнительно замерить после DROP INDEX (остальная схема без изменений).",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    baseline_path = root / "scripts" / "benchmark_baseline.txt"

    lines: list[str] = []
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    lines.append(f"# benchmark_db.py — {stamp}")

    with tempfile.TemporaryDirectory() as td:
        db_with = Path(td) / "bench.db"
        m_with = _run_benchmark(str(db_with), with_indexes=True)
        lines.append(f"with_indexes find_open_trips_ms={m_with['find_open_trips_ms']:.4f}")
        lines.append(f"with_indexes list_pending_rating_prompts_ms={m_with['list_pending_rating_prompts_ms']:.4f}")

        if args.compare_no_indexes:
            db_wo = Path(td) / "bench_no_idx.db"
            m_wo = _run_benchmark(str(db_wo), with_indexes=False)
            lines.append(f"no_etap2_indexes find_open_trips_ms={m_wo['find_open_trips_ms']:.4f}")
            lines.append(
                f"no_etap2_indexes list_pending_rating_prompts_ms={m_wo['list_pending_rating_prompts_ms']:.4f}"
            )

    text = "\n".join(lines) + "\n"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    with baseline_path.open("a", encoding="utf-8") as f:
        f.write(text)

    print(text)


if __name__ == "__main__":
    main()
