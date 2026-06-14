# Деплой Yaride на Railway

Три сервиса в одном проекте Railway:

| Сервис | Root Directory | Публичный URL | Назначение |
|--------|----------------|---------------|------------|
| **yaride-core** | `/` (корень репо) | API | Бот + `webapp_api` |
| **yaride-miniapp** | `miniapp` | Mini App | Фронт Telegram Web App |
| **yaride-admin** (опц.) | `/` | Админка | Модерация |

**База данных:** PostgreSQL (плагин Railway). Один `DATABASE_URL` на **yaride-core** и **yaride-admin** — общие данные без синхронизации volume.

## Сеть (Railway Networking)

Yaride **не** подключает miniapp к Postgres напрямую. Схема:

```text
Telegram / браузер
    → yaride-miniapp (публичный домен)
    → yaride-core API (публичный домен, /api/*)
    → PostgreSQL (приватная сеть Railway, Variable Reference)

Админка:
    браузер → yaride-admin (публичный домен) → PostgreSQL (тот же DATABASE_URL)
```

| Кто | С кем говорит | Как |
|-----|---------------|-----|
| **miniapp** | **yaride-core** | `API_URL` = публичный URL core (`https://….up.railway.app`) |
| **yaride-core** | **Postgres** | `DATABASE_URL` = `${{ Postgres.DATABASE_URL }}` |
| **yaride-admin** | **Postgres** | `DATABASE_URL` = `${{ Postgres.DATABASE_URL }}` |
| **Postgres** | — | Публичный `DATABASE_PUBLIC_URL` только для миграции с локального ПК |

**Private networking** ([документация](https://docs.railway.com/networking)): сервисы в одном проекте ходят в БД по внутреннему хосту (`RAILWAY_PRIVATE_DOMAIN`). В Variable Reference это уже подставлено — **не** копируйте `DATABASE_PUBLIC_URL` в core/admin.

Проверка после деплоя:

```text
GET https://<core-domain>/health   → {"status":"ok","database":"postgresql"}
GET https://<admin-domain>/health  → {"status":"ok","database":"postgresql"}
```

Если `"database":"sqlite"` — сервис всё ещё пишет в файл на volume, не в Postgres.

## 1. Подготовка репозитория

Закоммитьте и запушьте изменения (Dockerfile, `railway.toml`, `scripts/start_prod.py`).

## 2. Проект Railway

1. [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo** → выберите `Yaride`.
2. Первый сервис переименуйте в `yaride-core`.

### PostgreSQL (обязательно в проде)

1. Проект → **Add Plugin** → **PostgreSQL** (сервис обычно называется **Postgres**).
2. На **yaride_core** и **yaride_admin** → Variables → **+ New Variable**:
   - имя: `DATABASE_URL`
   - значение: `${{ Postgres.DATABASE_URL }}`  
     (через UI: **Reference** → сервис Postgres → переменная `DATABASE_URL`)
3. **Volume для БД не нужен** — удалите `/data` volume у admin (и у core, если только для SQLite).

Код читает обычную переменную окружения `DATABASE_URL` (`app/database.py`); синтаксис `${{ … }}` — только в Railway Dashboard, не в Python.

Локально без Postgres: `DB_PATH=yaride.db` (SQLite по умолчанию).

### Миграция данных SQLite → Postgres (один раз)

```bash
py -3 scripts/migrate_sqlite_to_postgres.py --source yaride.db --target "<DATABASE_PUBLIC_URL>" --wipe
```

`DATABASE_PUBLIC_URL` — с локального ПК. На сервисах Railway — `${{ Postgres.DATABASE_URL }}`.

## 3. Переменные окружения

### yaride-core

| Переменная | Значение |
|------------|----------|
| `BOT_TOKEN` | токен от BotFather |
| `DATABASE_URL` | `${{ Postgres.DATABASE_URL }}` |
| `ADMIN_SESSION_SECRET` | случайная строка (32+ символов) |
| `WEBAPP_CORS_ORIGINS` | `https://<домен-miniapp>.up.railway.app` |
| `WEBAPP_DEV_USER_ID` | *(пусто в проде)* |
| `YARIDE_SKIP_ADMIN` | `1` *(если админка — отдельный сервис)* |
| `REDIS_URL` | *(опционально, этап 2 — кэш)* |

Railway сам задаёт `PORT` — API слушает его автоматически.

### yaride-miniapp

Root Directory: **`miniapp`**.

| Переменная | Значение |
|------------|----------|
| `API_URL` | `https://<домен-api>.up.railway.app` |
| `VITE_YANDEX_MAPS_KEY` | ключ JS API Яндекс.Карт |
| `NITRO_HOST` | `0.0.0.0` |

### yaride-admin

| Переменная | Значение |
|------------|----------|
| `YARIDE_SERVICE` | **`admin`** |
| `DATABASE_URL` | `${{ Postgres.DATABASE_URL }}` |
| `ADMIN_SESSION_SECRET` | тот же секрет |
| `BOT_TOKEN` | опционально |

Healthcheck: `/health`. Volume **не** нужен.

## 4. Публичные домены

1. **yaride-core** → Generate Domain (API).
2. **yaride-miniapp** → Generate Domain (Mini App).
3. **yaride-admin** → Generate Domain (админка).

## 5. BotFather

Mini App URL: `https://<miniapp-domain>/`. Один polling на токен.

## 6. Первый админ

```bash
railway link
railway run python -m admin.cli create-admin <логин>
```

## 7. Яндекс.Карты

Referer: домен miniapp + `web.telegram.org`.

## 8. Локальная разработка

```bash
py -3 scripts/dev.py
# SQLite: DB_PATH=yaride.db (по умолчанию)
# Postgres: DATABASE_URL=postgresql://...
```

## 9. CLI

```bash
railway login && railway link
railway up --service yaride_core -d
```

## Ограничения

- Один инстанс бота (не масштабировать core горизонтально).
- Redis (этап 2): `REDIS_URL` + `app/cache.py`.

## Legacy: SQLite volume

Устарело. См. `scripts/sync_db_railway.py` или миграцию в Postgres (раздел 2).
