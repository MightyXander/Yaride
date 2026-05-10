# Этап 3 — Архитектура: распил `bot.py` и упрощение `Repo`

**Зависимости:** Этап 0 (линтер, константы в config), Этап 1 (атомарные операции, миграции), Этап 2 (индексы).
**Roadmap:** см. `2026-05-11-audit-and-roadmap.md`, раздел 3.
**Покрывает находки:** H4 (глобальное состояние), M5 (размер `bot.py`), M6 (дублирование `NavigationFlow`), M7 (фасад `Repo`).

---

## 1. Цель

Привести проект к структуре, в которой:

- handler'ы разбиты по доменам и каждый файл помещается в окно внимания (≤400 строк);
- глобальных синглтонов в `bot.py` нет; всё собирается в `run()` и проходит через `Dispatcher`-зависимости (`dp["..."]`);
- `NavigationFlow` использует общий `FLOW_MODE_CFG` вместо параллельных `search_*` / `create_*` веток;
- `Repo` — тонкий контейнер ссылок на под-репозитории; handler'ы и сервисы ходят напрямую (`repo.bookings.create_booking(...)`).

## 2. Скоуп

### В скоупе

- Создание пакета `app/handlers/`:
  - `registration.py` — `/start`, выбор роли, ВУ.
  - `account.py` — раздел «Аккаунт» и upgrade в водителя.
  - `trip_search.py` — `/Найти поездки`, поиск-flow до выбора даты.
  - `trip_create.py` — `/Создать поездку`, флоу создания + время + места + цена.
  - `booking.py` — `book:*`, `cancel_booking:*`, «Мои брони».
  - `driver_manage.py` — «Управление», `manage_trip:*`, `reject_bk:*`, `cancel_trip:*`, threshold.
  - `rating.py` — `rate:*`, текстовый отзыв, оценки в аккаунте.
  - `geo.py` — обработчики геолокации и `gxs:*`.
  - `favorites.py` — `Избранные маршруты`, `fav_add:*`, `fav_route:*`.
  - `calendar.py` — `YarideCalendar`, обработчик `SimpleCalendarCallback`.
  - `fallback.py` — `/Назад`, `message()` fallback.
- Создание `app/bootstrap.py` — единая точка сборки зависимостей (`Repo`, `ChatUiService`, `KeyboardFactory`, `TripFlowOrchestrator`, `NavigationFlow`, фоновых задач).
- Превращение `app/bot.py` в **тонкий runner**: `parse args → bootstrap → register routers → start_polling → graceful shutdown`. Объём — не больше 200 строк.
- Все зависимости пробрасываются через `dp[...]` или фабричные функции; никаких `global`.
- Объединение веток `search_*` / `create_*` в `NavigationFlow` через общий `FLOW_MODE_CFG`.
- Сокращение фасада `Repo` до явных полей под-репозиториев. Handler'ы зовут `repo.users`, `repo.trips`, `repo.bookings` напрямую. Удаление прокси-методов **с одновременным апдейтом всех вызовов** (без обратной совместимости — это внутренний API).
- Тесты на ключевые handler'ы (как минимум `/start`, `book_trip`, `cancel_booking_reason`, `driver_cancel_trip`) — на уровне «handler принимает FakeMessage/FakeCallback с FakeRepo, ожидаемое состояние FSM и сообщения».

### Не в скоупе

- Изменение схемы БД.
- Изменение UI/UX/текстов.
- Перенос FSM на другой backend.
- Замена aiogram-роутера на свой.

## 3. Поведение после этапа

- `wc -l app/bot.py` показывает ≤200.
- В `app/handlers/*.py` ни один файл не превышает 400 строк.
- `python -m unittest discover` запускается из корня и проходит, включая новые тесты handler'ов.
- `git grep "global _" app/` пуст.
- В `NavigationFlow.handle_callback_back` нет дублирующихся блоков по 100 строк на каждое направление.
- В `Repo` нет 35 прокси-методов; есть `users`, `trips`, `bookings`, `routes`, `favorites`, `ratings` плюс утилиты `default_date`, `chunk_rows`.

## 4. Архитектура изменений

### 4.1 `app/bootstrap.py`

```python
@dataclass
class Container:
    settings: Settings
    db: Database
    repo: Repo
    keyboards: KeyboardFactory
    chat_ui: ChatUiService
    flow_orchestrator: TripFlowOrchestrator
    navigation_flow: NavigationFlow

def build_container() -> Container: ...
def attach_to_dispatcher(dp: Dispatcher, container: Container) -> None: ...
def start_background_tasks(bot: Bot, container: Container) -> set[asyncio.Task]: ...
```

`attach_to_dispatcher` регистрирует все routers и кладёт зависимости в `dp[...]`:

```python
dp["repo"] = container.repo
dp["chat_ui"] = container.chat_ui
dp["keyboards"] = container.keyboards
dp["flow"] = container.flow_orchestrator
dp["nav"] = container.navigation_flow
```

Handler'ы принимают `chat_ui: ChatUiService` и т.д. — aiogram сам разрулит DI.

### 4.2 Структура `app/handlers/`

Каждый файл экспортирует `router = Router()` и набор обработчиков. `app/bootstrap.py` импортирует и регистрирует:

```python
from app.handlers import (
    registration, account, trip_search, trip_create, booking,
    driver_manage, rating, geo, favorites, calendar as calendar_handlers,
    fallback,
)

routers = [
    registration.router, account.router, trip_search.router,
    trip_create.router, booking.router, driver_manage.router,
    rating.router, geo.router, favorites.router,
    calendar_handlers.router, fallback.router,
]
for r in routers:
    dp.include_router(r)
```

Порядок включения важен: `fallback.router` — последним.

### 4.3 `app/bot.py` после распила

```python
from __future__ import annotations
import asyncio
import logging
from aiogram import Bot, Dispatcher

from app.bootstrap import build_container, attach_to_dispatcher, start_background_tasks

logger = logging.getLogger(__name__)

async def run() -> None:
    logging.basicConfig(...)
    container = build_container()
    bot = Bot(token=container.settings.bot_token)
    dp = Dispatcher()
    attach_to_dispatcher(dp, container)

    await bot.delete_webhook(drop_pending_updates=True)
    tasks = start_background_tasks(bot, container)
    try:
        await dp.start_polling(bot)
    finally:
        for t in tasks: t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await bot.session.close()
```

### 4.4 Унификация `NavigationFlow`

Текущая `handle_callback_back` имеет 20+ блоков `elif target == "search_..."` / `"create_..."`. Каждая пара отличается только префиксом и заголовком — это map.

После рефакторинга `NavigationFlow` получает `FLOW_MODE_CFG` (тот же, что в `TripFlowOrchestrator`). Тело `handle_callback_back` сокращается до:

```python
async def handle_callback_back(self, callback, state, repo):
    target = callback.data.split(":", 1)[1]
    if target == "menu":
        ...
    if target == "switch_role_start":
        ...
    step = _parse_back_target(target)  # mode + step_name
    if step is None:
        await callback.answer("Нечего откатывать", show_alert=True); return
    cfg = self._flow_cfg[step.mode]
    handler = self._step_handlers[step.name]
    await handler(callback, state, repo, cfg)
    await callback.answer()
```

`_step_handlers` — словарь по именам шагов (`start_locality`, `start_district`, ...); каждый handler универсален для search/create через `cfg`. Общая длина уменьшается с 200 до ≤80 строк.

`handle_reply_back` приводится к той же схеме.

### 4.5 Упрощение `Repo`

После этапа:

```python
class Repo:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.routes = RouteRepository(db)
        self.trips = TripRepository(db)
        self.bookings = BookingRepository(db)
        self.favorites = FavoriteRouteRepository(db)
        self.ratings = RatingRepository(db)
```

Прокси-методы (`upsert_user`, `get_user`, ...) **удаляются**. Все вызовы из handler'ов переписываются на `repo.users.upsert_user(...)`, `repo.trips.find_open_trips(...)` и т.д.

Утилитные методы (`default_date`, `chunk_rows`) остаются в `Repo` или выносятся в `app/repo_helpers.py` — деталь плана.

### 4.6 `KeyboardFactory` и `ChatUiService` — без модульных синглтонов

- `bot.py` больше не создаёт `KEYBOARDS`, `CHAT_UI`, `_REPO_FOR_KB`.
- Эти объекты создаются в `build_container()` и пробрасываются через DI.
- `ChatUiService` принимает `Database` сразу в конструктор (или после `build_container`), не через `attach_database` после факта. `attach_database` снимается.

## 5. Файлы

### Новые

- `app/bootstrap.py`
- `app/handlers/__init__.py`
- `app/handlers/registration.py`
- `app/handlers/account.py`
- `app/handlers/trip_search.py`
- `app/handlers/trip_create.py`
- `app/handlers/booking.py`
- `app/handlers/driver_manage.py`
- `app/handlers/rating.py`
- `app/handlers/geo.py`
- `app/handlers/favorites.py`
- `app/handlers/calendar.py`
- `app/handlers/fallback.py`
- `app/handlers/_common.py` (опционально — общие helpers вроде `STALE_CREATE_FLOW`)
- `tests/test_handler_registration.py`, `tests/test_handler_booking.py` и т.п. (минимум 4 файла)

### Существенно меняются

- `app/bot.py` — превращается в тонкий runner.
- `app/repo.py` — удалены прокси-методы.
- `app/navigation_flow.py` — унификация через `FLOW_MODE_CFG`.
- `app/chat_ui.py` — `attach_database` уходит.

### Удаляются

- Глобалы из `bot.py` (`KEYBOARDS`, `CHAT_UI`, `_REPO_FOR_KB`, `FLOW_ORCHESTRATOR`, `NAVIGATION_FLOW` на module level — переезжают в `Container`).

## 6. Состояние БД

- Не меняется.

## 7. Тестирование

### Юнит-тесты handler'ов

Используется минимум 1 тест на handler с проверкой ожидаемой реакции:

- `registration.start`: новый пользователь видит вопрос про имя; известный — переход в `waiting_role`.
- `booking.book_trip`: успешный путь — `repo.bookings.create_booking` вызван, водителю отправлено уведомление; путь «не пассажир» — `callback.answer` с alert.
- `booking.cancel_booking_reason`: при коротком тексте — повторный запрос; при нормальном — отмена и уведомление водителю.
- `driver_manage.driver_cancel_trip`: отмена с рассылкой пассажирам.

Тесты используют ту же стратегию, что уже применена для `TripFlowOrchestrator` и `NavigationFlow`: фейковые State / Callback / Message / Repo.

### Регрессионные тесты

Существующие 32+ — должны остаться зелёными после рефакторинга без модификации (кроме изменений импортов в тестах, если переехали символы).

## 8. Критерии приёмки

1. `app/bot.py` ≤200 строк.
2. Ни один файл в `app/handlers/` не превышает 400 строк.
3. `git grep -n "^global " app/` — пусто.
4. `git grep -n "^[A-Z_]* = KeyboardFactory" app/bot.py` — пусто.
5. `NavigationFlow.handle_callback_back` и `handle_reply_back` суммарно ≤200 строк (сейчас ~450).
6. В `Repo` нет ни одного метода, который просто делегирует к `self.users.X(...)` / `self.trips.X(...)`. Handler'ы и сервисы зовут под-репо напрямую.
7. Все существующие тесты + минимум 4 новых файла тестов handler'ов — зелёные.
8. Ручная проверка в Telegram: пройти полный сценарий «регистрация → поиск → бронь → отмена → рейтинг» без регрессий.

## 9. Self-review

- **Placeholder scan:** нет TBD / TODO.
- **Согласованность:** структура `app/handlers/` соответствует доменной декомпозиции; `bootstrap.py` — единственная точка сборки.
- **Область:** только рефакторинг архитектуры; никаких изменений UX, FSM, схемы БД.
- **Однозначность:** выбор «где хранить `default_date`/`chunk_rows`» — деталь плана.
