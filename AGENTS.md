# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Yaride MVP is a Telegram carpool bot (aiogram 3.x) for Yaroslavl, Russia. It is a single Python service using SQLite for persistence. No Docker, no external databases, no microservices.

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
- **Schema version:** SQLite has a `schema_version(id, version)` table. `app.db.SCHEMA_VERSION` is the current code version. Linear migrations by version are introduced in Этап 1 (see `docs/superpowers/specs/2026-05-11-etap-1-data-resilience.md`).
- SQLite DB file (`yaride.db`) is created at first run and is gitignored implicitly (not tracked). Delete it to reset state.
