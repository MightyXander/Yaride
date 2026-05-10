from __future__ import annotations

import os
from unittest import TestCase
from unittest.mock import patch

from app.config import Settings, load_settings


def _clean_env() -> dict[str, str]:
    keep = {"PATH"}
    return {k: v for k, v in os.environ.items() if k in keep}


class LoadSettingsDefaultsTests(TestCase):
    def test_defaults_when_only_bot_token_set(self) -> None:
        env = _clean_env() | {"BOT_TOKEN": "tok"}
        with patch.dict(os.environ, env, clear=True):
            s = load_settings()
        self.assertEqual(s.bot_token, "tok")
        self.assertEqual(s.db_path, "yaride.db")
        self.assertEqual(s.seats_choices, (2, 3, 4))
        self.assertEqual(s.price_choices, (100, 150, 200))
        self.assertEqual(s.time_step_minutes, 30)
        self.assertEqual(s.work_hours_start, 6)
        self.assertEqual(s.work_hours_end, 23)
        self.assertEqual(s.geo_suggest_limit, 5)
        self.assertAlmostEqual(s.geo_suggest_max_km, 85.0)
        self.assertAlmostEqual(s.locality_geo_max_km, 150.0)
        self.assertEqual(s.rating_prompt_initial_delay_s, 45)
        self.assertEqual(s.rating_prompt_interval_s, 180)


class LoadSettingsOverridesTests(TestCase):
    def test_overrides_from_env(self) -> None:
        env = _clean_env() | {
            "BOT_TOKEN": "tok",
            "DB_PATH": "custom.db",
            "SEATS_CHOICES": "1, 2, 3, 4, 5",
            "PRICE_CHOICES": "50,100",
            "TIME_STEP_MINUTES": "15",
            "WORK_HOURS_START": "5",
            "WORK_HOURS_END": "22",
            "GEO_SUGGEST_LIMIT": "10",
            "GEO_SUGGEST_MAX_KM": "60.0",
            "LOCALITY_GEO_MAX_KM": "200.5",
            "RATING_PROMPT_INITIAL_DELAY_S": "30",
            "RATING_PROMPT_INTERVAL_S": "120",
        }
        with patch.dict(os.environ, env, clear=True):
            s = load_settings()
        self.assertEqual(s.db_path, "custom.db")
        self.assertEqual(s.seats_choices, (1, 2, 3, 4, 5))
        self.assertEqual(s.price_choices, (50, 100))
        self.assertEqual(s.time_step_minutes, 15)
        self.assertEqual(s.work_hours_start, 5)
        self.assertEqual(s.work_hours_end, 22)
        self.assertEqual(s.geo_suggest_limit, 10)
        self.assertAlmostEqual(s.geo_suggest_max_km, 60.0)
        self.assertAlmostEqual(s.locality_geo_max_km, 200.5)
        self.assertEqual(s.rating_prompt_initial_delay_s, 30)
        self.assertEqual(s.rating_prompt_interval_s, 120)


class LoadSettingsRejectsInvalidTests(TestCase):
    def test_invalid_seats_choices_raises(self) -> None:
        env = _clean_env() | {"BOT_TOKEN": "tok", "SEATS_CHOICES": "abc,2"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError):
                load_settings()

    def test_empty_seats_choices_raises(self) -> None:
        env = _clean_env() | {"BOT_TOKEN": "tok", "SEATS_CHOICES": ""}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError):
                load_settings()

    def test_invalid_geo_km_raises(self) -> None:
        env = _clean_env() | {"BOT_TOKEN": "tok", "GEO_SUGGEST_MAX_KM": "not-a-float"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError):
                load_settings()

    def test_missing_bot_token_raises(self) -> None:
        env = _clean_env()
        with patch.dict(os.environ, env, clear=True):
            with patch("app.config.load_dotenv"):
                with self.assertRaises(RuntimeError):
                    load_settings()
