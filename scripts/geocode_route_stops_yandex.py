"""
Перегеокодирует app/stop_coordinates.json через Яндекс.Геокодер (HTTP API).

Зачем: публичный Photon (OSM) промахивается на общих русских названиях
(часть точек улетала в другие города). Яндекс точнее по РФ; запросы ограничены
рамкой Ярославля (bbox + rspn=1), поэтому результат не уходит за город.

Требуется отдельный ключ продукта «Geocoder API (HTTP)» из Кабинета разработчика
Яндекса (ключ JS API для карт сюда не подходит — даёт 403). Положите его в .env как
YANDEX_GEOCODER_KEY=... (или экспортируйте в окружение).

Запуск из корня репозитория:
  py -3 scripts/geocode_route_stops_yandex.py
  py -3 scripts/geocode_route_stops_yandex.py --limit 5   # пробный прогон
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
GEOCODER = "https://geocode-maps.yandex.ru/1.x/"
DEFAULT_DELAY_S = 0.2

# Рамка Ярославля (lon,lat): результаты геокодера ограничиваем городом.
YAR_BBOX = "39.65,57.50~40.10,57.80"

# Точность Яндекса, которую считаем достаточной (остальное помечаем для ручной проверки).
GOOD_PRECISION = {"exact", "number", "near"}


def build_queries(admin_area: str, title: str) -> list[str]:
    short_title = re.sub(r"[«»\"]", "", title).strip()
    queries = [
        f"Ярославль, {title}",
        f"Ярославль, {admin_area}, {short_title}",
        f"Ярославль, остановка {short_title}",
    ]
    # Убираем дубликаты, сохраняя порядок.
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out


def yandex_geocode(key: str, q: str) -> tuple[float, float, str] | None:
    """Возвращает (lat, lon, precision) или None. Точка Яндекса в формате 'lon lat'."""
    params = urllib.parse.urlencode(
        {
            "apikey": key,
            "format": "json",
            "geocode": q,
            "results": 1,
            "bbox": YAR_BBOX,
            "rspn": 1,
            "lang": "ru_RU",
        }
    )
    req = urllib.request.Request(f"{GEOCODER}?{params}", headers={"User-Agent": "YarideBot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise SystemExit(
                "HTTP 403 от Яндекс.Геокодера: ключ не подходит для Geocoder API (HTTP). "
                "Создайте ключ продукта «Geocoder API (HTTP)» и положите в .env как YANDEX_GEOCODER_KEY."
            ) from e
        return None
    except Exception:
        return None

    members = data.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])
    if not members:
        return None
    obj = members[0]["GeoObject"]
    pos = obj["Point"]["pos"]
    lon_s, lat_s = pos.split()
    precision = obj.get("metaDataProperty", {}).get("GeocoderMetaData", {}).get("precision", "other")
    return float(lat_s), float(lon_s), str(precision)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Максимум остановок (0 = все)")
    args = ap.parse_args()

    load_dotenv()
    key = (os.getenv("YANDEX_GEOCODER_KEY") or "").strip()
    if not key:
        raise SystemExit("YANDEX_GEOCODER_KEY не задан. Добавьте ключ Geocoder API (HTTP) в .env.")

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

    low_precision: list[tuple[str, str, str, str, str]] = []
    failed: list[tuple[str, str, str, str]] = []

    for i, key_t in enumerate(rows):
        if key_t in manual_done:
            continue
        loc, d, a, title = key_t
        found: tuple[float, float, str] | None = None
        for q in build_queries(a, title):
            time.sleep(delay)
            found = yandex_geocode(key, q)
            if found:
                break

        if not found:
            failed.append(key_t)
            print(f"[FAIL] {d} / {a} / {title}")
            continue

        lat, lon, precision = found
        result.append(
            {
                "locality": loc,
                "district": d,
                "admin_area": a,
                "title": title,
                "lat": lat,
                "lon": lon,
                "source": "yandex",
                "precision": precision,
            }
        )
        flag = "" if precision in GOOD_PRECISION else f"  ⚠ precision={precision}"
        if precision not in GOOD_PRECISION:
            low_precision.append((loc, d, a, title, precision))
        print(f"[ok {i + 1}/{len(rows)}] {title[:40]}{flag}")

    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nЗаписано {len(result)} координат в {OUT_PATH}")
    if low_precision:
        print(f"\nНизкая точность у {len(low_precision)} точек (проверить вручную / добавить override):")
        for _loc, d, a, title, p in low_precision:
            print(f"  [{p}] {d} / {a} / {title}")
    if failed:
        print(f"\nНе найдено {len(failed)} точек (нужен ручной override в geo_stops.py):")
        for f in failed:
            print(" ", f)


if __name__ == "__main__":
    main()
