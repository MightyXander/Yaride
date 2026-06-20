"""Тесты на `KeyboardFactory.with_back_button`.

Покрытие:
- `with_back_button` добавляет одну строку с inline-кнопкой `«⬅ Назад»` и `callback_data=f"back:{target}"`,
  не модифицируя исходную клавиатуру.
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
