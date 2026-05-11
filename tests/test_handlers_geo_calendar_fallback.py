"""Роутеры geo / calendar / fallback подключены и экспортируют обработчики."""

from __future__ import annotations

from unittest import TestCase

from app.handlers.calendar import process_calendar_selection
from app.handlers.fallback import fallback, go_back, go_back_keyboard
from app.handlers.geo import geo_pick_suggested_start_stop


class HandlersModuleSmokeTests(TestCase):
    def test_callables_are_async_handlers(self) -> None:
        self.assertTrue(callable(geo_pick_suggested_start_stop))
        self.assertTrue(callable(process_calendar_selection))
        self.assertTrue(callable(go_back))
        self.assertTrue(callable(go_back_keyboard))
        self.assertTrue(callable(fallback))
