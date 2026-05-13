"""Регрессии: мёртвый no-op `add_back_button` удалён, рейтинг-хелпер живёт в `app.formatting`."""

from __future__ import annotations

from unittest import TestCase

from app import bot_support, formatting
from app.ui import KeyboardFactory


class AddBackButtonRemovedTests(TestCase):
    def test_keyboard_factory_no_longer_exposes_add_back_button(self) -> None:
        self.assertFalse(hasattr(KeyboardFactory, "add_back_button"))

    def test_bot_support_no_longer_re_exports_add_back_button(self) -> None:
        self.assertFalse(hasattr(bot_support, "add_back_button"))

    def test_with_back_button_remains_the_supported_helper(self) -> None:
        self.assertTrue(callable(KeyboardFactory.with_back_button))


class PassengerRatingHintRelocatedTests(TestCase):
    def test_helper_is_public_on_formatting_module(self) -> None:
        self.assertTrue(hasattr(formatting, "passenger_rating_hint"))
        self.assertTrue(callable(formatting.passenger_rating_hint))

    def test_no_zero_ratings_yields_explicit_label(self) -> None:
        row = {"rating_count": 0, "rating_avg": 0}
        self.assertEqual(formatting.passenger_rating_hint(row), "нет оценок")

    def test_non_zero_ratings_yield_formatted_label(self) -> None:
        row = {"rating_count": 7, "rating_avg": 4.4}
        self.assertEqual(formatting.passenger_rating_hint(row), "4.4, оценок: 7")

    def test_bot_support_no_longer_re_exports_private_helper(self) -> None:
        self.assertFalse(hasattr(bot_support, "_passenger_rating_hint"))
