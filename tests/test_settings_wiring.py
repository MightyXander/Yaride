from __future__ import annotations

from unittest import TestCase

from app.config import Settings
from app.ui import KeyboardFactory


def _make_settings(**overrides: object) -> Settings:
    base = Settings(bot_token="x", db_path="t.db")
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


class KeyboardFactoryUsesSettingsTests(TestCase):
    def test_seats_keyboard_reflects_seats_choices(self) -> None:
        kf = KeyboardFactory(settings=_make_settings(seats_choices=(1, 2, 5)))
        markup = kf.seats_keyboard()
        texts = [b.text for row in markup.inline_keyboard for b in row]
        self.assertEqual(texts, ["1", "2", "5"])

    def test_price_keyboard_reflects_price_choices(self) -> None:
        kf = KeyboardFactory(settings=_make_settings(price_choices=(50, 99)))
        markup = kf.price_keyboard()
        texts = [b.text for row in markup.inline_keyboard for b in row]
        self.assertEqual(texts, ["50 руб", "99 руб"])

    def test_time_keyboard_reflects_step_and_hours(self) -> None:
        kf = KeyboardFactory(settings=_make_settings(time_step_minutes=60, work_hours_start=8, work_hours_end=10))
        markup = kf.time_keyboard("prefix")
        texts = [b.text for row in markup.inline_keyboard for b in row]
        self.assertEqual(texts, ["08:00", "09:00"])


class KeyboardFactoryBackwardCompatTests(TestCase):
    def test_default_factory_keeps_old_behavior(self) -> None:
        kf = KeyboardFactory()
        seats_texts = [b.text for row in kf.seats_keyboard().inline_keyboard for b in row]
        price_texts = [b.text for row in kf.price_keyboard().inline_keyboard for b in row]
        time_texts = [b.text for row in kf.time_keyboard("p").inline_keyboard for b in row]
        self.assertEqual(seats_texts, ["2", "3", "4"])
        self.assertEqual(price_texts, ["100 руб", "150 руб", "200 руб"])
        self.assertEqual(time_texts[0], "06:00")
        self.assertEqual(time_texts[-1], "22:30")
