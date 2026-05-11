"""Тесты на `KeyboardFactory.with_back_button` и наличие inline-back в root-меню.

Покрытие:
- `with_back_button` добавляет одну строку с inline-кнопкой `«⬅ Назад»` и `callback_data=f"back:{target}"`,
  не модифицируя исходную клавиатуру.
- Все root-меню (Управление / Мои брони / Избранные / Аккаунт) после оборачивания содержат `back:menu`.
- driver_trip_detail и driver_thr_menu (подменю) используют `back:manage_root`.
"""

from __future__ import annotations

from unittest import TestCase

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.ui import KeyboardFactory


class WithBackButtonContractTests(TestCase):
    def setUp(self) -> None:
        self.kb = KeyboardFactory()

    @staticmethod
    def _sample_markup() -> InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        b.button(text="A", callback_data="a")
        b.button(text="B", callback_data="b")
        b.adjust(1)
        return b.as_markup()

    def test_appends_one_row_with_back_button(self) -> None:
        markup = self._sample_markup()
        before_rows = len(markup.inline_keyboard)
        result = self.kb.with_back_button(markup, target="menu")
        self.assertEqual(len(result.inline_keyboard), before_rows + 1)
        last_row = result.inline_keyboard[-1]
        self.assertEqual(len(last_row), 1)
        self.assertEqual(last_row[0].callback_data, "back:menu")
        self.assertIn("Назад", last_row[0].text)

    def test_default_target_is_menu(self) -> None:
        result = self.kb.with_back_button(self._sample_markup())
        self.assertEqual(result.inline_keyboard[-1][0].callback_data, "back:menu")

    def test_custom_target_renders_correct_callback(self) -> None:
        result = self.kb.with_back_button(self._sample_markup(), target="manage_root")
        self.assertEqual(result.inline_keyboard[-1][0].callback_data, "back:manage_root")

    def test_original_markup_is_not_mutated(self) -> None:
        markup = self._sample_markup()
        snapshot = [list(row) for row in markup.inline_keyboard]
        self.kb.with_back_button(markup, target="menu")
        self.assertEqual([list(row) for row in markup.inline_keyboard], snapshot)


class RootMenuBackButtonsTests(TestCase):
    """Каждое root-меню (то, что открывается reply-кнопкой главного меню) должно содержать `back:menu`."""

    def setUp(self) -> None:
        self.kb = KeyboardFactory()

    @staticmethod
    def _flat_callbacks(markup: InlineKeyboardMarkup) -> list[str]:
        return [btn.callback_data for row in markup.inline_keyboard for btn in row if btn.callback_data]

    def test_driver_manage_root_with_open_trips_has_back_menu(self) -> None:
        trips = [
            {
                "id": 7,
                "seats_total": 4,
                "seats_booked": 1,
                "start_title": "Yaroslavl",
                "end_title": "Moscow",
            }
        ]
        inner = self.kb.driver_manage_root_keyboard(trips)
        wrapped = self.kb.with_back_button(inner, target="menu")
        self.assertIn("back:menu", self._flat_callbacks(wrapped))

    def test_driver_rating_threshold_root_has_back_menu(self) -> None:
        wrapped = self.kb.with_back_button(self.kb.driver_rating_threshold_keyboard(), target="menu")
        self.assertIn("back:menu", self._flat_callbacks(wrapped))

    def test_cancel_booking_root_has_back_menu(self) -> None:
        bookings = [{"id": 1, "trip_id": 9, "status": "active"}]
        wrapped = self.kb.with_back_button(self.kb.cancel_booking_keyboard(bookings), target="menu")
        self.assertIn("back:menu", self._flat_callbacks(wrapped))

    def test_favorite_routes_root_has_back_menu(self) -> None:
        rows = [{"id": 1, "start_title": "A", "end_title": "B"}]
        wrapped = self.kb.with_back_button(self.kb.favorite_routes_keyboard(rows), target="menu")
        self.assertIn("back:menu", self._flat_callbacks(wrapped))

    def test_account_root_has_back_menu_and_no_account_main_menu(self) -> None:
        inner = self.kb.account_menu_keyboard(show_become_driver=True)
        wrapped = self.kb.with_back_button(inner, target="menu")
        cbs = self._flat_callbacks(wrapped)
        self.assertIn("back:menu", cbs)
        self.assertNotIn("account:main_menu", cbs)


class SubMenuBackButtonsTests(TestCase):
    """Подменю в «Управление» (детали поездки и порог рейтинга) должны вести в корень управления."""

    def setUp(self) -> None:
        self.kb = KeyboardFactory()

    @staticmethod
    def _flat_callbacks(markup: InlineKeyboardMarkup) -> list[str]:
        return [btn.callback_data for row in markup.inline_keyboard for btn in row if btn.callback_data]

    def test_driver_trip_detail_with_manage_root_back(self) -> None:
        inner = self.kb.driver_trip_detail_keyboard(trip_id=42, bookings=[])
        wrapped = self.kb.with_back_button(inner, target="manage_root")
        self.assertIn("back:manage_root", self._flat_callbacks(wrapped))

    def test_driver_rating_threshold_submenu_with_manage_root_back(self) -> None:
        wrapped = self.kb.with_back_button(self.kb.driver_rating_threshold_keyboard(), target="manage_root")
        self.assertIn("back:manage_root", self._flat_callbacks(wrapped))
