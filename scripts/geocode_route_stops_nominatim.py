"""
Перегеокодирует app/stop_coordinates.json через Nominatim (OSM) с жёсткой рамкой Ярославля.

В отличие от старого geocode_route_stops.py здесь задан viewbox + bounded=1, поэтому
результаты не уходят за пределы города (раньше часть точек улетала в другие регионы).
Ручные override'ы из app.geo_stops сохраняются как авторитетные (source=manual).

Публичный Nominatim требует не чаще ~1 запроса/с и валидный User-Agent.
Запуск из корня репозитория:
  py -3 scripts/geocode_route_stops_nominatim.py
  py -3 scripts/geocode_route_stops_nominatim.py --limit 5   # пробный прогон
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.geo_stops import COORDINATE_OVERRIDES  # noqa: E402
from app.seeds import ROUTE_HIERARCHY  # noqa: E402

OUT_PATH = ROOT / "app" / "stop_coordinates.json"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
UA = "YarideBot/1.0 (carpool telegram bot; contact: yaride-local-dev)"
DELAY_S = 1.1

# viewbox = lon_min,lat_max,lon_max,lat_min (рамка Ярославля); bounded=1 — только внутри неё.
YAR_VIEWBOX = "39.65,57.80,40.10,57.50"


def build_queries(admin_area: str, title: str) -> list[str]:
    short_title = re.sub(r"[«»\"]", "", title).strip()
    queries = [
        f"{title}, Ярославль",
        f"{short_title}, {admin_area}, Ярославль",
        f"остановка {short_title}, Ярославль",
    ]
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out


def nominatim_search(q: str) -> tuple[float, float] | None:
    params = urllib.parse.urlencode(
        {
            "q": q,
            "format": "json",
            "limit": 1,
            "accept-language": "ru",
            "viewbox": YAR_VIEWBOX,
            "bounded": 1,
        }
    )
    req = urllib.request.Request(f"{NOMINATIM}?{params}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            time.sleep(30)
        return None
    except Exception:
        return None
    if not data:
        return None
    return float(data[0]["lat"]), float(data[0]["lon"])


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Максимум остановок (0 = все)")
    args = ap.parse_args()

    rows: list[tuple[str, str, str, str]] = []
    for loc, districts in ROUTE_HIERARCHY.items():
        for d, admins in districts.items():
            for a, stops in admins.items():
                for t in stops:
                    rows.append((loc, d, a, t))
    if args.limit:
        rows = rows[: args.limit]

    result: list[dict[str, object]] = []
    manual_done: set[tuple[str, str, str, str]] = set()
    for key_t, (lat, lon) in COORDINATE_OVERRIDES.items():
        loc, d, a, title = key_t
        result.append(
            {
                "locality": loc,
                "district": d,
                "admin_area": a,
                "title": title,
                "lat": lat,
                "lon": lon,
                "source": "manual",
            }
        )
        manual_done.add(key_t)

    failed: list[tuple[str, str, str, str]] = []
    for i, key_t in enumerate(rows):
        if key_t in manual_done:
            continue
        loc, d, a, title = key_t
        found: tuple[float, float] | None = None
        for q in build_queries(a, title):
            time.sleep(DELAY_S)
            found = nominatim_search(q)
            if found:
                break

        if not found:
            failed.append(key_t)
            print(f"[FAIL] {d} / {a} / {title}")
            continue

        lat, lon = found
        result.append(
            {
                "locality": loc,
                "district": d,
                "admin_area": a,
                "title": title,
                "lat": lat,
                "lon": lon,
                "source": "nominatim",
            }
        )
        print(f"[ok {i + 1}/{len(rows)}] {title[:40]}")

    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nЗаписано {len(result)} координат в {OUT_PATH}")
    if failed:
        print(f"\nНе найдено {len(failed)} точек (останутся на центре района — нужен ручной override):")
        for f in failed:
            print(" ", f)


if __name__ == "__main__":
    main()
