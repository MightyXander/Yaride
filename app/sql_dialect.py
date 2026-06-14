"""SQL-фрагменты, зависящие от диалекта (SQLite vs PostgreSQL)."""

from __future__ import annotations

from typing import Literal

DialectName = Literal["sqlite", "postgres"]


class SqlDialect:
    def __init__(self, name: DialectName) -> None:
        self.name = name

    @property
    def is_sqlite(self) -> bool:
        return self.name == "sqlite"

    def placeholder(self) -> str:
        return "?" if self.is_sqlite else "%s"

    def trip_departure_lte_now(self) -> str:
        if self.is_sqlite:
            return (
                "datetime(trim(t.trip_date) || ' ' || trim(COALESCE(t.departure_time, '00:00'))) "
                "<= datetime('now', 'localtime')"
            )
        return (
            "(trim(t.trip_date) || ' ' || trim(COALESCE(t.departure_time, '00:00')))::timestamp "
            "<= NOW()"
        )

    def trip_departure_lte_param(self) -> str:
        p = self.placeholder()
        if self.is_sqlite:
            return f"datetime(trim(t.trip_date) || ' ' || trim(t.departure_time)) <= datetime({p})"
        return f"(trim(t.trip_date) || ' ' || trim(t.departure_time))::timestamp <= {p}::timestamp"

    def days_ago_param(self, days: int) -> str:
        if self.is_sqlite:
            return f"-{days} days"
        return f"{days} days"

    def days_ago_sql(self, column: str) -> str:
        p = self.placeholder()
        if self.is_sqlite:
            return f"datetime({column}) >= datetime('now', {p})"
        return f"{column} >= NOW() - ({p})::interval"

    def insert_ignore_rating_prompt(self) -> str:
        if self.is_sqlite:
            return """
                INSERT OR IGNORE INTO rating_prompts_sent(trip_id, rater_user_id, rated_user_id)
                VALUES (?, ?, ?)
            """
        return """
            INSERT INTO rating_prompts_sent(trip_id, rater_user_id, rated_user_id)
            VALUES (?, ?, ?)
            ON CONFLICT (trip_id, rater_user_id, rated_user_id) DO NOTHING
        """

    def insert_ignore_route_point(self) -> str:
        if self.is_sqlite:
            return """
                INSERT OR IGNORE INTO route_points(locality, district, admin_area, title, kind)
                VALUES (?, ?, ?, ?, 'stop')
            """
        return """
            INSERT INTO route_points(locality, district, admin_area, title, kind)
            VALUES (?, ?, ?, ?, 'stop')
            ON CONFLICT (locality, district, admin_area, title) DO NOTHING
        """

    def adapt_sql(self, sql: str) -> str:
        if self.is_sqlite:
            return sql
        return sql.replace("?", "%s")
