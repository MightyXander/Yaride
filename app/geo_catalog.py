"""Загрузка координат остановок из JSON (генерируется scripts/geocode_route_stops.py)."""

from __future__ import annotations

import json
from pathlib import Path


def catalog_path() -> Path:
    return Path(__file__).resolve().parent / "stop_coordinates.json"


def load_stop_coordinates_catalog() -> dict[tuple[str, str, str, str], tuple[float, float]]:
    path = catalog_path()
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[tuple[str, str, str, str], tuple[float, float]] = {}
    if isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict):
                continue
            k = (
                str(row["locality"]),
                str(row["district"]),
                str(row["admin_area"]),
                str(row["title"]),
            )
            out[k] = (float(row["lat"]), float(row["lon"]))
    elif isinstance(raw, dict):
        sep = "|"
        for key_str, v in raw.items():
            parts = key_str.split(sep)
            if len(parts) != 4 or not isinstance(v, list) or len(v) != 2:
                continue
            out[(parts[0], parts[1], parts[2], parts[3])] = (float(v[0]), float(v[1]))
    return out
