# Деплой Yaride на Railway

Три сервиса в одном проекте Railway:

| Сервис | Root Directory | Публичный URL | Назначение |
|--------|----------------|---------------|------------|
| **yaride-core** | `/` (корень репо) | API | Бот + `webapp_api` |
| **yaride-miniapp** | `miniapp` | Mini App | Фронт Telegram Web App |
| **yaride-admin** (опц.) | `/` | Админка | Модерация |

Общий **Volume** `yaride-data` смонтирован в `/data` у **yaride-core** и **yaride-admin**.

## 1. Подготовка репозитория

Закоммитьте и запушьте изменения (Dockerfile, `railway.toml`, `scripts/start_prod.py`).

## 2. Проект Railway

1. [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo** → выберите `Yaride`.
2. Первый сервис переименуйте в `yaride-core`.

### Volume (обязательно)

1. Сервис `yaride-core` → **Volumes** → **Add Volume**.
2. Mount path: `/data`
3. Тот же volume подключите к `yaride-admin` (если используете).

Без volume файл `yaride.db` **теряется при каждом редеплое**.

## 3. Переменные окружения

### yaride-core

| Переменная | Значение |
|------------|----------|
| `BOT_TOKEN` | токен от BotFather |
| `DB_PATH` | `/data/yaride.db` |
| `ADMIN_SESSION_SECRET` | случайная строка (32+ символов) |
| `WEBAPP_CORS_ORIGINS` | `https://<домен-miniapp>.up.railway.app` |
| `WEBAPP_DEV_USER_ID` | *(пусто в проде)* |
| `YARIDE_SKIP_ADMIN` | `1` *(если админка — отдельный сервис)* |

Railway сам задаёт `PORT` — API слушает его автоматически.

### yaride-miniapp

Root Directory в настройках сервиса: **`miniapp`**.

| Переменная | Значение |
|------------|----------|
| `VITE_API_URL` | `https://<домен-api>.up.railway.app` *(опц.)* |
| `API_URL` | `https://<домен-api>.up.railway.app` *(runtime, рекомендуется)* |
| `VITE_YANDEX_MAPS_KEY` | ключ JS API Яндекс.Карт |
| `NITRO_HOST` | `0.0.0.0` |

`API_URL` — **runtime**: miniapp проксирует `/api/*` на core без пересборки.
Если `VITE_API_URL` не задан при сборке, фронт ходит на относительный `/api` (через proxy).

### yaride-admin (опционально)

Тот же Dockerfile, root `/`, Start Command: `python -m admin`.

| Переменная | Значение |
|------------|----------|
| `BOT_TOKEN` | тот же токен |
| `DB_PATH` | `/data/yaride.db` |
| `ADMIN_SESSION_SECRET` | тот же секрет, что у core |
| Volume | `/data` (тот же volume) |

## 4. Публичные домены

1. **yaride-core** → Settings → Networking → **Generate Domain** → это URL API.
2. **yaride-miniapp** → Generate Domain → URL для BotFather и `WEBAPP_CORS_ORIGINS`.
3. **yaride-admin** → Generate Domain (если нужна модерация в браузере).

Порядок: сначала домен API → прописать `VITE_API_URL` и `WEBAPP_CORS_ORIGINS` → redeploy miniapp.

## 5. BotFather

1. `/setmenubutton` или Bot Settings → Mini App URL: `https://<miniapp-domain>/`
2. Убедитесь, что бот запущен **только на Railway** (один polling на токен).

## 6. Первый админ

После деплоя core (с volume):

```bash
railway link   # выбрать проект и yaride-core
railway run python -m admin.cli create-admin <логин>
```

Или через Railway Dashboard → сервис → **Shell**.

## 7. Яндекс.Карты

В кабинете разработчика Яндекса добавьте в HTTP Referer:

- домен miniapp (`*.up.railway.app` или точный хост)
- `web.telegram.org`

## 8. Локальная проверка Docker

```bash
# Backend
docker build -t yaride-core .
docker run --rm -p 8080:8080 -e BOT_TOKEN=... -e DB_PATH=/tmp/yaride.db yaride-core

# Mini App
cd miniapp
docker build -t yaride-miniapp --build-arg VITE_API_URL=http://127.0.0.1:8080 .
docker run --rm -p 3000:3000 -e PORT=3000 yaride-miniapp
```

## 9. CLI (альтернатива GitHub)

```bash
npm i -g @railway/cli
railway login
railway init
railway up
```

## Ограничения

- **Один инстанс бота** — не масштабируйте `yaride-core` горизонтально.
- SQLite + Volume: бэкапы — периодическое копирование `/data/yaride.db`.
- Postgres — отдельный этап, не блокер для первого деплоя.
