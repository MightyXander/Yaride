"""Вычисление промежуточных остановок через Яндекс.Маршрутизатор.

Использует YANDEX_ROUTER_KEY (или YANDEX_GEOCODER_KEY как fallback).
При недоступности API возвращает None — вызывающий код обязан мягко обработать это.
"""

from __future__ import annotations

import json
import logging
import math
import os
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

YANDEX_ROUTER_URL = "https://api.routing.yandex.net/v2/route"
STOP_ON_ROUTE_THRESHOLD_M = 200  # ≤200 м — остановка считается «по пути»

Polyline = list[tuple[float, float]]  # [(lat, lon), ...]


def _router_key() -> str:
    return (
        os.getenv("YANDEX_ROUTER_KEY", "").strip()
        or os.getenv("YANDEX_GEOCODER_KEY", "").strip()
    )


def fetch_yandex_polyline(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
) -> Polyline | None:
    """Запрашивает маршрут A→B и возвращает [(lat, lon), ...].

    Возвращает None при любой ошибке (нет ключа, сеть, неизвестный формат).
    """
    key = _router_key()
    if not key:
        logger.warning("Нет ключа YANDEX_ROUTER_KEY/YANDEX_GEOCODER_KEY — промежуточные посадки отключены.")
        return None

    params = urllib.parse.urlencode(
        {
            "apikey": key,
            "waypoints": f"{from_lat},{from_lon}|{to_lat},{to_lon}",
            "mode": "driving",
            "lang": "ru_RU",
        }
    )
    url = f"{YANDEX_ROUTER_URL}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "YarideBot/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:
        logger.warning("Яндекс.Маршрутизатор: ошибка запроса: %s", exc)
        return None

    return _parse_polyline(data)


def _parse_polyline(data: dict) -> Polyline | None:
    """Извлекает [(lat, lon)] из ответа Яндекс.Маршрутизатора v2."""
    try:
        legs = data["route"]["legs"]
        points: Polyline = []
        for leg in legs:
            for step in leg["steps"]:
                for lon, lat in step["polyline"]["points"]:
                    points.append((float(lat), float(lon)))
        return points if points else None
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("Яндекс.Маршрутизатор: не удалось разобрать polyline: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Геометрия
# ---------------------------------------------------------------------------

def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _dist_point_to_segment_m(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> float:
    """Кратчайшее расстояние от точки P до отрезка AB (в метрах, плоская аппроксимация)."""
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return _haversine_m(px, py, ax, ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return _haversine_m(px, py, cx, cy)


def _project_stop(
    lat: float,
    lon: float,
    polyline: Polyline,
) -> tuple[float, int] | None:
    """(min_dist_m, segment_index) — проекция точки на ближайший сегмент polyline."""
    if len(polyline) < 2:
        return None
    best_dist = math.inf
    best_seg = 0
    for i in range(len(polyline) - 1):
        a_lat, a_lon = polyline[i]
        b_lat, b_lon = polyline[i + 1]
        d = _dist_point_to_segment_m(lat, lon, a_lat, a_lon, b_lat, b_lon)
        if d < best_dist:
            best_dist = d
            best_seg = i
    return best_dist, best_seg


# ---------------------------------------------------------------------------
# Основная функция
# ---------------------------------------------------------------------------

def compute_intermediate_stops(
    polyline: Polyline,
    stops: list,
    start_point_id: int,
    end_point_id: int,
    threshold_m: float = STOP_ON_ROUTE_THRESHOLD_M,
) -> list[dict]:
    """Возвращает остановки, лежащие ≤ threshold_m от маршрута, без начальной/конечной.

    `stops` — список строк/dict-like с полями: id, latitude, longitude.
    Результат отсортирован по порядку вдоль маршрута:
        [{"id": int, "order_index": int}, ...]
    """
    excluded = {start_point_id, end_point_id}
    scored: list[tuple[int, int]] = []  # (seg_idx, stop_id)

    for row in stops:
        sid = int(row["id"])
        if sid in excluded:
            continue
        lat = row["latitude"]
        lon = row["longitude"]
        if lat is None or lon is None:
            continue

        result = _project_stop(float(lat), float(lon), polyline)
        if result is None:
            continue

        dist_m, seg_idx = result
        if dist_m <= threshold_m:
            scored.append((seg_idx, sid))

    scored.sort()
    return [{"id": sid, "order_index": i} for i, (_, sid) in enumerate(scored)]


# ---------------------------------------------------------------------------
# Сериализация polyline для хранения в БД
# ---------------------------------------------------------------------------

def polyline_to_json(polyline: Polyline) -> str:
    return json.dumps(polyline)


def polyline_from_json(s: str) -> Polyline | None:
    try:
        data = json.loads(s)
        return [(float(lat), float(lon)) for lat, lon in data]
    except Exception:
        return None
