# Этап 0 — Гигиена и основания: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Подготовить фундамент перед Этапами 1-4: убрать `BOT_TOKEN` из репо, подключить `ruff`, перенести UX-константы в `app/config.py`, завести таблицу `schema_version`, поправить формат логов.

**Architecture:** Без изменения поведения handler'ов и схемы данных кроме новой таблицы `schema_version`. Изменения изолированы в `app/config.py`, `app/db.py`, `app/bot.py` (только импорты и логи), `app/ui.py` (использует `KeyboardFactory(settings=...)` опционально или через прокинутые значения). Тестирование через `unittest` (текущий toolchain проекта), без `pytest`.

**Tech Stack:** Python 3.14, aiogram 3.x, SQLite stdlib, `python-dotenv`, новая dev-зависимость `ruff`, `unittest`.

**Spec reference:** `docs/superpowers/specs/2026-05-11-etap-0-hygiene-and-foundations.md`.

---

## Task 0: Pre-flight — изоляция работы

**Files:** ничего не создаётся в коде.

- [ ] **Step 1: Зафиксировать или отложить текущие незакоммиченные изменения**

Сейчас в working tree есть незакоммиченная работа по `2026-05-10-trip-search-geo-retry-design.md` (`app/bot.py`, `app/trip_flow.py`, `tests/test_trip_flow.py`). Решить с владельцем: закоммитить их отдельно или сделать `git stash` до конца этапа.

Run (если коммит):

```bash
git add app/bot.py app/trip_flow.py tests/test_trip_flow.py
git commit -m "feat(geo): удаление пользовательских геосообщений после выбора остановки"
```

Run (если stash):

```bash
git stash push -m "geo-retry WIP"
```

Expected: `git status` показывает чистое working tree (только untracked spec'и из 2026-05-11).

- [ ] **Step 2: Закоммитить новые спеки отдельным коммитом**

```bash
git add docs/superpowers/specs/2026-05-11-audit-and-roadmap.md \
        docs/superpowers/specs/2026-05-11-etap-0-hygiene-and-foundations.md \
        docs/superpowers/specs/2026-05-11-etap-1-data-resilience.md \
        docs/superpowers/specs/2026-05-11-etap-2-db-performance.md \
        docs/superpowers/specs/2026-05-11-etap-3-architecture-refactor.md \
        docs/superpowers/specs/2026-05-11-etap-4-chat-ux.md \
        docs/superpowers/plans/2026-05-11-etap-0-hygiene-and-foundations.md
git commit -m "docs: roadmap аудита и спеки этапов 0-4 + план этапа 0"
```

- [ ] **Step 3: Создать рабочую ветку**

```bash
git checkout -b etap-0-hygiene
```

- [ ] **Step 4: Зафиксировать зелёный baseline тестов**

```bash
py -3 -m unittest discover -s tests -v
```

Expected: `Ran 32 tests` (или больше, если geo-retry уже добавил), `OK`.

---

## Task 1: `.gitignore`, `.env.example`, удаление `.env` из tracked

**Files:**
- Modify: `.gitignore`
- Create: `.env.example`
- Remove from index: `.env` (файл на диске сохраняется)

- [ ] **Step 1: Добавить `.env` в `.gitignore`**

Изменение `.gitignore`:

```text
__pycache__/
*.py[cod]
yaride.db
.pytest_cache/
.env
```

- [ ] **Step 2: Создать `.env.example`**

Создать файл `.env.example` с содержимым:

```text
BOT_TOKEN=
DB_PATH=yaride.db

# Опциональные UX-константы (см. app/config.py). Значения по умолчанию устраивают.
# SEATS_CHOICES=2,3,4
# PRICE_CHOICES=100,150,200
# TIME_STEP_MINUTES=30
# WORK_HOURS_START=6
# WORK_HOURS_END=23
# GEO_SUGGEST_LIMIT=5
# GEO_SUGGEST_MAX_KM=85.0
# LOCALITY_GEO_MAX_KM=150.0
# RATING_PROMPT_INITIAL_DELAY_S=45
# RATING_PROMPT_INTERVAL_S=180
```

- [ ] **Step 3: Снять `.env` из git index**

```bash
git rm --cached .env
```

Expected: `.env` помечен как deleted в git index, файл на диске остался.

- [ ] **Step 4: Проверка**

```bash
git status
```

Expected: видим `deleted: .env` (staged), `modified: .gitignore` (staged/unstaged), новый файл `.env.example` (untracked).

```bash
git check-ignore -v .env
```

Expected: вывод вида `.gitignore:5:.env	.env`.

- [ ] **Step 5: Коммит**

```bash
git add .gitignore .env.example
git commit -m "chore: вывести .env из репо, добавить .env.example"
```

> **Manual op (не часть плана, делается владельцем отдельно):** ротация токена в BotFather и очистка истории через `git filter-repo --invert-paths --path .env`. Документировано в Task 7.

---

## Task 2: Установка `ruff` и `pyproject.toml`

**Files:**
- Create: `pyproject.toml`
- Modify: `requirements.txt` (не трогаем — `ruff` не runtime-зависимость; ставится локально)

- [ ] **Step 1: Установить `ruff`**

```bash
py -3 -m pip install ruff
```

Expected: `Successfully installed ruff-*`.

- [ ] **Step 2: Зафиксировать версию**

```bash
py -3 -m ruff --version
```

Expected: вывод вида `ruff 0.x.x`. Записать конкретную версию для использования в `pyproject.toml`.

- [ ] **Step 3: Создать `pyproject.toml`**

```toml
[project]
name = "yaride"
version = "0.1.0"
description = "Yaride MVP: Telegram carpool bot for Yaroslavl"
requires-python = ">=3.11"

[tool.ruff]
line-length = 120
target-version = "py311"
extend-exclude = ["yaride.db"]

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP", "B"]
ignore = [
    "E501",   # long lines: line-length уже задан, но русские строки UI могут не помещаться
    "B008",   # function call in default argument: aiogram-стиль
]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["B011"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
docstring-code-format = false
```

- [ ] **Step 4: Прогнать lint и зафиксировать список ошибок**

```bash
py -3 -m ruff check . --no-fix
```

Expected: некоторое число ошибок (типично `F401`, `I001` — порядок импортов). Если ошибок ноль — пропустить Step 5.

- [ ] **Step 5: Автоисправление безопасных ошибок**

```bash
py -3 -m ruff check . --fix
py -3 -m ruff check . --no-fix
```

Expected после Fix: оставшиеся ошибки видны. Если есть оставшиеся ошибки — добавить нужные правила в `[tool.ruff.lint.per-file-ignores]` или починить руками.

- [ ] **Step 6: Прогнать форматтер**

```bash
py -3 -m ruff format .
py -3 -m ruff format --check .
```

Expected первая команда: вывод `N files reformatted`.
Expected вторая команда: `N files already formatted` (без ошибок).

- [ ] **Step 7: Прогнать тесты — убедиться, что автофиксы ничего не сломали**

```bash
py -3 -m unittest discover -s tests -v
```

Expected: `OK`, число тестов как в Task 0 Step 4.

- [ ] **Step 8: Коммит**

```bash
git add pyproject.toml
git add -u  # все ruff-fix модификации
git commit -m "chore: подключить ruff, прогнать lint и format по репо"
```

---

## Task 3: Таблица `schema_version` — failing test

**Files:**
- Create: `tests/test_db_schema_version.py`

- [ ] **Step 1: Написать первый failing test**

Создать `tests/test_db_schema_version.py`:

```python
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase

from app.db import SCHEMA_VERSION, Database


class SchemaVersionTests(TestCase):
    def test_fresh_db_records_current_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "fresh.db"
            db = Database(str(db_path))
            db.init_schema()

            with db.transaction() as conn:
                row = conn.execute(
                    "SELECT version FROM schema_version WHERE id = 1"
                ).fetchone()
            self.assertIsNotNone(row, "schema_version row must exist after init_schema")
            self.assertEqual(int(row["version"]), SCHEMA_VERSION)

    def test_init_schema_is_idempotent_for_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "twice.db"
            db = Database(str(db_path))
            db.init_schema()
            db.init_schema()

            with db.transaction() as conn:
                rows = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM schema_version"
                ).fetchall()
            self.assertEqual(int(rows[0]["cnt"]), 1)

    def test_existing_db_without_schema_version_gets_marked_at_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "legacy.db"
            raw = sqlite3.connect(str(db_path))
            raw.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, tg_user_id INTEGER, name TEXT, role TEXT)")
            raw.execute("CREATE TABLE trips (id INTEGER PRIMARY KEY)")
            raw.execute("CREATE TABLE route_points (id INTEGER PRIMARY KEY)")
            raw.commit()
            raw.close()

            db = Database(str(db_path))
            db.init_schema()

            with db.transaction() as conn:
                row = conn.execute(
                    "SELECT version FROM schema_version WHERE id = 1"
                ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(int(row["version"]), SCHEMA_VERSION)
```

- [ ] **Step 2: Подтвердить, что тесты падают**

```bash
py -3 -m unittest tests.test_db_schema_version -v
```

Expected: `ImportError: cannot import name 'SCHEMA_VERSION' from 'app.db'` либо аналогичная ошибка отсутствия атрибута.

---

## Task 4: Таблица `schema_version` — реализация

**Files:**
- Modify: `app/db.py`

- [ ] **Step 1: Добавить константу и метод в `app/db.py`**

В `app/db.py` после импортов, **до** `class Database`:

```python
SCHEMA_VERSION = 1
```

Внутри класса `Database`, новый метод (поместить после `_seed_route_points` или в любое логически удобное место — конец класса):

```python
def _ensure_schema_version(self, conn: sqlite3.Connection) -> None:
    """Создаёт таблицу schema_version и записывает текущую версию, если её ещё нет."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            version INTEGER NOT NULL
        )
        """
    )
    row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO schema_version(id, version) VALUES (1, ?)",
            (SCHEMA_VERSION,),
        )
```

В `init_schema` добавить вызов **в самом конце** транзакции, после `_fill_route_point_coordinates`:

```python
def init_schema(self) -> None:
    with self.transaction() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                ...
            ...
            """
        )
        self._migrate_schema(conn)
        self._migrate_users_dl_columns(conn)
        self._migrate_users_min_passenger_rating(conn)
        self._migrate_route_points_schema(conn)
        self._migrate_route_points_latlng(conn)
        self._migrate_favorites_and_ratings(conn)
        self._migrate_bot_chat_messages(conn)
        self._migrate_trip_ratings_review_text(conn)
        self._seed_route_points(conn)
        self._fill_route_point_coordinates(conn)
        self._ensure_schema_version(conn)  # NEW
```

(Существующая `init_schema` сохраняется как есть; добавляется только последняя строка.)

- [ ] **Step 2: Прогнать новые тесты**

```bash
py -3 -m unittest tests.test_db_schema_version -v
```

Expected: 3 теста проходят, `OK`.

- [ ] **Step 3: Прогнать весь тестовый набор — регрессий нет**

```bash
py -3 -m unittest discover -s tests -v
```

Expected: количество тестов в Task 0 Step 4 + 3 (новые), всё `OK`.

- [ ] **Step 4: Лёгкая проверка существующей `yaride.db`**

```bash
py -3 -c "from app.db import Database, SCHEMA_VERSION; db = Database('yaride.db'); db.init_schema(); import sqlite3; conn = sqlite3.connect('yaride.db'); conn.row_factory = sqlite3.Row; row = conn.execute('SELECT version FROM schema_version WHERE id=1').fetchone(); print('version =', row['version']); assert int(row['version']) == SCHEMA_VERSION"
```

Expected: `version = 1` без AssertionError.

- [ ] **Step 5: Прогон lint/format**

```bash
py -3 -m ruff check app/db.py tests/test_db_schema_version.py
py -3 -m ruff format --check app/db.py tests/test_db_schema_version.py
```

Expected: no errors.

- [ ] **Step 6: Коммит**

```bash
git add app/db.py tests/test_db_schema_version.py
git commit -m "feat(db): добавить таблицу schema_version с текущей версией 1"
```

---

## Task 5: `Settings` расширение — failing tests

**Files:**
- Create: `tests/test_config.py`

- [ ] **Step 1: Написать тесты**

Создать `tests/test_config.py`:

```python
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
            with self.assertRaises(RuntimeError):
                load_settings()
```

- [ ] **Step 2: Подтвердить падение**

```bash
py -3 -m unittest tests.test_config -v
```

Expected: ошибки `AttributeError: 'Settings' object has no attribute 'seats_choices'` или `ImportError`.

---

## Task 6: `Settings` расширение — реализация

**Files:**
- Modify: `app/config.py`

- [ ] **Step 1: Переписать `app/config.py`**

Заменить содержимое `app/config.py` на:

```python
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
```

- [ ] **Step 2: Проверить тесты**

```bash
py -3 -m unittest tests.test_config -v
```

Expected: 7 тестов проходят, `OK`.

- [ ] **Step 3: Полный тестовый прогон**

```bash
py -3 -m unittest discover -s tests -v
```

Expected: ранее зелёные тесты + 7 новых, всё `OK`.

- [ ] **Step 4: Lint + format**

```bash
py -3 -m ruff check app/config.py tests/test_config.py
py -3 -m ruff format --check app/config.py tests/test_config.py
```

Expected: no errors.

- [ ] **Step 5: Коммит**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat(config): UX-константы (seats, price, time, geo, rating intervals) в Settings"
```

---

## Task 7: Использование констант в `app/bot.py`, `app/ui.py`, `app/rating_worker.py`

**Files:**
- Modify: `app/bot.py`
- Modify: `app/ui.py`
- Modify: `app/rating_worker.py` (опционально — там константы зашиты сверху `run()`; см. ниже)
- Create: `tests/test_settings_wiring.py`

- [ ] **Step 1: Написать failing-тесты «UI читает из Settings»**

Создать `tests/test_settings_wiring.py`:

```python
from __future__ import annotations

from unittest import TestCase

from app.config import Settings
from app.ui import KeyboardFactory


def _make_settings(**overrides) -> Settings:
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
        kf = KeyboardFactory(
            settings=_make_settings(time_step_minutes=60, work_hours_start=8, work_hours_end=10)
        )
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
```

- [ ] **Step 2: Подтвердить падение**

```bash
py -3 -m unittest tests.test_settings_wiring -v
```

Expected: ошибки про неподдерживаемый параметр `settings=` в `KeyboardFactory`.

- [ ] **Step 3: Адаптировать `app/ui.py`**

Изменить `class KeyboardFactory` в `app/ui.py`:

```python
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import Settings


class KeyboardFactory:
    """Factory for all bot keyboards."""

    def __init__(self, *, settings: Settings | None = None, time_step_minutes: int | None = None) -> None:
        if settings is None:
            settings = Settings(bot_token="", db_path="")
        if time_step_minutes is not None:
            settings.time_step_minutes = time_step_minutes
        self._settings = settings
        self._time_choices = self._build_time_choices(
            settings.time_step_minutes, settings.work_hours_start, settings.work_hours_end
        )

    @staticmethod
    def _build_time_choices(step_minutes: int, hour_start: int, hour_end: int) -> list[str]:
        out: list[str] = []
        for hour in range(hour_start, hour_end):
            for minute in range(0, 60, step_minutes):
                out.append(f"{hour:02d}:{minute:02d}")
        return out

    # ... остальные методы как было ...

    def seats_keyboard(self, prefix: str = "create_seats") -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        for seats in self._settings.seats_choices:
            kb.button(text=str(seats), callback_data=f"{prefix}:{seats}")
        kb.adjust(len(self._settings.seats_choices) or 3)
        return kb.as_markup()

    def price_keyboard(self, prefix: str = "create_price") -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        for price in self._settings.price_choices:
            kb.button(text=f"{price} руб", callback_data=f"{prefix}:{price}")
        kb.adjust(len(self._settings.price_choices) or 3)
        return kb.as_markup()
```

Существующие `@staticmethod` у `seats_keyboard` / `price_keyboard` снимаются (становятся методами экземпляра).

> **Замечание:** Все handler'ы и rating_worker в текущем коде вызывают `KEYBOARDS.seats_keyboard()` и `_kb.seats_keyboard()` без аргументов или с `prefix=...`. Сигнатура сохраняется (prefix опционален), но теперь поведение зависит от `settings` инстанса. Это сознательное небольшое нарушение совместимости static-метода → instance-метода: ни один внешний вызывающий не зависел от static-семантики.

- [ ] **Step 4: Запустить тесты**

```bash
py -3 -m unittest tests.test_settings_wiring -v
```

Expected: 4 теста проходят, `OK`.

- [ ] **Step 5: Запустить полный тестовый набор — поймать регрессии**

```bash
py -3 -m unittest discover -s tests -v
```

Expected: всё `OK`. Если падает — проблема в местах, где `KeyboardFactory()` вызывался без аргументов; нужно убедиться, что новый дефолт (`Settings(bot_token="", db_path="")`) корректно даёт прежние списки (2,3,4 / 100,150,200 / 6-22 шаг 30). Тест `KeyboardFactoryBackwardCompatTests` это подтверждает.

- [ ] **Step 6: Использовать `settings` в `bot.py`**

В `app/bot.py` найти строки:

```python
LOCALITY_GEO_MAX_KM = 150.0
GEO_SUGGEST_LIMIT = 5
GEO_SUGGEST_MAX_KM = 85.0
```

Заменить на пустую строку (удалить эти константы из модуля).

В `_handle_start_locality_geo` (ищется по `repo.nearest_stops_global`) текущий вызов:

```python
ranked = repo.nearest_stops_global(
    lat,
    lng,
    limit=GEO_SUGGEST_LIMIT,
    max_km=GEO_SUGGEST_MAX_KM,
)
```

Заменить на:

```python
ranked = repo.nearest_stops_global(
    lat,
    lng,
    limit=_settings.geo_suggest_limit,
    max_km=_settings.geo_suggest_max_km,
)
```

И в той же функции `nearest_locality_from_geo(lat, lng, max_km=LOCALITY_GEO_MAX_KM)` → `nearest_locality_from_geo(lat, lng, max_km=_settings.locality_geo_max_km)`.

Чтобы `_settings` был доступен внутри handler'а, в начале `bot.py` (рядом с другими module-level переменными) добавить:

```python
_SETTINGS: Settings | None = None
```

И в `run()`, после `settings = load_settings()`:

```python
global _REPO_FOR_KB, _SETTINGS
_SETTINGS = settings
```

Создание `KEYBOARDS`:

Найти строку `KEYBOARDS = KeyboardFactory()` и заменить на:

```python
KEYBOARDS = KeyboardFactory()  # дефолтные значения; будет переинициализирован в run()
```

В `run()` после `_SETTINGS = settings`:

```python
global KEYBOARDS
KEYBOARDS = KeyboardFactory(settings=settings)
```

(Это временное решение в рамках Этапа 0; Этап 3 уберёт глобалы вместе с `KEYBOARDS`.)

Аналогично в `rating_worker.py`: `_kb = KeyboardFactory()` — оставить как есть (там используются только `rating_stars_keyboard`, не зависящий от settings).

Hardcoded `seats < 2 or seats > 4` в `bot.py`, `create_set_seats`:

Найти:

```python
if seats < 2 or seats > 4:
```

Заменить на:

```python
if seats not in _SETTINGS.seats_choices:
```

И `price not in (100, 150, 200)` в `create_set_price`:

Найти:

```python
if price not in (100, 150, 200):
```

Заменить на:

```python
if price not in _SETTINGS.price_choices:
```

В тех же местах, где формируется сообщение об ошибке (например, `"Допустимо только 2-4 пассажира."`), привести текст к динамическому:

```python
allowed_seats = ", ".join(str(s) for s in _SETTINGS.seats_choices)
await edit_or_send_clean(
    callback,
    f"Допустимо только: {allowed_seats}.",
    reply_markup=add_back_button(seats_keyboard(), "create_time"),
)
```

Аналогично для price:

```python
allowed_prices = ", ".join(str(p) for p in _SETTINGS.price_choices)
await edit_or_send_clean(
    callback,
    f"Доступные цены: {allowed_prices}.",
    reply_markup=add_back_button(price_keyboard(), "create_seats"),
)
```

Импорт в `bot.py` дополнить:

```python
from app.config import Settings, load_settings
```

(Если `Settings` не импортирован — добавить.)

`asyncio.sleep(45)` в `rating_prompt_loop` (см. `bot.py:1699`):

```python
async def rating_prompt_loop() -> None:
    await asyncio.sleep(_SETTINGS.rating_prompt_initial_delay_s)
    while True:
        try:
            await process_pending_rating_prompts(bot, repo)
        except Exception:
            logger.exception("rating_prompt_loop")
        await asyncio.sleep(_SETTINGS.rating_prompt_interval_s)
```

- [ ] **Step 7: Полный тестовый прогон**

```bash
py -3 -m unittest discover -s tests -v
```

Expected: всё `OK`. Если падают тесты — проверить, что `KEYBOARDS` в bot.py корректно переинициализируется в момент тестов (тесты не зовут `run()`, поэтому модульный `KEYBOARDS = KeyboardFactory()` остаётся дефолтным; тесты против handler'ов в этом этапе не пишем).

- [ ] **Step 8: Lint + format**

```bash
py -3 -m ruff check app/ tests/
py -3 -m ruff format --check app/ tests/
```

Expected: no errors. Если есть — пофиксить.

- [ ] **Step 9: Коммит**

```bash
git add app/ui.py app/bot.py tests/test_settings_wiring.py
git commit -m "feat(config): подключить Settings к KeyboardFactory, bot.py geo/seats/price/timing"
```

---

## Task 8: Формат логов

**Files:**
- Modify: `app/bot.py`

- [ ] **Step 1: Расширить формат `basicConfig`**

В `app/bot.py`, функция `run()`, заменить:

```python
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
```

на:

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s [%(filename)s:%(lineno)d] %(message)s",
)
```

- [ ] **Step 2: Прогнать тесты**

```bash
py -3 -m unittest discover -s tests -v
```

Expected: `OK`.

- [ ] **Step 3: Lint + format**

```bash
py -3 -m ruff check app/bot.py
py -3 -m ruff format --check app/bot.py
```

Expected: no errors.

- [ ] **Step 4: Коммит**

```bash
git add app/bot.py
git commit -m "chore(log): добавить filename:lineno в формат логов"
```

---

## Task 9: Обновление `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Обновить инструкцию по запуску**

В `README.md` в разделе «Быстрый старт» заменить:

```text
2. Создать `.env` на основе `.env.example`:
   - `BOT_TOKEN=...`
   - `DB_PATH=yaride.db`
```

на:

```text
2. Создать `.env` на основе `.env.example` (см. файл в репозитории):
   - `cp .env.example .env`
   - Открыть `.env`, вписать `BOT_TOKEN=<токен от BotFather>`.
   - При желании — переопределить UX-константы (см. `app/config.py`).
```

В конце README добавить новый раздел:

```markdown
## Разработка

### Lint и format

Перед коммитом:

```bash
py -3 -m ruff check .
py -3 -m ruff format --check .
```

Авто-исправления:

```bash
py -3 -m ruff check . --fix
py -3 -m ruff format .
```

### Запуск тестов

```bash
py -3 -m unittest discover -s tests -v
```

### Версия схемы БД

Текущая версия — в `app.db.SCHEMA_VERSION`. Таблица `schema_version` в `yaride.db` хранит фактически применённую версию. Линейные миграции по версиям подключаются в Этапе 1 (см. `docs/superpowers/specs/2026-05-11-etap-1-data-resilience.md`).
```

- [ ] **Step 2: Коммит**

```bash
git add README.md
git commit -m "docs(readme): обновить раздел запуска, добавить раздел разработки (ruff, тесты)"
```

---

## Task 10: Обновление `AGENTS.md`

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Заменить блок про `.env`**

В `AGENTS.md`, раздел «Key caveats», заменить пункт:

```text
- The `.env` file is committed to the repo with a bot token. Treat it as a development convenience; do not rotate or remove it.
```

на:

```text
- The `.env` file is **not** committed (since 2026-05-11). Use `.env.example` as a template:
  - `cp .env.example .env`
  - Set `BOT_TOKEN=<token from BotFather>`.
  - Rotate the token at BotFather if it ever leaks; treat any leaked token as compromised.
```

Добавить новый пункт в тот же раздел:

```text
- **Linting:** project uses `ruff` (>=0.x.x).
  - `py -3 -m ruff check .` and `py -3 -m ruff format --check .` must pass before committing.
  - Configuration lives in `pyproject.toml`.
- **Schema version:** SQLite has a `schema_version(id, version)` table. `app.db.SCHEMA_VERSION` is the current code version. Linear migrations by version are introduced in Этап 1 (see `docs/superpowers/specs/2026-05-11-etap-1-data-resilience.md`).
```

- [ ] **Step 2: Коммит**

```bash
git add AGENTS.md
git commit -m "docs(agents): обновить политику .env, добавить ruff и schema_version"
```

---

## Task 11: Документация ручных операций по токену

**Files:**
- Create: `docs/operations/2026-05-11-rotate-bot-token-and-clean-history.md`

- [ ] **Step 1: Написать инструкцию**

Создать `docs/operations/2026-05-11-rotate-bot-token-and-clean-history.md`:

```markdown
# Ротация BOT_TOKEN и очистка git-истории от утечки

**Контекст:** до 2026-05-11 `.env` был закоммичен в репо вместе с активным `BOT_TOKEN`. Этап 0 (`docs/superpowers/plans/2026-05-11-etap-0-...md`) автоматизировал вынос `.env` из tracked; этот документ — ручные шаги владельца, которые автоматизировать нельзя или опасно автоматизировать.

## Шаг 1. Ротация токена в BotFather

1. Открыть `@BotFather` в Telegram.
2. `/mybots` → выбрать бота.
3. `API Token` → `Revoke current token`.
4. Скопировать новый токен.
5. Локально записать в `.env`:
   ```text
   BOT_TOKEN=<новый токен>
   DB_PATH=yaride.db
   ```

## Шаг 2. Подтвердить, что новый токен работает

```bash
py -3 main.py
```

Ожидание: бот стартует без `TelegramConflictError` и без `Unauthorized`. Прервать `Ctrl+C` после старта.

## Шаг 3. Очистить старый токен из истории git

Установить `git-filter-repo` (по необходимости):

```bash
py -3 -m pip install git-filter-repo
```

Из чистого working tree (нет незакоммиченных изменений):

```bash
git filter-repo --invert-paths --path .env
```

Проверка:

```bash
git log --all -- .env
```

Ожидание: пустой вывод.

## Шаг 4. Force-push (опасный шаг)

> Force-push переписывает remote. Если у проекта есть другие участники — согласовать с ними.

```bash
git push origin main --force
```

## Шаг 5. Известить участников

Сделать рассылку: «История репозитория переписана; перед продолжением сделать `git fetch && git reset --hard origin/main` (потеряются локальные коммиты не из remote)».

## Чек-лист завершения

- [ ] Старый токен у BotFather отозван.
- [ ] Новый токен в локальном `.env`, файл не tracked в git.
- [ ] `git log --all -- .env` пуст.
- [ ] `git push --force` выполнен.
- [ ] Уведомление участникам отправлено.
```

- [ ] **Step 2: Коммит**

```bash
mkdir -p docs/operations
git add docs/operations/2026-05-11-rotate-bot-token-and-clean-history.md
git commit -m "docs(ops): инструкция по ротации токена и очистке истории"
```

---

## Task 12: Финальная проверка и merge

**Files:** ничего не меняется в коде.

- [ ] **Step 1: Прогнать lint, format, тесты целиком**

```bash
py -3 -m ruff check .
py -3 -m ruff format --check .
py -3 -m unittest discover -s tests -v
```

Expected: всё зелёное.

- [ ] **Step 2: Smoke-test: запустить бота на короткое время**

```bash
py -3 main.py
```

Ожидание: лог `INFO ...` с `filename:lineno`, бот стартует без ошибок. Прервать `Ctrl+C` через 5-10 секунд. Не страшно, если последний `INFO` ругается на `TelegramConflictError` (если другой инстанс уже работает) — это ожидаемо по AGENTS.md.

- [ ] **Step 3: Проверка структуры**

```bash
git ls-files .env
```

Expected: пусто.

```bash
Test-Path .env.example
Test-Path pyproject.toml
Test-Path docs/operations/2026-05-11-rotate-bot-token-and-clean-history.md
```

Expected: все три `True`.

```bash
py -3 -c "from app.config import load_settings; print(load_settings())"
```

Expected: `Settings(bot_token='...', db_path='yaride.db', seats_choices=(2, 3, 4), ...)`.

- [ ] **Step 4: Coverage check (sanity)**

```bash
py -3 -m unittest discover -s tests 2>&1 | Select-String "Ran"
```

Expected: число тестов вырастает с baseline на 14 (3 в Task 3, 7 в Task 5, 4 в Task 7).

- [ ] **Step 5: Merge в main (на усмотрение владельца)**

```bash
git checkout main
git merge etap-0-hygiene
```

Либо открыть PR — на усмотрение владельца. План этапа на этом завершён.

- [ ] **Step 6: Ручные операции из Task 11**

После merge выполнить ротацию токена и очистку истории по `docs/operations/2026-05-11-rotate-bot-token-and-clean-history.md`.

---

## Self-review

### Spec coverage

| Spec requirement | Task |
|------------------|------|
| Ротация токена + `.env.example` + `.gitignore` + AGENTS.md | 1, 10, 11 |
| `ruff` lint+format | 2 |
| `schema_version` таблица | 3, 4 |
| UX-константы в `app/config.py` | 5, 6, 7 |
| Формат логов | 8 |
| Обновление README | 9 |
| Документация ручных операций | 11 |

### Placeholder scan

- Все блоки кода полные (full implementation в каждом step).
- Команды конкретны (`py -3 ...`).
- Expected output указан для каждой проверки.

### Type consistency

- `Settings` — `dataclass(slots=True)` с явными типами.
- `KeyboardFactory(*, settings=None, time_step_minutes=None)` — единая сигнатура; используется одинаково во всех тестах и в `bot.py`.
- `SCHEMA_VERSION: int = 1` — единственная константа версии, используется и в коде, и в тестах через импорт.
