# Этап 2 — Производительность БД

**Зависимости:** Этап 1 (миграции линейные, схема версионируется, БД в WAL, бронирование атомарное).
**Roadmap:** см. `2026-05-11-audit-and-roadmap.md`, раздел 3.
**Покрывает находки:** M8 (индексы), L11 (rating_worker O(N·M)).

---

## 1. Цель

Привести запросы к виду, который не деградирует с ростом числа поездок и пользователей. Сейчас ничего не «горит», но фундамент закладывается под рост.

Конкретно:

- `find_open_trips` ходит по индексу, а не по полному сканированию `trips`.
- `list_passenger_bookings`, `list_bookings_for_driver_trip` ходят по индексу.
- `list_pending_rating_prompts` выполняется одним SQL вместо O(N·M) циклов.
- Все новые индексы покрыты регрессионными тестами и миграцией с записью в `schema_version`.

## 2. Скоуп

### В скоупе

- Новые индексы (см. раздел 4).
- Переписать `RatingRepository.list_pending_rating_prompts` одним запросом.
- Бенчмарк до/после на синтетических данных (1000 trips, 5000 bookings, 1000 ratings) — фиксируется в плане.
- Документировать в `README.md` или `AGENTS.md` раздел «Индексы и запросы», коротко: что есть, под что.

### Не в скоупе

- Замена SQLite на Postgres.
- Полнотекстовый поиск.
- Кеширование на уровне приложения.
- Изменение поведения handler'ов.

## 3. Поведение после этапа

- Бенчмарк на 1000 поездок: `find_open_trips(start, end, date)` отрабатывает за единицы миллисекунд (точный SLA — деталь плана; устанавливается после первого замера).
- `list_pending_rating_prompts` для 1000 trips × 5 пассажиров каждый делает не больше 1-3 SQL-запросов вместо ~20000.
- Все unit-тесты зелёные, плюс минимум 4 новых теста на корректность нового запроса для rating_prompts.

## 4. Архитектура изменений

### 4.1 Индексы

Новая миграция (шаг `N → N+1`):

```sql
CREATE INDEX IF NOT EXISTS idx_trips_status_date_route
    ON trips(status, trip_date, start_point_id, end_point_id);

CREATE INDEX IF NOT EXISTS idx_bookings_passenger_status
    ON bookings(passenger_id, status);

CREATE INDEX IF NOT EXISTS idx_bookings_trip_status
    ON bookings(trip_id, status);

CREATE INDEX IF NOT EXISTS idx_trip_ratings_rated
    ON trip_ratings(rated_user_id);

CREATE INDEX IF NOT EXISTS idx_trip_ratings_trip_rater_rated
    ON trip_ratings(trip_id, rater_user_id, rated_user_id);

CREATE INDEX IF NOT EXISTS idx_rating_prompts_trip_rater_rated
    ON rating_prompts_sent(trip_id, rater_user_id, rated_user_id);
```

После миграции — `EXPLAIN QUERY PLAN` на типовых запросах в тесте подтверждает использование индексов (строка с `USING INDEX`).

### 4.2 Один SQL для `list_pending_rating_prompts`

Идея: один `SELECT ... FROM trips JOIN bookings LEFT JOIN trip_ratings (на p→d) LEFT JOIN trip_ratings (на d→p) LEFT JOIN rating_prompts_sent (на p→d) LEFT JOIN rating_prompts_sent (на d→p)` с фильтрами:

- `trips.status != 'cancelled'`
- `bookings.status = 'active'`
- `trip_date + departure_time` уже на 3+ часа в прошлом (вычисление в SQL через `datetime(t.trip_date || ' ' || t.departure_time)` и сравнение с `datetime('now', '-3 hours')`).
- `trip_ratings IS NULL` И `rating_prompts_sent IS NULL`.

Результирующий набор: по две строки на каждую (driver, passenger) пару — одна для запроса оценки пассажира водителю, одна для водителя пассажиром. Каждая строка имеет ровно те же поля, что текущий `PendingRatingPrompt`.

Альтернатива (если запрос с двойным `LEFT JOIN` к `trip_ratings` окажется неудобным): два отдельных запроса (`p→d` и `d→p`) — по-прежнему O(1) вместо O(N·M). План выбирает между двумя вариантами по читаемости запроса (бенчмарк не повлияет на разницу заметно).

### 4.3 Бенчмарки

Тестовый скрипт (отдельный, не в `tests/`, а в `scripts/`):

- Создаёт временную БД.
- Засевает 1000 пользователей, 1000 trips (200 разных пар точек), 5000 bookings.
- Замеряет `find_open_trips`, `list_pending_rating_prompts` до и после индексов.

Скрипт остаётся в репо как ориентир для будущих этапов.

## 5. Файлы

### Изменяются

- `app/db.py` или `app/migrations.py` — новый шаг миграции на индексы.
- `app/repo.py` — `RatingRepository.list_pending_rating_prompts`.

### Возможно появится

- `scripts/benchmark_db.py` — синтетика и замеры.

### Не меняются

- Handler'ы, FSM, UI.

## 6. Состояние БД

- Шесть новых индексов (см. 4.1).
- `schema_version` инкрементируется на 1.

## 7. Тестирование

### Юнит-тесты

- **EXPLAIN QUERY PLAN**: после миграции для каждого нового индекса есть тест, который запускает соответствующий типовой запрос и проверяет, что план содержит `USING INDEX`.
- **`list_pending_rating_prompts`**: набор фейковых данных, в которых ожидается:
  - 0 prompt'ов для отменённой поездки.
  - 0 prompt'ов для поездки, прошедшей <3 ч назад.
  - 2 prompt'а (p→d и d→p) для поездки 4 ч назад, 1 пассажир, ни оценок, ни отправок.
  - 1 prompt (d→p) для поездки 4 ч назад, где пассажир уже оценил водителя, а водитель пассажира — нет.
  - 0 prompt'ов, если `rating_prompts_sent` уже содержит запись.
  - 1 prompt при двух пассажирах: один уже оценил/получил, другой — нет.

### Бенчмарк (не unit, отдельный скрипт)

- До/после на 1000 trips, 5000 bookings — числа фиксируются в `docs/superpowers/plans/etap-2-...` как baseline.

## 8. Критерии приёмки

1. Все индексы из 4.1 присутствуют в БД после `init_schema`.
2. `EXPLAIN QUERY PLAN` подтверждает использование каждого индекса в соответствующем тесте.
3. `list_pending_rating_prompts` выполняет ≤3 SQL-запросов на любом наборе данных (проверяется счётчиком на фейковом Connection).
4. Все ранее существующие тесты + минимум 6 новых тестов на rating_prompts — зелёные.
5. Бенчмарк-скрипт работает и записывает baseline в файл (например, `scripts/benchmark_baseline.txt`), на который можно ориентироваться в будущих этапах.

## 9. Self-review

- **Placeholder scan:** нет TBD / TODO.
- **Согласованность:** все индексы — по полям, упомянутым в существующих запросах; новых полей не добавляется.
- **Область:** только индексы и переписывание одного метода; UI/handler'ы не меняются.
- **Однозначность:** выбор «двойной LEFT JOIN vs два запроса» — деталь плана; критерий — читаемость.
