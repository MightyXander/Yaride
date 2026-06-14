# Yaride Mini App (TanStack Start)

Telegram Mini App для карпулинга по Ярославлю.

## Стек

- TanStack Start + React 19 + Vite 7
- Tailwind CSS v4
- TanStack Query → `webapp_api` (FastAPI)

## Переменные окружения

Скопируйте `.env.example` в корень репозитория (для API) и `miniapp/.env` (для фронта):

```bash
cp .env.example .env
cp miniapp/.env.example miniapp/.env
```

| Переменная | Где | Описание |
|------------|-----|----------|
| `BOT_TOKEN` | корень `.env` | Токен бота (HMAC initData) |
| `WEBAPP_DEV_USER_ID` | корень `.env` | Dev-пользователь без Telegram |
| `VITE_API_URL` | `miniapp/.env` | База API (пусто = прокси Vite на :8080) |
| `VITE_YANDEX_MAPS_KEY` | `miniapp/.env` или корень `.env` | Ключ JS API Яндекс.Карт. Если не задан — подставляется `YANDEX_GEOCODER_KEY` из корневого `.env` |

## Запуск локально

**Одной командой** (из корня репозитория):

```bash
py -3 scripts/dev.py
```

Поднимает API `:8080`, админку `:8000`, фронт `:5174` и бота. Стабильный адрес фронта: `http://yaride.local:5174` (после `py -3 scripts/setup_hosts.py`).

**По отдельности:**

```bash
py -3 -m webapp_api    # :8080
py -3 -m admin         # :8000
cd miniapp && npm run dev   # :5174
py -3 main.py
```

Vite проксирует `/api` → `http://127.0.0.1:8080`.

**Браузер без Telegram:** `WEBAPP_DEV_USER_ID=900001` в корневом `.env`.

**Одобрение водителя (dev):** `http://127.0.0.1:8000` → пользователи → одобрить.

## Сборка

```bash
cd miniapp
npm run build
```

## Структура

- `src/routes/` — экраны (file-based routing)
- `src/lib/api.ts` — HTTP-клиент (`X-Init-Data`)
- `src/lib/queries.ts` — TanStack Query options
- `src/lib/store.tsx` — только UI-состояние (черновики)
