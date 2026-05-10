# Этап 4 — UX чата: уход от полного `cleanup_chat`

**Зависимости:** Этап 3 (handler'ы разбиты по доменам, `ChatUiService` без global, тесты handler'ов есть).
**Roadmap:** см. `2026-05-11-audit-and-roadmap.md`, раздел 3.
**Покрывает находки:** M10.

---

## 1. Цель

Сменить модель UI-управления чата с «удалить всё, нарисовать заново» на «один якорь-сообщение на flow, редактируем его».

Сейчас `ChatUiService.send_flow_step` и `send_clean_message` начинаются с `cleanup_chat`, который:

1. Шлёт «мост»-сообщение `\u2060` (чтобы Telegram не показал «Запустить бота»).
2. Удаляет до `history_limit=12` отслеживаемых сообщений бота.
3. Удаляет текущее пользовательское сообщение.
4. Удаляет «мост» в конце.

В худшем случае одна кнопка = 14 HTTP-вызовов к Telegram. Spec `2026-05-10-trip-search-geo-retry-design.md` уже боролся с симптомом (геолокация); новый подход решает корневую проблему для всех flow'ов.

## 2. Скоуп

### В скоупе

- В `ChatUiService` появляется концепция **anchor message** — id сообщения, которое держит текущий шаг flow. Все обновления внутри одного flow идут через `edit_message_text` этого anchor'а.
- При входе в новый flow (например, «Найти поездки») создаётся новый anchor; предыдущий (если был) — удаляется или превращается в подтверждение.
- Пользовательские сообщения (ответы текстом — имя, причина отмены, отзыв) удаляются по факту, по одному, **без полной чистки**.
- При смене flow или возврате в главное меню очищается только anchor + сопутствующие сообщения flow, а не вся история.
- Таблица `bot_chat_messages` сохраняется, но её роль меняется: она хранит «привязки flow → message_ids» по чату, чтобы пережить рестарт.

### Не в скоупе

- Изменение логики FSM (всех States).
- Изменение текстов сообщений.
- Reply-keyboard'ы остаются по существующей схеме (main / flow_with_back / location). Их рендеринг можно перерисовать только через `delete + send`, потому что aiogram/Telegram не поддерживают `edit_reply_markup` для reply-клавиатур; этот случай явно описан в плане.

## 3. Поведение после этапа

- Пользователь нажимает кнопку «Найти поездки» → бот **редактирует** существующее главное сообщение в «Откуда едем...». Старая клавиатура `main_keyboard` остаётся; reply-кнопки `«⬅ Назад»` появляются дополнительно одним сообщением, которое затем переиспользуется на всех шагах flow.
- При движении между шагами flow редактируется один и тот же anchor.
- Telegram не получает каскад `delete_message` на каждом нажатии — типично 1-2 вызова на переход.
- При завершении flow (выбор даты в поиске → список поездок) anchor превращается в результат; новые сообщения с inline-клавиатурой `book:*` отправляются отдельно.

## 4. Архитектура изменений

### 4.1 Anchor pattern в `ChatUiService`

```python
class ChatUiService:
    async def open_flow(self, chat_id, text, inline_markup) -> int:
        """Начать новый flow. Удаляет предыдущий anchor (если был), отправляет новый."""

    async def update_flow(self, chat_id, text, inline_markup) -> None:
        """Обновить anchor (edit_message_text). При ошибке — fallback на open_flow."""

    async def close_flow(self, chat_id, *, keep_message_id: int | None = None) -> None:
        """Завершить flow. Удалить anchor (или сохранить как итог)."""

    async def send_user_facing_message(self, message, text, *, reply_markup=None) -> Message:
        """Сообщение, которое НЕ относится к flow (main_menu, ошибки). Не трогает anchor."""
```

В БД: новая таблица или поле в `bot_chat_messages`:

```sql
CREATE TABLE IF NOT EXISTS chat_anchors (
    chat_id INTEGER PRIMARY KEY,
    anchor_message_id INTEGER NOT NULL,
    flow_kind TEXT NOT NULL,  -- 'search', 'create', 'manage', etc.
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

При старте handler'ов flow:

1. Прочитать `chat_anchors` по chat_id.
2. Если есть и `flow_kind` совпадает — edit.
3. Если есть и `flow_kind` другой — удалить старый anchor, создать новый.
4. Если нет — создать новый.

### 4.2 Пользовательские сообщения flow (ответы текстом)

`Registration.waiting_name` ожидает имя текстом. Сейчас бот отвечает `send_clean_message` (cleanup всей истории). Будет:

```python
@router.message(Registration.waiting_name)
async def reg_name(message, state, chat_ui):
    name = (message.text or "").strip()
    if len(name) < 2:
        await chat_ui.update_flow(message.chat.id, "Имя слишком короткое, попробуй ещё раз.")
        try: await message.delete()
        except: pass
        return
    await state.update_data(name=name)
    await state.set_state(Registration.waiting_role)
    await chat_ui.update_flow(message.chat.id, "Выбери роль:", role_keyboard())
    try: await message.delete()
    except: pass
```

Удаление пользовательского сообщения — точечный `message.delete()`, не каскад.

### 4.3 Reply-клавиатуры

Для перехода с inline-flow на состояние, требующее reply-клавиатуры (`«⬅ Назад»`, `«📍 Отправить местоположение»`), используется отдельное вспомогательное сообщение:

- При открытии flow с reply-keyboard: одно «сервисное» сообщение с reply-markup (например, `«Используй кнопки ниже:»`), которое отслеживается и удаляется при закрытии flow.
- При смене reply-keyboard внутри flow (с `flow_keyboard` на `location_reply_keyboard`) старое служебное сообщение удаляется, новое отправляется.
- Это компромисс из-за ограничений Telegram API.

### 4.4 Удаление `bot_chat_messages` массового удаления

`cleanup_chat` упрощается до:

```python
async def cleanup_chat_legacy(self, message): ...  # помечается deprecated и удаляется в конце этапа
```

Везде, где сейчас вызывается `cleanup_chat` — заменяется на `update_flow` / `close_flow` / точечный `message.delete()`.

### 4.5 «Мост» `\u2060`

При новом подходе нужда в мостовом сообщении почти отпадает (anchor всегда есть). Если флаг «после полного выхода из flow чат остался пустым» окажется встречным кейсом — отправляется одно главное меню reply-keyboard'ой, оно само поднимет интерфейс. План фиксирует точно: убрать `_EMPTY_CHAT_BRIDGE` или оставить как fallback в `close_flow`.

## 5. Файлы

### Изменяются

- `app/chat_ui.py` — новые методы, удаление массового cleanup.
- `app/handlers/*.py` — переход на `chat_ui.open_flow` / `update_flow` / `close_flow` вместо `send_flow_step` / `send_clean_message`.
- `app/db.py` или `app/migrations.py` — миграция на `chat_anchors`.

### Возможно сворачиваются

- `bot_chat_messages` — если не используется в результирующей модели, удаляется отдельным шагом миграции.

## 6. Состояние БД

- Новая таблица `chat_anchors` (см. 4.1).
- Возможное удаление `bot_chat_messages` — деталь плана.
- `schema_version` инкрементируется.

## 7. Тестирование

### Юнит-тесты

- `ChatUiService.open_flow`: при отсутствии anchor — `send_message`; при наличии и совпадении flow — `edit_message_text`; при несовпадении — `delete + send`.
- `ChatUiService.update_flow`: при `TelegramBadRequest` (сообщение не существует) — fallback на новый `send_message` + обновление anchor.
- `ChatUiService.close_flow`: anchor удаляется; при `keep_message_id` — сохраняется как итог.
- Регрессия handler'ов: ключевые сценарии (регистрация, поиск, бронирование) проходят с новыми вызовами.

### Ручная проверка в Telegram

- Открыть «Найти поездки», пройти 4 шага: количество сообщений в чате не растёт лавинообразно.
- Прервать flow «Назад» в середине: после возврата в меню в чате — одно главное меню.
- Открыть «Создать поездку», в середине открыть «Мои брони»: anchor flow_create удаляется, открывается новый.

## 8. Критерии приёмки

1. На прохождении полного flow «Найти поездки» (откуда → район → подрайон → остановка → куда → ... → дата) количество `bot.delete_message` ≤ 3 (для удаления пользовательских геосообщений).
2. Anchor flow редактируется через `edit_message_text`; команды `send_message` для UI шага не вызываются повторно.
3. При резком прерывании flow и старте нового anchor предыдущего корректно удаляется.
4. Все ранее существующие тесты + новые тесты `ChatUiService` — зелёные.
5. Регрессии в сценариях «регистрация», «поиск», «создание поездки», «бронь», «рейтинг» отсутствуют (ручная проверка).

## 9. Self-review

- **Placeholder scan:** нет TBD / TODO.
- **Согласованность:** Модель «anchor + edit» применяется ко всем flow одинаково.
- **Область:** только UI-слой и связанная таблица; FSM/handler'ы переписываются механически.
- **Однозначность:** reply-keyboard'ы — отдельный механизм через служебное сообщение (явно обозначено в 4.3).
