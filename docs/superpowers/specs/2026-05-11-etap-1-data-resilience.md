# Этап 1 — Данные и устойчивость

**Зависимости:** Этап 0 (`schema_version` уже существует, UX-константы в `app/config.py`, линтер настроен).
**Roadmap:** см. `2026-05-11-audit-and-roadmap.md`, раздел 3.
**Покрывает находки:** H2 (гонка при бронировании), H3 (миграции на каждой транзакции), M9 (линейный список миграций), L13 (correlation id для критичных путей), L16 (graceful shutdown).

---

## 1. Цель

Привести проект к состоянию, в котором:

- параллельные брони одного места не могут оба пройти;
- миграции выполняются один раз на старте и линейно по версиям;
- запросы используют WAL и не открывают новое соединение на каждый чих;
- завершение бота не оставляет «висящих» бэкграунд-задач;
- критичные операции (бронирование, отмена, рейтинг) логируются с привязкой к `tg_user_id` / `trip_id`.

## 2. Скоуп

### В скоупе

- **Атомарное бронирование.** `BookingRepository.create_booking` использует `BEGIN IMMEDIATE` и условный `UPDATE trips SET seats_booked = seats_booked + 1 WHERE id = ? AND status = 'open' AND seats_booked < seats_total`, проверяет `rowcount`.
- **Атомарная отмена брони.** То же для `cancel_booking_by_passenger` и `reject_booking_by_driver`: `UPDATE trips SET seats_booked = seats_booked - 1 WHERE id = ? AND seats_booked > 0` с проверкой `rowcount`, без полагания на `CASE WHEN`.
- **Атомарная отмена поездки.** `cancel_trip_by_driver`: одна транзакция вместо текущих 3 SQL без явной изоляции.
- **Подключение БД:** опциональный «one connection per request» паттерн заменяется на единое подключение с `check_same_thread=False`, плюс `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, `PRAGMA busy_timeout=5000`. Выбор между «pool / single connection» — деталь плана; принцип: новые `connect()` на каждый SELECT недопустимы.
- **Миграции один раз.** `Database.transaction()` больше не зовёт `_ensure_extended_schema`. На старте `Database.init_schema()` читает `schema_version`, запускает только нужные шаги.
- **Линейный список миграций.** Каждая миграция — функция `_migrate_v{n}_to_v{n+1}(conn)`. Запускаются по очереди от текущей версии БД до `CURRENT_SCHEMA_VERSION`. Каждая миграция в собственной транзакции с записью новой версии в `schema_version`.
- **Graceful shutdown.** В `run()` ссылки на `asyncio.create_task(...)` сохраняются; на `SIGINT/SIGTERM` они отменяются с ожиданием завершения текущей итерации.
- **Correlation id в логах.** Каждый критичный handler (`book_trip`, `cancel_booking_*`, `cancel_trip_*`, `submit_rating`) пишет лог с полями `tg_user_id`, `trip_id`/`booking_id`, `action`, `outcome`.

### Не в скоупе

- Изменение клавиатур, текстов, шагов FSM.
- Индексы и оптимизация запросов — Этап 2.
- Замена rating_worker'а на один SQL — Этап 2.
- Изменение `bot.py` помимо graceful shutdown — Этап 3.
- Полный structured logging (JSON, stdout/stderr separation) — отдельный отложенный backlog.

## 3. Поведение после этапа

- 100 параллельных попыток забронировать последнее место завершатся 1 успехом и 99 явными отказами «свободных мест нет» (юнит-тест с `ThreadPoolExecutor`).
- `trips.seats_booked` никогда не выходит за `[0, seats_total]` ни при одной комбинации параллельных операций.
- При старте бот делает один прогон миграций и больше до перезапуска их не повторяет.
- При `Ctrl+C` polling и `rating_prompt_loop` завершаются в пределах одного цикла без `Task was destroyed but it is pending!` варнингов.
- Запись `repo.create_booking` в логах содержит `tg_user_id=..., trip_id=..., outcome=success` либо `outcome=rejected reason=...`.

## 4. Архитектура изменений

### 4.1 Атомарное бронирование

Шаги в одной транзакции `BEGIN IMMEDIATE`:

1. `SELECT ... FROM trips WHERE id = ?` — проверки права/времени/драйвера.
2. `SELECT ... FROM users WHERE id = ?` — проверка пассажира и фильтра по рейтингу.
3. `INSERT ... INTO bookings ... ON CONFLICT (trip_id, passenger_id) DO UPDATE SET status='active', cancel_reason=NULL, ...` — обновление существующей записи или вставка.
4. `UPDATE trips SET seats_booked = seats_booked + 1 WHERE id = ? AND status='open' AND seats_booked < seats_total` — гарантирует, что место есть; если `rowcount == 0` — `raise ValueError("Свободных мест нет.")` и откат.
5. Возврат `booking_id`.

`ON CONFLICT` или fallback на «существующий ID → UPDATE» — конкретика для плана. Главное — приведение к **одному** UPDATE на trips с условием.

### 4.2 Атомарные отмены

```sql
UPDATE trips
SET seats_booked = seats_booked - 1
WHERE id = ?
  AND seats_booked > 0
```

Если `rowcount == 0`, логика откатывает изменение `bookings.status` и пишет в лог несоответствие (это сигнал об инварианте). Текущая ветвь `CASE WHEN seats_booked > 0 THEN -1 ELSE 0 END` снимается.

### 4.3 Линейный список миграций

`app/db.py` получает структуру:

```python
CURRENT_SCHEMA_VERSION = N  # фиксируется в плане; N не меньше 1.

MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _migrate_to_v2,  # пример: schema_version → users_dl_columns
    2: _migrate_to_v3,
    # ...
}
```

`Database.init_schema()`:

1. Создаёт `schema_version` если её нет.
2. Если БД пустая (`users` нет) — выполняет полный `CREATE TABLE` блок и ставит `schema_version=CURRENT_SCHEMA_VERSION`.
3. Иначе читает текущую версию и применяет шаги `i → i+1` до `CURRENT_SCHEMA_VERSION`, каждый — в `BEGIN IMMEDIATE`, в конце шага `UPDATE schema_version SET version = i+1`.
4. Все существующие `_migrate_*` методы маппятся на шаги `1 → 2`, `2 → 3` и т.д. План фиксирует точное соответствие.

`Database.transaction()` больше не зовёт миграции.

### 4.4 Подключение к БД

Решение по умолчанию: одно постоянное соединение с `check_same_thread=False`, защищённое единственным `asyncio.Lock` для записей (sqlite сам сериализует запись; lock служит для предсказуемости порядка). Альтернатива — connection pool на N=2-4 соединений с одним «писателем» и остальными «читателями» в WAL-режиме.

План выбирает между ними после быстрого замера: если разница в нагрузочном бенчмарке `<10%` — берём более простой single-connection.

### 4.5 WAL и PRAGMA

При первом `connect()`:

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;
```

WAL ставится один раз на БД (он сохраняется в файле). Тест: после `init_schema` повторное чтение `PRAGMA journal_mode` возвращает `wal`.

### 4.6 Graceful shutdown

`run()` хранит ссылки:

```python
background_tasks: set[asyncio.Task] = set()

def spawn(coro):
    task = asyncio.create_task(coro)
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return task

spawn(rating_prompt_loop())
spawn(push_main_menu_after_restart(bot, repo))

try:
    await dp.start_polling(bot)
finally:
    for task in background_tasks:
        task.cancel()
    await asyncio.gather(*background_tasks, return_exceptions=True)
    await bot.session.close()
```

`rating_prompt_loop` ловит `asyncio.CancelledError` и выходит без шума.

### 4.7 Correlation id в логах

В рамках одной операции — `logger.info("book_trip", extra={...})` с одинаковыми полями. Конкретный формат через `logging.LoggerAdapter` или `extra={}` — деталь плана.

Список handler'ов под обязательное логирование:

- `book_trip` (`bot.py:969`)
- `cancel_booking_reason` (`bot.py:1261`)
- `driver_reject_booking` (`bot.py:1429`)
- `driver_cancel_trip` (`bot.py:1460`)
- `complete_trip_rating_review` (`bot.py:1607`)

Для каждого: `action, tg_user_id, trip_id|booking_id, outcome, reason`.

## 5. Файлы

### Изменяются

- `app/db.py` — миграции, `schema_version`, WAL, single connection.
- `app/repo.py` — атомарные `create_booking`, `cancel_booking_by_passenger`, `reject_booking_by_driver`, `cancel_trip_by_driver`. Возможно появление утилит для критичной транзакции.
- `app/bot.py` — graceful shutdown, correlation id логи (минимум — `extra` на 5 указанных handler'ов).

### Не меняются

- Клавиатуры, FSM, тексты, фасад `Repo` (форма публичного API сохраняется; меняются только реализации соответствующих методов).

### Возможно появится

- `app/migrations.py` — отдельный модуль для линейного списка миграций (если `db.py` начнёт превышать ~500 строк).

## 6. Состояние БД

- Никаких новых таблиц.
- Существующие миграции не отменяются; они переписаны в виде шагов 1→2, 2→3, ... до `CURRENT_SCHEMA_VERSION`.
- Никаких `DROP COLUMN` — sqlite этого не любит, и оно нам не нужно.

## 7. Тестирование

### Юнит-тесты (новые)

- **Атомарность бронирования**: фейковый Connection, который симулирует «уже занято» через возврат `rowcount=0` на UPDATE — `create_booking` должен поднять `ValueError("Свободных мест нет.")` и не оставить запись в `bookings`.
- **Реальная гонка**: тест с настоящим sqlite (`tempfile`), N=20 параллельных `create_booking` через `ThreadPoolExecutor` на trip с seats_total=1 — ровно один успех.
- **Отмена бронирования**: проверка, что `seats_booked` уменьшается ровно на 1; повторная отмена той же брони не уменьшает.
- **Линейные миграции**: создание БД старой версии (V1), применение `init_schema`, проверка, что `schema_version` стало `CURRENT_SCHEMA_VERSION` и схема обновилась.
- **Идемпотентность init**: двукратный вызов `init_schema` не меняет состояние БД.

### Регрессия

- Все 32+ существующих теста зелёные.
- Ручная проверка в Telegram: бронирование/отмена/полное заполнение поездки.

## 8. Критерии приёмки

1. Параллельный тест 20×create_booking на trip с 1 местом завершается с ровно 1 успехом, 19 отказами; `seats_booked == 1`.
2. `seats_booked` не уходит ниже 0 и выше `seats_total` ни при одной серии параллельных операций.
3. `Database.transaction()` не вызывает миграций; ни одной записи в `sqlite_master` после первого старта не меняется при повторном открытии транзакции.
4. `PRAGMA journal_mode` возвращает `wal` после `init_schema`.
5. Бот останавливается на `Ctrl+C` без варнингов про незавершённые tasks.
6. В логах присутствуют записи `extra` с `tg_user_id`, `trip_id|booking_id`, `action`, `outcome` для 5 критичных handler'ов.
7. Все существующие и новые тесты зелёные.

## 9. Self-review

- **Placeholder scan:** нет TBD / TODO.
- **Согласованность:** атомарность реализуется через условный UPDATE с rowcount — единая стратегия для бронирования, отмены брони и отмены поездки.
- **Область:** только данные и устойчивость; никаких изменений UX/handler'ов кроме graceful shutdown и логов.
- **Однозначность:** выбор «single connection vs pool» — деталь плана с замерами, но критерий принятия зафиксирован (10%).
