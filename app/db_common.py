"""Общая логика схемы: сиды и координаты остановок (SQLite и PostgreSQL)."""

from __future__ import annotations

from typing import Any, Protocol

from app.geo_stops import COORDINATE_OVERRIDES, lat_lng_for_stop
from app.seeds import ROUTE_HIERARCHY
from app.sql_dialect import SqlDialect


class _Conn(Protocol):
    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> Any: ...


def seed_route_points(conn: _Conn, dialect: SqlDialect) -> None:
    """Заполнить справочник остановок из seeds.py."""
    row = conn.execute("SELECT COUNT(*) AS cnt FROM route_points").fetchone()
    existing = int(row["cnt"] if hasattr(row, "keys") else row[0])
    if existing > 0:
        trips_row = conn.execute("SELECT COUNT(*) AS cnt FROM trips").fetchone()
        trips_cnt = int(trips_row["cnt"] if hasattr(trips_row, "keys") else trips_row[0])
        if trips_cnt == 0:
            conn.execute("DELETE FROM route_points")

    insert_sql = dialect.insert_ignore_route_point()
    for locality, districts in ROUTE_HIERARCHY.items():
        for district, admin_areas in districts.items():
            d = district if district else ""
            for admin_area, stops in admin_areas.items():
                a = admin_area if admin_area else ""
                for stop_name in stops:
                    conn.execute(insert_sql, (locality, d, a, stop_name))


def fill_route_point_coordinates(conn: _Conn, dialect: SqlDialect) -> None:
    """Проставить координаты остановкам без lat/lng."""
    p = "?"
    rows = conn.execute(
        """
        SELECT id, locality, district, admin_area, title FROM route_points
        WHERE kind = 'stop' AND (latitude IS NULL OR longitude IS NULL)
        """
    ).fetchall()
    for r in rows:
        lat, lng = lat_lng_for_stop(
            str(r["locality"]),
            str(r["district"] or ""),
            str(r["admin_area"] or ""),
            str(r["title"]),
        )
        conn.execute(
            f"UPDATE route_points SET latitude = {p}, longitude = {p} WHERE id = {p}",
            (lat, lng, int(r["id"])),
        )
    for loc, dist, adm, title in COORDINATE_OVERRIDES:
        lat, lng = lat_lng_for_stop(loc, dist, adm, title)
        conn.execute(
            f"""
            UPDATE route_points
            SET latitude = {p}, longitude = {p}
            WHERE kind = 'stop' AND locality = {p}
              AND COALESCE(district, '') = {p}
              AND COALESCE(admin_area, '') = {p}
              AND title = {p}
            """,
            (lat, lng, loc, dist, adm, title),
        )


def apply_route_hierarchy_simplify(conn: _Conn) -> None:
    conn.execute(
        """
        UPDATE route_points SET admin_area = 'Весь Ленинский район'
        WHERE locality = 'Ярославль' AND district = 'Ленинский район'
          AND admin_area IN ('Загородный Сад', 'Пятёрка')
        """
    )
    conn.execute(
        """
        UPDATE route_points SET admin_area = 'Посёлки (малые)'
        WHERE locality = 'Ярославль' AND district = 'Красноперекопский район'
          AND admin_area IN (
            'Бутырки', 'Забелицы', 'Новодуховское', 'Творогово', 'пос. Силикатного завода'
          )
        """
    )
