# Этап 3 — Распил `bot.py` и упрощение `Repo`: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Довести архитектуру до контейнерной сборки без модульных синглтонов: `app/bootstrap.py`, пакет `app/handlers/`, тонкий `app/bot.py` (≤200 строк), унифицированный `NavigationFlow`, прямой доступ к под-репозиториям (`repo.users`, `repo.trips`, …), минимум четыре новых файла тестов handler'ов.

**Architecture:** Зависимости собираются один раз в `build_container()` и попадают в обработчики через `Dispatcher` + middleware (инъекция `repo`, `keyboards`, `chat_ui`, `flow`, `nav` в `data` для aiogram handler'ов). Роутеры из `app/handlers/*.py` подключаются в порядке домена; `fallback.router` — последним. `ChatUiService` получает `Database` в конструкторе; метод `attach_database` удаляется. Рефакторинг `NavigationFlow` строится на уже существующем `FLOW_MODE_CFG` из `TripFlowOrchestrator` / `bot.py` — один раз прочитать источник истины и сопоставить шаги search/create.

**Tech Stack:** Python 3.x, aiogram ≥3.7, SQLite stdlib, `unittest` (как в проекте), без новых внешних зависимостей.

**Spec reference:** `docs/superpowers/specs/2026-05-11-etap-3-architecture-refactor.md`.

**Baseline перед стартом:**

```bash
git checkout main
git pull
py -3 -m unittest discover -s tests -v
py -3 -m ruff check .
```

Expected: все тесты OK, ruff OK.

---

## Task 0: Ветка и инвентаризация

**Files:** только git и заметки в голове.

- [ ] **Step 1: Создать ветку**

```bash
git checkout -b etap-3-architecture-refactor
```

- [ ] **Step 2: Зафиксировать метрики «до»**

```bash
py -3 -c "print(open('app/bot.py',encoding='utf-8').read().count(chr(10))+1)"
wc -l app/bot.py app/navigation_flow.py app/repo.py 2>nul || py -3 -c "import pathlib; [print(sum(1 for _ in pathlib.Path(p).open(encoding='utf-8')), p) for p in ['app/bot.py','app/navigation_flow.py','app/repo.py']]"
git grep -n "^global " app/ || echo "no global"
```

Записать числа строк в коммит-сообщение первого значимого рефакторинга.

---

## Task 1: `ChatUiService` — база данных в конструкторе

**Files:**
- Modify: `app/chat_ui.py`
- Modify: `app/bot.py` (инициализация `CHAT_UI` и вызов `run`)
- Tests: при необходимости точечный тест; регрессия — полный `unittest`

**Идея:** Заменить `attach_database` на обязательный или опциональный аргумент `database: Database | None` в `__init__`. Удалить `attach_database` и поле «поздней привязки», если контракт станет «всегда с БД в проде».

- [ ] **Step 1: Изменить конструктор `ChatUiService`**

В `app/chat_ui.py` после правки сигнатура должна позволять:

```python
def __init__(
    self,
    main_keyboard_provider: Callable[[int], ReplyKeyboardMarkup],
    flow_keyboard_provider: Callable[[], ReplyKeyboardMarkup],
    *,
    database: Database | None = None,
    history_limit: int = 12,
) -> None:
    ...
    self._db = database
```

Удалить метод `attach_database`. Все места, где проверялось «есть ли db», оставить через `self._db`.

- [ ] **Step 2: Обновить создание `CHAT_UI` в `app/bot.py`**

На этапе перехода можно всё ещё создавать `Database` до `CHAT_UI`, затем передать `database=db` в конструктор. Убрать строку `CHAT_UI.attach_database(db)` в `run()`.

- [ ] **Step 3: Прогон тестов и коммит**

```bash
py -3 -m unittest discover -s tests -v
py -3 -m ruff check .
git add app/chat_ui.py app/bot.py
git commit -m "refactor(chat_ui): передача Database в конструктор, убран attach_database"
```

---

## Task 2: Контейнер и middleware инъекции

**Files:**
- Create: `app/bootstrap.py`
- Create: `app/middleware/deps.py` (или `app/bootstrap.py` — если хотите один файл до разрастания)
- Modify: `app/bot.py` — использовать контейнер вместо модульных `KEYBOARDS`, `CHAT_UI`, …

**Идея:** Dataclass `Container` по спеку; `build_container()` создаёт `Settings`, `Database`, `Repo`, фабрики клавиатур с замыканиями на `repo`/`settings`, `TripFlowOrchestrator`, `NavigationFlow`. Middleware добавляет в `data` ключи, совпадающие с именами параметров handler'ов.

Пример middleware (новый файл):

```python
from aiogram import BaseMiddleware

class ContainerMiddleware(BaseMiddleware):
    def __init__(self, container: Container) -> None:
        super().__init__()
        self._c = container

    async def __call__(self, handler, event, data):
        data["repo"] = self._c.repo
        data["keyboards"] = self._c.keyboards
        data["chat_ui"] = self._c.chat_ui
        data["flow"] = self._c.flow_orchestrator
        data["nav"] = self._c.navigation_flow
        data["settings"] = self._c.settings
        return await handler(event, data)
```

Подключить: `dp.update.middleware(ContainerMiddleware(container))` **до** регистрации роутеров или на уровне `dp` — проверить порядок по документации aiogram для вашей версии.

- [ ] **Step 1: Реализовать `Container` и `build_container()` без переноса handler'ов**

Пока `KeyboardFactory` и провайдеры для `ChatUiService` строятся так же, как сейчас в `bot.py`, но внутри функции фабрики.

- [ ] **Step 2: В `run()` заменить модульные синглтоны на `container = build_container()`**

Временно оставить определения handler'ов в `bot.py`, но заменить обращения `KEYBOARDS` → получение из замыкания нельзя без переноса функций; поэтому **минимальный шаг**: объявить `KEYBOARDS = container.keyboards` локально в `run()` и не использовать глобальные имена модулей — либо сразу перейти к Task 3 и импортировать router'ы с параметром через middleware.

Рекомендуемая последовательность: после контейнера **сразу** вынести один модуль `handlers/registration.py` и перевести его handler'ы на параметры `repo`, `keyboards` из middleware — тогда глобальные `KEYBOARDS` можно удалять по мере миграции.

- [ ] **Step 3: Тесты + коммит**

```bash
py -3 -m unittest discover -s tests -v
git add app/bootstrap.py app/middleware/deps.py app/bot.py
git commit -m "feat(bootstrap): Container и middleware зависимостей"
```

---

## Task 3: Пакет `app/handlers/` — первый модуль и паттерн

**Files:**
- Create: `app/handlers/__init__.py`
- Create: `app/handlers/registration.py` (или меньший файл для пробы — `fallback.py`)
- Modify: `app/bot.py` — удалить перенесённые декораторы, `include_router`

**Идея:** Каждый файл экспортирует `router = Router()`. Импортировать хендлеры для побочных эффектов регистрации: `from app.handlers import registration`.

Паттерн handler'а:

```python
@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    repo: Repo,
    keyboards: KeyboardFactory,
):
    ...
```

- [ ] **Step 1: Перенести `/start` и связанные состояния регистрации в `registration.py`**

Точные имена функций взять из текущего `bot.py` (поиск `@router.message(CommandStart())` и цепочки FSM).

- [ ] **Step 2: В `bootstrap.attach_to_dispatcher` или `bot.run` подключить `registration.router`**

- [ ] **Step 3: Новый тест `tests/test_handler_registration.py`**

Минимум сценарий из спеки: новый пользователь → ожидаемое следующее состояние / вызов `repo.users` или заглушки. Использовать стиль `tests/test_navigation_flow.py` / `tests/test_trip_flow.py` (фейковые объекты).

- [ ] **Step 4: unittest + commit**

```bash
py -3 -m unittest discover -s tests -v
git add app/handlers/ app/bot.py tests/test_handler_registration.py
git commit -m "refactor(handlers): вынесена регистрация в app/handlers/registration.py"
```

---

## Task 4: Остальные домены по одному файлу

Повторять тот же паттерн Task 3 для каждого файла из спеки (порядок рекомендуется по зависимостям и размеру):

| Файл | Содержимое (ориентир) |
|------|------------------------|
| `account.py` | Аккаунт, апгрейд в водителя |
| `trip_search.py` | Поиск до выбора даты |
| `trip_create.py` | Создание поездки |
| `booking.py` | Брони, отмена пассажиром |
| `driver_manage.py` | Управление поездкой водителя |
| `rating.py` | Оценки |
| `geo.py` | Геолокация, `gxs:*` |
| `favorites.py` | Избранное |
| `calendar.py` | Календарь |
| `fallback.py` | Назад, message fallback — **последним в include_router** |

После каждого крупного переноса:

```bash
py -3 -m unittest discover -s tests -v
git commit -m "refactor(handlers): <домен>"
```

Тесты из спеки (минимум ещё три файла):

- `tests/test_handler_booking.py` — `book_trip`, `cancel_booking_reason`
- `tests/test_handler_driver_manage.py` — `driver_cancel_trip`
- объединить или разнести по файлам — главное ≥4 новых файла тестов всего за этап

---

## Task 5: Тонкий `app/bot.py`

**Критерий:** ≤200 строк, без `@router` декораторов (все в `handlers/`).

- [ ] **Step 1: Удалить модульные `KEYBOARDS`, `CHAT_UI`, `FLOW_ORCHESTRATOR`, `NAVIGATION_FLOW`, `_REPO_FOR_KB`**

Проверка:

```bash
git grep -n "^global " app/
git grep -n "KEYBOARDS = KeyboardFactory" app/bot.py
```

Оба должны быть пустыми / без совпадений.

- [ ] **Step 2: `run()` только: logging, `build_container`, `Bot`, `Dispatcher`, `attach_to_dispatcher`, polling, shutdown из этапа 1**

- [ ] **Step 3: Коммит**

```bash
git commit -m "refactor(bot): тонкий runner, handlers только в app/handlers"
```

---

## Task 6: `NavigationFlow` — унификация `handle_callback_back` / `handle_reply_back`

**Files:**
- Modify: `app/navigation_flow.py`
- Possibly: `app/trip_flow.py` — экспорт единого `FLOW_MODE_CFG`, если сейчас дублируется

**Критерий из спеки:** суммарно `handle_callback_back` + `handle_reply_back` ≤200 строк; нет зеркальных блоков search/create на сотни строк.

- [ ] **Step 1: Извлечь парсинг `callback.data` → `(mode, step)`**

- [ ] **Step 2: Таблица шагов `_step_handlers: dict[str, Callable]`** с универсальными колбэками, принимающими `cfg` для режима.

- [ ] **Step 3: Прогон тестов** (`test_navigation_flow.py` расширить при изменении контракта)

```bash
py -3 -m unittest tests.test_navigation_flow -v
py -3 -m unittest discover -s tests -v
```

---

## Task 7: Удаление прокси методов `Repo`

**Files:**
- Modify: `app/repo.py` — класс `Repo` только поля + статические утилиты
- Modify: все вызовы в `app/handlers/*.py`, `app/trip_flow.py`, `app/navigation_flow.py`, `workers`, и т.д.

**Идея:** `grep -R "repo\\.upsert_user\\|repo\\.create_booking"` по `app/` и заменить на `repo.users.upsert_user`, `repo.bookings.create_booking`. Обратить внимание на алиасы `list_favorite_routes` → `repo.favorites.list_favorites`.

- [ ] **Step 1: grep по проекту**

```bash
git grep -n "repo\\.\\(upsert_user\\|get_user\\|create_trip\\|find_open_trips" app/
```

- [ ] **Step 2: Удалить методы-прокси из `Repo`, оставить:**

```python
class Repo:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.users = UserRepository(db)
        ...
    @staticmethod
    def default_date() -> str: ...
    @staticmethod
    def chunk_rows(...) -> ...: ...
```

Утилиты при желании перенести в `app/repo_helpers.py` одним коммитом.

- [ ] **Step 3: Полный прогон тестов**

---

## Task 8: Приёмка этапа

- [ ] **Step 1: Чеклист из спеки §8**

  - `wc -l app/bot.py` ≤ 200
  - каждый `app/handlers/*.py` ≤ 400 строк
  - `git grep "^global " app/` пусто
  - нет модульных фабрик клавиатур в `bot.py`
  - NavigationFlow строки — см. §6
  - нет прокси в `Repo`

- [ ] **Step 2: Документация**

Обновить `README.md` / `AGENTS.md` коротко: структура `app/handlers/`, `bootstrap.py`.

- [ ] **Step 3: Обновить трекинг в `docs/superpowers/specs/2026-05-11-audit-and-roadmap.md` раздел 10**

- [ ] **Step 4: Ручной smoke в Telegram** (спека §8 п.8)

---

## Заметки по рискам

1. **Циклические импорты:** `handlers` импортируют типы из `app.repo`; не импортировать `bot` из handlers.
2. **FSM группы:** при переносе сохранить те же `group_id` / имена состояний, иначе сломаются сохранённые состояния пользователей в памяти (для long polling обычно приемлемо перезапускать).
3. **KeyboardFactory и `_REPO_FOR_KB`:** после контейнера провайдеры должны замыкать `repo` из контейнера, не глобаль.
4. **Размер коммитов:** после каждого переносимого домена — зелёные тесты.
