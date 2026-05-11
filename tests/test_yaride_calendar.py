"""Фабрика календаря для выбора даты."""

from __future__ import annotations

from unittest import TestCase

from app.yaride_calendar import YarideCalendar, trip_calendar


class YarideCalendarTests(TestCase):
    def test_trip_calendar_returns_configured_instance(self) -> None:
        cal = trip_calendar()
        self.assertIsInstance(cal, YarideCalendar)
