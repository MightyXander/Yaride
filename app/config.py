from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    bot_token: str
    db_path: str
    seats_choices: tuple[int, ...] = field(default_factory=lambda: (2, 3, 4))
    price_choices: tuple[int, ...] = field(default_factory=lambda: (100, 150, 200))
    time_step_minutes: int = 30
    work_hours_start: int = 6
    work_hours_end: int = 23
    geo_suggest_limit: int = 5
    geo_suggest_max_km: float = 85.0
    locality_geo_max_km: float = 150.0
    rating_prompt_initial_delay_s: int = 45
    rating_prompt_interval_s: int = 180


def _parse_int_tuple(raw: str, *, name: str) -> tuple[int, ...]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise RuntimeError(f"{name} is empty or invalid: {raw!r}")
    try:
        values = tuple(int(p) for p in parts)
    except ValueError as exc:
        raise RuntimeError(f"{name} must contain integers separated by commas: {raw!r}") from exc
    if not values:
        raise RuntimeError(f"{name} is empty after parsing: {raw!r}")
    return values


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer: {raw!r}") from exc


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a float: {raw!r}") from exc


def _env_int_tuple(name: str, default: tuple[int, ...]) -> tuple[int, ...]:
    raw = os.getenv(name)
    if raw is None:
        return default
    return _parse_int_tuple(raw, name=name)


def load_settings() -> Settings:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    db_path = os.getenv("DB_PATH", "yaride.db").strip() or "yaride.db"
    if not token:
        raise RuntimeError("BOT_TOKEN is not set. Add it to environment or .env file.")
    return Settings(
        bot_token=token,
        db_path=db_path,
        seats_choices=_env_int_tuple("SEATS_CHOICES", (2, 3, 4)),
        price_choices=_env_int_tuple("PRICE_CHOICES", (100, 150, 200)),
        time_step_minutes=_env_int("TIME_STEP_MINUTES", 30),
        work_hours_start=_env_int("WORK_HOURS_START", 6),
        work_hours_end=_env_int("WORK_HOURS_END", 23),
        geo_suggest_limit=_env_int("GEO_SUGGEST_LIMIT", 5),
        geo_suggest_max_km=_env_float("GEO_SUGGEST_MAX_KM", 85.0),
        locality_geo_max_km=_env_float("LOCALITY_GEO_MAX_KM", 150.0),
        rating_prompt_initial_delay_s=_env_int("RATING_PROMPT_INITIAL_DELAY_S", 45),
        rating_prompt_interval_s=_env_int("RATING_PROMPT_INTERVAL_S", 180),
    )
