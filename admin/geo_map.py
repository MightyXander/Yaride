"""Подготовка остановок для карты в админке."""

from __future__ import annotations

import sqlite3
from typing import Any

from app.geo_stops import DEFAULT_CENTER, lat_lng_for_stop


def stops_for_admin_map(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Сериализовать остановки для Leaflet: сохранённые координаты или оценка из geo_stops."""
    out: list[dict[str, Any]] = []
    for row in rows:
        lat = row["latitude"]
        lng = row["longitude"]
        saved = lat is not None and lng is not None
        if saved:
            lat_f, lng_f = float(lat), float(lng)
        else:
            lat_f, lng_f = lat_lng_for_stop(
                row["locality"],
                row["district"] or "",
                row["admin_area"] or "",
                row["title"],
            )
        out.append(
            {
                "id": int(row["id"]),
                "title": row["title"],
                "locality": row["locality"],
                "district": row["district"] or "",
                "admin_area": row["admin_area"] or "",
                "latitude": lat_f,
                "longitude": lng_f,
                "saved": saved,
            }
        )
    return out


def map_center_for_point(
    *,
    latitude: float | None,
    longitude: float | None,
    locality: str = "",
    district: str = "",
    admin_area: str = "",
    title: str = "",
) -> tuple[float, float, bool]:
    """Центр карты для одной остановки: (lat, lng, coords_saved)."""
    if latitude is not None and longitude is not None:
        return float(latitude), float(longitude), True
    if title:
        lat, lng = lat_lng_for_stop(locality, district, admin_area, title)
        return lat, lng, False
    return DEFAULT_CENTER[0], DEFAULT_CENTER[1], False
