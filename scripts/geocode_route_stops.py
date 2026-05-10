"""
Один раз заполняет app/stop_coordinates.json координатами по данным OSM.

По умолчанию используется Photon (Komoot) — лучше переносит массовые запросы.
Опционально: Nominatim (GEOCODE_ENGINE=nominatim или both), не чаще ~1 запрос/с.
Запуск из корня репозитория:
  py -3 scripts/geocode_route_stops.py
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

from app.geo_stops import COORDINATE_OVERRIDES  # noqa: E402
from app.seeds import ROUTE_HIERARCHY  # noqa: E402

OUT_PATH = ROOT / "app" / "stop_coordinates.json"
UA = "YarideBot/1.0 (carpool telegram bot; contact: yaride-local-dev)"
PHOTON = "https://photon.komoot.io/api/"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
DEFAULT_REQUEST_DELAY_S = 1.0
NOMINATIM_DELAY_S = 2.0


def _city_context(locality: str) -> str:
    if locality == "Ярославль":
        return "Ярославль"
    if locality == "Ростов Великий":
        return "Ростов Великий"
    return locality


def build_queries(locality: str, district: str, admin_area: str, title: str) -> list[str]:
    """Сначала полное название + город; при необходимости — без кавычек и с подрайоном."""
    city = _city_context(locality)
    short_title = re.sub(r"[«»\"]", "", title).strip()
    queries = [
        f"{title}, {city}, Россия",
        f"{short_title}, {admin_area}, {city}, Россия",
        f"остановка {short_title}, {city}, Россия",
    ]
    return queries


def photon_search(q: str) -> tuple[float, float] | None:
    """Photon возвращает координаты из OSM; геометрия GeoJSON — [lon, lat]."""
    # Не передавать lang=ru — публичный photon.komoot.io на части запросов отвечает 400.
    params = urllib.parse.urlencode({"q": q, "limit": 1})
    url = f"{PHOTON}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None
    features = data.get("features") or []
    if not features:
        return None
    lon, lat = features[0]["geometry"]["coordinates"][:2]
    return float(lat), float(lon)


def nominatim_search(q: str) -> tuple[float, float] | None:
    params = urllib.parse.urlencode({"q": q, "format": "json", "limit": 1, "accept-language": "ru"})
    url = f"{NOMINATIM}?{params}"
    backoff_s = 45
    for attempt in range(6):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 5:
                print(f"[429] пауза {backoff_s}s (попытка {attempt + 1}/6)...")
                time.sleep(backoff_s)
                backoff_s = min(int(backoff_s * 1.5), 300)
                continue
            return None
        except Exception:
            return None
        if not data:
            return None
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
        return lat, lon
    return None


def _geocode_one(engine: str, q: str, delay: float, nominatim_delay: float) -> tuple[tuple[float, float] | None, str]:
    """Возвращает ((lat, lon) или None, метка источника для JSON)."""
    if engine == "photon":
        time.sleep(delay)
        c = photon_search(q)
        return c, "photon"
    if engine == "nominatim":
        time.sleep(nominatim_delay)
        c = nominatim_search(q)
        return c, "nominatim"
    raise ValueError(engine)


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

    manual_done: set[tuple[str, str, str, str]] = set()
    result: list[dict[str, object]] = []
    for key, (lat, lon) in COORDINATE_OVERRIDES.items():
        loc, d, a, title = key
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
        manual_done.add(key)

    failed: list[tuple[str, str, str, str]] = []

    delay = float(os.environ.get("GEOCODE_DELAY", str(DEFAULT_REQUEST_DELAY_S)))
    nominatim_delay = float(os.environ.get("GEOCODE_NOMINATIM_DELAY", str(NOMINATIM_DELAY_S)))
    engine_env = (os.environ.get("GEOCODE_ENGINE") or "photon").strip().lower()
    if engine_env not in ("photon", "nominatim", "both"):
        engine_env = "photon"
    single_pass = os.environ.get("GEOCODE_SINGLE_PASS") == "1"

    for i, key in enumerate(rows):
        if key in manual_done:
            continue
        loc, d, a, title = key
        coord: tuple[float, float] | None = None
        source_tag = "photon"
        qs = build_queries(loc, d, a, title)
        if single_pass:
            qs = qs[:1]

        engines: list[str]
        if engine_env == "both":
            engines = ["photon", "nominatim"]
        else:
            engines = [engine_env]

        for q in qs:
            if coord:
                break
            for eng in engines:
                if eng == "photon":
                    coord, source_tag = _geocode_one("photon", q, delay, nominatim_delay)
                else:
                    coord, source_tag = _geocode_one("nominatim", q, delay, nominatim_delay)
                if coord:
                    break

        if coord:
            result.append(
                {
                    "locality": loc,
                    "district": d,
                    "admin_area": a,
                    "title": title,
                    "lat": coord[0],
                    "lon": coord[1],
                    "source": source_tag,
                }
            )
            print(f"[ok {i + 1}/{len(rows)}] {title[:40]}...")
        else:
            failed.append(key)
            print(f"[FAIL] {loc} / {d} / {a} / {title}")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Written {len(result)} coords to {OUT_PATH}")
    if failed:
        print(f"FAILED {len(failed)} stops — используйте ручные дополнения в geo_stops.py")
        for f in failed:
            print(" ", f)


if __name__ == "__main__":
    main()
