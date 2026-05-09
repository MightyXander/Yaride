# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Yaride MVP is a Telegram carpool bot (aiogram 3.x) for Yaroslavl, Russia. It is a single Python service using SQLite for persistence. No Docker, no external databases, no microservices.

### Running the application

```bash
python3 main.py
```

The bot uses long-polling via aiogram. It requires a valid `BOT_TOKEN` in the `.env` file. On startup it auto-creates / migrates the SQLite database (`yaride.db` by default, controlled by `DB_PATH` in `.env`).

**Note:** If another instance of the bot is running with the same token, you will see `TelegramConflictError`. This is expected and does not indicate a code error — only one polling instance can be active per token.

### Running tests

```bash
python3 -m unittest discover -s tests -v
```

Tests run from the repo root. Trip-flow tests use `unittest.IsolatedAsyncioTestCase` without Telegram; driver-license tests use a temporary SQLite file per case.

### Key caveats

- Use `python3` (not `python`) — the system does not have a `python` symlink.
- No linter is configured in the repo (no flake8, ruff, mypy, or pylint config files). Static checks can be done ad-hoc with `python3 -m py_compile <file>`.
- The `.env` file is committed to the repo with a bot token. Treat it as a development convenience; do not rotate or remove it.
- SQLite DB file (`yaride.db`) is created at first run and is gitignored implicitly (not tracked). Delete it to reset state.
- Driver identity uses table `driver_license_verifications` (self-declared license number + expiry); there is no integration with GIBDD or external verification APIs.
- Users already registered as passengers who want to become drivers should run `/driver_license` to enter license data before the in-bot role switch to driver can succeed.
