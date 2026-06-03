# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Yaride MVP is a Telegram carpool bot (aiogram 3.x) for Yaroslavl, Russia. It is a single Python service using SQLite for persistence. No Docker, no external databases, no microservices.

**Layout:** `main.py` runs `app.bot.run`. Thin entry `app/bot.py` wires `build_container()`, `bot_support.configure()` (TripFlowOrchestrator + NavigationFlow + UI helpers), attaches routers from `app/handlers/*.py`, registers `BanMiddleware` (`app/middlewares.py`) as an outer update middleware, and starts polling. Shared Telegram helpers and `FLOW_MODE_CFG` live in `app/bot_support.py`. Domain handlers import lazily from `app.bot_support` to avoid cycles. Data access uses `Repo` as a thin holder of `users`, `routes`, `trips`, `bookings`, `favorites`, `ratings`, `admin` sub-repositories (no facade methods on `Repo`).

**Admin web UI (`admin/`):** separate local FastAPI app over the **same** `yaride.db`. Run with `py -3 -m admin` (create accounts via `py -3 -m admin.cli create-admin <login>`). All edits/deletes go through `app/services/admin_service.py` → `app/repo.py`, so domain invariants and cascades hold. Admin actions are written to `admin_audit_log`; trip cancellation and user ban notify users via the bot (Notifier, `admin/notifications.py`). `fastapi/uvicorn/jinja2/itsdangerous/passlib/python-multipart` are runtime deps for the admin UI; `httpx` is test-only (HTTP tests self-skip without it).

### Running the application

```bash
python3 main.py
# Windows (if `python3` is not on PATH):
py -3 main.py
```

The bot uses long-polling via aiogram. It requires a valid `BOT_TOKEN` in the `.env` file. On startup it auto-creates / migrates the SQLite database (`yaride.db` by default, controlled by `DB_PATH` in `.env`).

**Note:** If another instance of the bot is running with the same token, you will see `TelegramConflictError`. This is expected and does not indicate a code error — only one polling instance can be active per token.

### Running tests

```bash
python3 -m unittest discover -s tests -v
# Windows:
py -3 -m unittest discover -s tests -v
```

Tests are pure unit tests (no network, no database) using `unittest.IsolatedAsyncioTestCase`. They import from `app/` so run them from the repo root.

### Key caveats

- **Invoke Python:** on Linux/macOS use `python3`. On Windows, if `python3` is missing from PATH, use `py -3` (Python launcher).
- The `.env` file is **not** committed (since 2026-05-11). Use `.env.example` as a template:
  - `cp .env.example .env`
  - Set `BOT_TOKEN=<token from BotFather>`.
  - Rotate the token at BotFather if it ever leaks; treat any leaked token as compromised.
- **Linting:** project uses `ruff` (>=0.15.12).
  - `py -3 -m ruff check .` and `py -3 -m ruff format --check .` must pass before committing.
  - Configuration lives in `pyproject.toml`.
- **Schema version:** SQLite has a `schema_version(id, version)` table. `app.db.SCHEMA_VERSION` is the current code version. Linear migrations by version are introduced in Этап 1 (see `docs/superpowers/specs/2026-05-11-etap-1-data-resilience.md`). Этап 2 adds performance indexes (`app/db.py`, migration to v3); see README «Индексы и запросы». Этап 4 adds `chat_anchors` (v4) and reply-aux column + drops `bot_chat_messages` (v5). Админка adds `users.is_banned`, `admin_users`, `admin_audit_log` (v6).
- **Anchor-based chat UI (Этап 4, завершён):** на чат хранится один anchor — inline-сообщение текущего шага flow в таблице `chat_anchors(chat_id, anchor_message_id, flow_kind, reply_aux_message_id)`. Рядом с anchor может жить «service reply-aux» сообщение, несущее reply-клавиатуру. Все handler'ы используют единый API `ChatUiService.open_flow / update_flow / close_flow / send_post_flow_message / delete_user_message` (тонкие обёртки в `app.bot_support`). Legacy-функции `cleanup_chat`, `send_flow_step`, `send_clean_message`, `edit_or_send_clean`, `track_bot_message`, таблица `bot_chat_messages` и сообщение `\u2060`-bridge — удалены. `NavigationFlow` и `TripFlowOrchestrator` получают `chat_ui` через DI и оперируют anchor-сообщением через `update_flow` (никаких массовых `delete_message`).
- SQLite DB file (`yaride.db`) is created at first run and is gitignored implicitly (not tracked). Delete it to reset state.
