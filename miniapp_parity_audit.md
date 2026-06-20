# Mini App Parity Audit — Issue #33

**Дата:** 2026-06-20  
**Цель:** Подтвердить, что Mini App полностью покрывает интерактивные бот-сценарии перед вычисткой aiogram-хендлеров (#23.3).

---

## Статус тестов webapp_api

✅ **Зелёный** — 13/13 тестов PASSED (1.5s)

```
test_all_stops_have_coords                               PASSED
test_create_trip_then_search_finds_it                    PASSED
test_driver_pending_cannot_create_trip_until_approved    PASSED
test_favorites_add_list_delete                           PASSED
test_health                                              PASSED
test_history_and_dl_fields_in_me                         PASSED
test_me_unregistered_then_register_passenger             PASSED
test_nearby_stops_by_geo                                 PASSED
test_passenger_rating_threshold_persists                 PASSED
test_register_driver_with_car_and_districts              PASSED
test_search_district_fallback_finds_trip                 PASSED
test_search_empty                                        PASSED
test_template_create_list_publish_delete                 PASSED
```

---

## Gap-анализ по сценариям

### ✅ 1. Поиск поездки

| Слой | Файл | Функционал |
|------|------|------------|
| **Бот** | `app/handlers/trip_search.py` | Префиксы `Sfl:`, `Sfd:`, `Sfa:`, `Sfp:`, `Stl:`, `Std:`, `Sta:`, `Stp:` — выбор районов/остановок отправления/назначения через inline-кнопки + геолокация |
| **Mini App** | `miniapp/src/routes/search.tsx` | Пошаговый wizard: `from-district` → `from-stop` → `from-geo` → `to-district` → `to-stop` → `date` → `results` (exact/district). Интеграция с картой через `route.map.tsx` |
| **API** | `webapp_api/routes/trips.py:search_trips` | GET `/api/trips?start_point=...&end_point=...&date=...` ИЛИ `start_district=...&end_district=...` — точный поиск + fallback на районы |

**Паритет:** ✅ **ПОЛНЫЙ**

- Mini App поддерживает выбор по district/stop/geo (компоненты `DistrictStep`, `StopStep`, `GeoStep`)
- Fallback на межрайонный поиск реализован (exact → district + `districtFallback`)
- Фильтры (время, свободные места) присутствуют (`SearchFilterSheet`)
- Тест `test_search_empty` + `test_search_district_fallback_finds_trip` покрывают API

---

### ✅ 2. Создание поездки водителем

| Слой | Файл | Функционал |
|------|------|------------|
| **Бот** | `app/handlers/trip_create.py` | Префиксы `Cfl:`, `Cfd:`, `Cfa:`, `Cfp:`, `Ctl:`, `Ctd:`, `Cta:`, `Ctp:` — выбор маршрута + `create_time:`, `create_seats:`, `create_price:` — параметры поездки |
| **Mini App** | `miniapp/src/routes/create.tsx` | Wizard: `start` (шаблон/новый) → `from` → `to` → `date` → `time` → `seats` → `price` → `comment`. Сохранение draft-состояния в localStorage. Поддержка шаблонов (templates API) |
| **API** | `webapp_api/routes/trips.py:create_trip` | POST `/api/trips` — проверки роли/ВУ + создание + enrichment промежуточных остановок |

**Паритет:** ✅ **ПОЛНЫЙ**

- Wizard в Mini App покрывает все шаги бота (маршрут, дата, время, места, цена, комментарий)
- Шаблоны (`POST /api/templates`, `POST /api/templates/{id}/publish`) реализованы, в боте их нет → **Mini App богаче**
- `CrownTimePicker` (UI для времени) — улучшенный UX vs inline-кнопки
- Тест `test_create_trip_then_search_finds_it` + `test_template_create_list_publish_delete` покрывают API
- Тест `test_driver_pending_cannot_create_trip_until_approved` проверяет модерацию

---

### ✅ 3. Бронирование и отмена брони

| Слой | Файл | Функционал |
|------|------|------------|
| **Бот** | `app/handlers/booking.py` | `book:` callback → создание брони + проверка роли/мест. `cancel_booking:` → FSM для ввода причины (min 3 символа) + уведомление водителю |
| **Mini App** | `miniapp/src/routes/bookings.tsx` | Список броней (GET `/api/bookings`). CancelScreen — textarea для причины + кнопка "Отменить бронь" |
| **API** | `webapp_api/routes/bookings.py` | POST `/api/bookings` (создание) + POST `/api/bookings/{id}/cancel` (отмена с причиной) + уведомление водителю через `BotNotifier` |

**Паритет:** ✅ **ПОЛНЫЙ**

- Mini App показывает список броней с фильтрацией по статусу (`active`, `cancelled_by_passenger`, `cancelled_by_driver`, `completed`)
- Отмена требует причину (min 3 символа) — аналогично боту
- Интеграция с `YandexRouteCard` для активных броней (маршрут в Яндекс.Навигатор) — **преимущество Mini App**
- Уведомления водителю работают через webapp_api → `BotNotifier`
- Нет прямого теста бронирования/отмены в `test_webapp_api.py` — **GAP в тестовом покрытии**, но сам функционал реализован

---

### ✅ 4. Управление поездками водителя

| Слой | Файл | Функционал |
|------|------|------------|
| **Бот** | `app/handlers/driver_manage.py` | Кнопка "Управление" → список открытых поездок + inline-кнопки `cancel_trip:`, `trip_bookings:`, `reject_booking:`, `set_threshold:` для порога рейтинга |
| **Mini App** | `miniapp/src/routes/manage.tsx` | Список поездок водителя (GET `/api/manage/trips`) + детали броней (`GET /api/manage/trips/{id}/bookings`) + отклонение брони + отмена поездки + настройка порога рейтинга (off / 3.0 / 4.0 / 4.5) |
| **API** | `webapp_api/routes/manage.py` | GET `/api/manage/trips`, GET `/api/manage/trips/{id}/bookings`, POST `/api/manage/trips/{id}/cancel`, POST `/api/manage/bookings/{id}/reject`, POST `/api/manage/passenger-rating-threshold` |

**Паритет:** ✅ **ПОЛНЫЙ**

- Mini App покрывает все операции бота (просмотр, отмена, отклонение, порог рейтинга)
- UI для порога рейтинга через `Chip` (визуально понятнее inline-кнопок)
- Интеграция с `YandexRouteCard` для поездок водителя
- Тест `test_passenger_rating_threshold_persists` покрывает API порога рейтинга

---

### ✅ 5. Регистрация, выбор роли, загрузка ВУ

| Слой | Файл | Функционал |
|------|------|------------|
| **Бот** | `app/handlers/registration.py` + `app/handlers/account.py` | `/start` → ввод имени → выбор роли (inline `set_role:`) → для водителя: серия/номер ВУ (FSM), срок действия, авто (модель/цвет/номер) |
| **Mini App** | `miniapp/src/routes/onboarding.tsx` + `miniapp/src/routes/account.tsx` + `miniapp/src/routes/license.tsx` | Stepper: `name` → `role` → (если driver) `license` (серия/номер/срок + авто). Валидация на фронте (`isLicenseSeriesValid`, `isLicenseExpiresValid`) |
| **API** | `webapp_api/routes/me.py` | GET `/api/me` (профиль), POST `/api/register` (регистрация/смена роли + данные ВУ для водителя) |

**Паритет:** ✅ **ПОЛНЫЙ**

- Mini App поддерживает полный онбординг (имя, роль, ВУ, авто)
- Валидация формата ВУ (`9916 АВ 123456`) и срока действия на фронте
- Тест `test_me_unregistered_then_register_passenger` + `test_register_driver_with_car_and_districts` + `test_history_and_dl_fields_in_me` покрывают API
- В боте нет UI для редактирования авто после регистрации — в Mini App есть (`account.tsx`, `license.tsx`) → **Mini App богаче**

---

### ✅ 6. Рейтинг (выставление оценок)

| Слой | Файл | Функционал |
|------|------|------------|
| **Бот** | `app/handlers/rating.py` | Callback `rate:` → ForceReply для комментария → сохранение через `RatingService` |
| **Mini App** | `miniapp/src/routes/rate.$id.tsx` | Двухэтапный wizard: выбор звёзд (1-5) + теги (`["Пунктуально", "Чистая машина", ...]`) → комментарий → submit |
| **API** | `webapp_api/routes/ratings.py` | GET `/api/ratings/pending` (список поездок, ожидающих оценки), POST `/api/ratings` (выставление звёзд + review_text) |

**Паритет:** ✅ **ПОЛНЫЙ**

- Mini App покрывает выставление оценок (звёзды + комментарий)
- UI богаче: теги + двухэтапный flow vs inline-кнопки + ForceReply
- API `GET /api/ratings/pending` возвращает список поездок с открытым окном оценки (аналог бот-логики в `repo.ratings.list_pending_rating_prompts`)
- Уведомление получателю через `BotNotifier.rating_received`

---

### ✅ 7. Избранное (favorites)

| Слой | Файл | Функционал |
|------|------|------------|
| **Бот** | `app/handlers/favorites.py` | Кнопка "Избранные маршруты" → список + `fav_add:`, `fav_date:`, `fav_search:` — добавление, выбор даты, поиск |
| **Mini App** | `miniapp/src/routes/favorites.tsx` | Список избранных (GET `/api/favorites`) + переход к поиску с prefill-параметрами (`fromPointId`, `toPointId`) + удаление (`DELETE /api/favorites/{id}`) |
| **API** | `webapp_api/routes/favorites.py` | GET `/api/favorites`, POST `/api/favorites` (по `trip_id` или `start_point_id`/`end_point_id`), DELETE `/api/favorites/{id}` |

**Паритет:** ✅ **ПОЛНЫЙ**

- Mini App покрывает все операции: список, добавление, удаление
- Переход к поиску с prefill (URL params) — аналог `fav_search:` в боте
- Тест `test_favorites_add_list_delete` покрывает API

---

### ✅ 8. Гео-подбор остановок и выбор даты

| Слой | Файл | Функционал |
|------|------|------------|
| **Бот** | `app/handlers/geo.py` + `app/handlers/calendar.py` + `app/geo_suggestion.py` | Геолокация (Message.location) → поиск ближайших остановок → inline `gxs:` + aiogram_calendar для выбора даты |
| **Mini App** | `miniapp/src/routes/route.map.tsx` + компоненты `GeoStep`, `RouteDateStep` | Интерактивная карта (lazy `StopMapPicker`) для выбора точки + календарь (встроенный UI в `RouteDateStep`) |
| **API** | `webapp_api/routes/trips.py:nearest_stops` + `webapp_api/routes/catalog.py` | GET `/api/trips/nearby/by-geo?lat=...&lng=...` (5 ближайших остановок), GET `/api/catalog/districts`, GET `/api/catalog/stops?district=...`, GET `/api/catalog/stops/all` |

**Паритет:** ✅ **ПОЛНЫЙ**

- Mini App использует интерактивную карту (Leaflet/YMaps) для выбора точки — **UX богаче** бот-геолокации
- Календарь в Mini App — нативный UI vs aiogram_calendar (inline-кнопки)
- API `/api/trips/nearby/by-geo` покрывает бот-логику `repo.routes.nearest_stops_global`
- Тест `test_nearby_stops_by_geo` + `test_all_stops_have_coords` покрывают API

---

## Итоговый gap-list

| Сценарий | Бот | Mini App | webapp_api | Статус |
|----------|-----|----------|------------|--------|
| **Поиск поездки** | ✅ Полный | ✅ Полный + фильтры | ✅ Покрыто тестами | ✅ **Покрыт** |
| **Создание поездки** | ✅ Базовый | ✅ Полный + шаблоны | ✅ Покрыто тестами | ✅ **Покрыт** (Mini App богаче) |
| **Бронь/отмена** | ✅ Полный | ✅ Полный + статусы | ⚠️ API есть, нет прямого теста | ✅ **Покрыт** (нужен тест) |
| **Управление водителя** | ✅ Полный | ✅ Полный + порог рейтинга | ✅ Покрыто тестами | ✅ **Покрыт** |
| **Регистрация+роль+ВУ** | ✅ Базовый | ✅ Полный + редактирование | ✅ Покрыто тестами | ✅ **Покрыт** (Mini App богаче) |
| **Рейтинг** | ✅ Базовый | ✅ Полный + теги | ⚠️ API есть, нет прямого теста | ✅ **Покрыт** (нужен тест) |
| **Избранное** | ✅ Полный | ✅ Полный | ✅ Покрыто тестами | ✅ **Покрыт** |
| **Гео/даты** | ✅ Базовый | ✅ Карта + календарь | ✅ Покрыто тестами | ✅ **Покрыт** (Mini App богаче) |

---

## Рекомендации

### 1. Тестовое покрытие

**GAP:** Нет прямых интеграционных тестов для:
- Бронирования (POST `/api/bookings` + отмена)
- Рейтинга (POST `/api/ratings`)

**Рекомендация:** Добавить в `tests/test_webapp_api.py`:
```python
def test_booking_lifecycle(self):
    # Passenger books trip → active booking → cancel with reason → cancelled_by_passenger
    pass

def test_rating_submit_and_pending(self):
    # Complete trip → pending rating → submit stars + review → rating persists
    pass
```

### 2. Функциональные gap'ы

**Нет критичных gap'ов** — все интерактивные бот-сценарии покрыты Mini App. Более того:

- **Mini App богаче** в следующих аспектах:
  - Шаблоны поездок (POST `/api/templates`)
  - Редактирование профиля/авто/ВУ после регистрации
  - Интерактивная карта для выбора точек (vs геолокация кнопкой)
  - Теги для рейтинга
  - Фильтры поиска (время, места)
  - Интеграция с Яндекс.Навигатор (YandexRouteCard)

### 3. Готовность к вычистке aiogram-хендлеров

**Вердикт:** ✅ **Безопасно удалять интерактивные бот-хендлеры** (#23.3)

- Все сценарии покрыты Mini App
- `webapp_api` стабилен (13/13 тестов зелёные)
- Уведомления водителю/пассажиру сохраняются через `BotNotifier` (бот остаётся для push-уведомлений)

**План действий:**
1. ✅ Добавить тесты бронирования/рейтинга (Issue #34?)
2. ✅ Удалить aiogram-хендлеры: `trip_search.py`, `trip_create.py`, `booking.py`, `driver_manage.py`, `rating.py`, `favorites.py`, `geo.py`, `calendar.py` (#23.3)
3. ✅ Оставить: `/start` (регистрация fallback), `BotNotifier` (push-уведомления), `admin/` (бэк-офис)

---

## Источники

- **Бот:** `app/handlers/*.py`
- **Mini App:** `miniapp/src/routes/*.tsx`
- **API:** `webapp_api/routes/*.py`
- **Тесты:** `tests/test_webapp_api.py` (13 tests, 1.5s, ✅ PASSED)
- **Контекст:** `docs/council-2026-06-17.md` (решение council про Mini App = основной интерфейс)

---

**Автор:** Worker (claude-sonnet-4-5)  
**Версия:** 1.0.0 (финальная)
