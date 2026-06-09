"""
Перегеокодирует app/stop_coordinates.json по данным OpenStreetMap (Overpass API), без ключей.

Берёт реальные объекты Ярославля (остановки, станции, крупные POI, улицы) и сопоставляет
их с нашим каталогом по нормализованному названию. Ручные override'ы из app.geo_stops
остаются авторитетными. Ненайденные точки в файл не пишутся — для них останется fallback
(центр района) или их можно добавить вручную.

Запуск из корня репозитория:
  py -3 scripts/geocode_route_stops_osm.py
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.geo_stops import COORDINATE_OVERRIDES  # noqa: E402
from app.seeds import ROUTE_HIERARCHY  # noqa: E402

OUT_PATH = ROOT / "app" / "stop_coordinates.json"
OVERPASS_ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]
BBOX = "57.53,39.70,57.78,40.05"  # south,west,north,east (городская черта Ярославля)

# Служебные слова, которые выкидываем при нормализации названий.
STOPWORDS = {
    "улица",
    "ул",
    "проспект",
    "пр",
    "переулок",
    "пер",
    "бульвар",
    "площадь",
    "пл",
    "набережная",
    "наб",
    "посёлок",
    "поселок",
    "пос",
    "микрорайон",
    "мкр",
    "остановка",
    "станция",
    "по",
    "требованию",
    "район",
    "со",
    "стороны",
    "в",
    "р-н",
}


def normalize(name: str) -> str:
    s = name.lower().replace("ё", "е")
    for ch in "«»\"'()-–—.,/№":
        s = s.replace(ch, " ")
    return " ".join(s.split())


def token_set(name: str) -> frozenset[str]:
    return frozenset(t for t in normalize(name).split() if t and t not in STOPWORDS)


# Два лёгких запроса вместо одного тяжёлого: объекты (остановки/POI/места) и крупные улицы.
QUERY_POI = (
    "[out:json][timeout:60];("
    f'node["highway"="bus_stop"]["name"]({BBOX});'
    f'node["public_transport"~"platform|station"]["name"]({BBOX});'
    f'node["railway"~"station|halt|tram_stop"]["name"]({BBOX});'
    f'nwr["tourism"="zoo"]["name"]({BBOX});'
    f'nwr["leisure"="water_park"]["name"]({BBOX});'
    f'nwr["amenity"~"cinema|university|college|hospital|townhall"]["name"]({BBOX});'
    f'nwr["shop"="mall"]["name"]({BBOX});'
    f'nwr["place"~"suburb|neighbourhood|quarter|village|hamlet|locality"]["name"]({BBOX});'
    ");out center tags;"
)
QUERY_STREETS = (
    "[out:json][timeout:60];("
    f'way["highway"~"^(primary|secondary|tertiary|residential|unclassified|living_street)$"]["name"]({BBOX});'
    ");out center tags;"
)


def _post_overpass(query: str) -> list[dict]:
    data = urllib.parse.urlencode({"data": query}).encode()
    last_err: Exception | None = None
    for url in OVERPASS_ENDPOINTS:
        try:
            print(f"  пробую {url} …", flush=True)
            req = urllib.request.Request(url, data=data, headers={"User-Agent": "YarideBot/1.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read().decode())["elements"]
        except Exception as e:  # noqa: BLE001 — перебираем зеркала, пробуем следующее
            print(f"    не вышло: {e}", flush=True)
            last_err = e
    raise SystemExit(f"Все зеркала Overpass недоступны: {last_err}")


def fetch_osm() -> list[dict]:
    print("Запрос POI/остановок…", flush=True)
    poi = _post_overpass(QUERY_POI)
    print(f"  POI получено: {len(poi)}", flush=True)
    print("Запрос улиц…", flush=True)
    streets = _post_overpass(QUERY_STREETS)
    print(f"  улиц получено: {len(streets)}", flush=True)
    return poi + streets


def coord_of(el: dict) -> tuple[float, float] | None:
    if "lat" in el and "lon" in el:
        return float(el["lat"]), float(el["lon"])
    c = el.get("center")
    if c:
        return float(c["lat"]), float(c["lon"])
    return None


def main() -> None:
    elements = fetch_osm()
    print(f"Получено объектов OSM: {len(elements)}", flush=True)

    # Индексы: точное нормализованное имя и набор токенов → координата.
    exact: dict[str, tuple[float, float]] = {}
    by_tokens: dict[frozenset[str], tuple[float, float]] = {}
    poi_names: list[tuple[str, tuple[float, float]]] = []
    for el in elements:
        name = (el.get("tags") or {}).get("name")
        c = coord_of(el)
        if not name or not c:
            continue
        n = normalize(name)
        exact.setdefault(n, c)
        ts = token_set(name)
        if ts:
            by_tokens.setdefault(ts, c)
        poi_names.append((n, c))

    rows: list[tuple[str, str, str, str]] = []
    for loc, districts in ROUTE_HIERARCHY.items():
        for d, admins in districts.items():
            for a, stops in admins.items():
                for t in stops:
                    rows.append((loc, d, a, t))

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

    matched = 0
    failed: list[tuple[str, str, str, str]] = []
    for loc, d, a, title in rows:
        if (loc, d, a, title) in manual_done:
            continue
        n = normalize(title)
        ts = token_set(title)
        coord: tuple[float, float] | None = None

        if n in exact:
            coord = exact[n]
        elif ts and ts in by_tokens:
            coord = by_tokens[ts]
        else:
            # Подстрочное совпадение: имя остановки содержится в имени OSM-объекта или наоборот.
            best: tuple[int, tuple[float, float]] | None = None
            for pn, pc in poi_names:
                if not pn:
                    continue
                if n and (n in pn or pn in n):
                    score = abs(len(pn) - len(n))
                    if best is None or score < best[0]:
                        best = (score, pc)
            if best is not None:
                coord = best[1]
            elif ts:
                # Совпадение по подмножеству токенов (например, улицы).
                for o_ts, oc in by_tokens.items():
                    if ts and (ts <= o_ts or o_ts <= ts):
                        coord = oc
                        break

        if coord is None:
            failed.append((loc, d, a, title))
            continue
        result.append(
            {
                "locality": loc,
                "district": d,
                "admin_area": a,
                "title": title,
                "lat": coord[0],
                "lon": coord[1],
                "source": "osm",
            }
        )
        matched += 1

    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    total_auto = len(rows) - len(manual_done)
    print(f"\nСовпало по OSM: {matched}/{total_auto}; ручных: {len(manual_done)}; в файле: {len(result)}")
    if failed:
        print(f"\nНе найдено в OSM ({len(failed)}):")
        for f in failed:
            print("  ", f[1], "/", f[2], "/", f[3])


if __name__ == "__main__":
    main()
