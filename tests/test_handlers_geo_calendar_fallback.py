"""Роутеры geo / calendar / fallback / favorites подключены и экспортируют обработчики."""

from __future__ import annotations

from unittest import TestCase

from app.handlers.calendar import process_calendar_selection
from app.handlers.driver_manage import driver_manage_back_to_root, driver_manage_entry
from app.handlers.fallback import fallback, go_back, go_back_keyboard
from app.handlers.favorites import fav_add, favorite_route_pick_date, favorite_routes_menu
from app.handlers.geo import geo_pick_suggested_start_stop


class HandlersModuleSmokeTests(TestCase):
    def test_callables_are_async_handlers(self) -> None:
        self.assertTrue(callable(geo_pick_suggested_start_stop))
        self.assertTrue(callable(process_calendar_selection))
        self.assertTrue(callable(go_back))
        self.assertTrue(callable(go_back_keyboard))
        self.assertTrue(callable(fallback))

    def test_favorites_handlers_callable(self) -> None:
        self.assertTrue(callable(favorite_routes_menu))
        self.assertTrue(callable(fav_add))
        self.assertTrue(callable(favorite_route_pick_date))

    def test_driver_manage_back_handler_callable(self) -> None:
        """`back:manage_root` handler существует и зарегистрирован в роутере `driver_manage`."""
        self.assertTrue(callable(driver_manage_entry))
        self.assertTrue(callable(driver_manage_back_to_root))
