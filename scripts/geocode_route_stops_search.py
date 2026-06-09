"""
Перегеокодирует app/stop_coordinates.json через Яндекс Search API («API Поиска по организациям»).

Зачем: HTTP-Геокодер в Кабинете недоступен для подключения, а Search API
(search-maps.yandex.ru) умеет возвращать координаты по тексту запроса — и для
организаций (Зоопарк, Арена-2000, вокзалы), и для топонимов (улицы, посёлки).
Запросы ограничены рамкой Ярославля (ll+spn+rspn=1), ручные override'ы сохраняются.

Ключ продукта «API Поиска по организациям» положите в .env как YANDEX_SEARCH_KEY
(скрипт также примет YANDEX_GEOCODER_KEY как запасной).

Запуск из корня репозитория:
  py -3 scripts/geocode_route_stops_search.py
  py -3 scripts/geocode_route_stops_search.py --limit 5   # пробный прогон
"""

from __future__ import annotations

import json
import os
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

from dotenv import load_dotenv  # noqa: E402

from app.geo_stops import COORDINATE_OVERRIDES  # noqa: E402
from app.seeds import ROUTE_HIERARCHY  # noqa: E402

OUT_PATH = ROOT / "app" / "stop_coordinates.json"
SEARCH = "https://search-maps.yandex.ru/v1/"
DEFAULT_DELAY_S = 0.25

# Центр Ярославля и охват рамки (ll=lon,lat; spn=dlon,dlat). rspn=1 — строго в рамке.
YAR_LL = "39.87,57.62"
YAR_SPN = "0.45,0.32"
# Грубые границы для отбраковки явных промахов (lat, lon).
LAT_MIN, LAT_MAX = 57.45, 57.85
LON_MIN, LON_MAX = 39.55, 40.15


def build_queries(admin_area: str, title: str) -> list[str]:
    short_title = re.sub(r"[«»\"]", "", title).strip()
    queries = [
        f"{title}, Ярославль",
        f"{short_title}, {admin_area}, Ярославль",
        f"{short_title}, Ярославль",
    ]
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out


def search_one(key: str, q: str, type_: str) -> tuple[float, float] | None:
    """Возвращает (lat, lon) внутри рамки города или None. Геометрия Search API — [lon, lat]."""
    params = urllib.parse.urlencode(
        {
            "apikey": key,
            "text": q,
            "lang": "ru_RU",
            "ll": YAR_LL,
            "spn": YAR_SPN,
            "rspn": 1,
            "results": 1,
            "type": type_,
        }
    )
    req = urllib.request.Request(f"{SEARCH}?{params}", headers={"User-Agent": "YarideBot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise SystemExit(
                f"HTTP {e.code} от Search API: ключ не принят. Подключите «API Поиска по организациям» "
                f"и положите ключ в .env как YANDEX_SEARCH_KEY. Ответ: {e.read().decode('utf-8', 'replace')}"
            ) from e
        return None
    except Exception:
        return None

    feats = data.get("features") or []
    if not feats:
        return None
    coords = feats[0].get("geometry", {}).get("coordinates")
    if not coords or len(coords) < 2:
        return None
    lon, lat = float(coords[0]), float(coords[1])
    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        return None
    return lat, lon


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Максимум остановок (0 = все)")
    args = ap.parse_args()

    load_dotenv()
    key = (os.getenv("YANDEX_SEARCH_KEY") or os.getenv("YANDEX_GEOCODER_KEY") or "").strip()
    if not key:
        raise SystemExit("YANDEX_SEARCH_KEY не задан. Добавьте ключ «API Поиска по организациям» в .env.")
    delay = float(os.getenv("GEOCODE_DELAY", str(DEFAULT_DELAY_S)))

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
        # Сначала как организация/объект (biz), затем как топоним (geo).
        for type_ in ("biz", "geo"):
            for q in build_queries(a, title):
                time.sleep(delay)
                found = search_one(key, q, type_)
                if found:
                    break
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
                "source": "yandex-search",
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
