from __future__ import annotations

from collections.abc import Callable

from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, ReplyKeyboardMarkup

from app.db import Database

# Невидимый символ: пока удалена вся история, одно сообщение остаётся — иначе в клиенте Telegram
# (особенно на телефоне) показывается экран «Запустить бота» вместо диалога.
_EMPTY_CHAT_BRIDGE = "\u2060"


class ChatUiService:
    """Service responsible for clean chat rendering and message history."""

    def __init__(
        self,
        main_keyboard_provider: Callable[[int], ReplyKeyboardMarkup],
        flow_keyboard_provider: Callable[[], ReplyKeyboardMarkup],
        history_limit: int = 12,
    ) -> None:
        self._main_keyboard_provider = main_keyboard_provider
        self._flow_keyboard_provider = flow_keyboard_provider
        self._history_limit = history_limit
        self._chat_history: dict[int, list[int]] = {}
        self._db: Database | None = None

    def attach_database(self, database: Database) -> None:
        """После вызова id сообщений бота сохраняются в SQLite и переживают перезапуск процесса."""
        self._db = database
        self._chat_history.clear()

    def _prune_db_chat(self, conn, chat_id: int) -> None:
        rows = conn.execute(
            "SELECT id FROM bot_chat_messages WHERE chat_id = ? ORDER BY id DESC",
            (chat_id,),
        ).fetchall()
        if len(rows) <= self._history_limit:
            return
        for r in rows[self._history_limit :]:
            conn.execute("DELETE FROM bot_chat_messages WHERE id = ?", (int(r["id"]),))

    async def track_bot_message(self, message: Message) -> None:
        chat_id = message.chat.id
        mid = message.message_id
        if self._db:
            with self._db.transaction() as conn:
                conn.execute(
                    "INSERT INTO bot_chat_messages(chat_id, message_id) VALUES (?, ?)",
                    (chat_id, mid),
                )
                self._prune_db_chat(conn, chat_id)
        else:
            ids = self._chat_history.get(chat_id, [])
            ids.append(mid)
            self._chat_history[chat_id] = ids[-self._history_limit :]

    async def cleanup_chat(self, message: Message) -> int | None:
        bridge_id: int | None = None
        try:
            bridge = await message.answer(_EMPTY_CHAT_BRIDGE, disable_notification=True)
            bridge_id = bridge.message_id
        except Exception:
            bridge_id = None

        chat_id = message.chat.id
        ids: list[int] = []
        if self._db:
            with self._db.transaction() as conn:
                rows = conn.execute(
                    "SELECT message_id FROM bot_chat_messages WHERE chat_id = ? ORDER BY id",
                    (chat_id,),
                ).fetchall()
                ids = [int(r["message_id"]) for r in rows]
                conn.execute("DELETE FROM bot_chat_messages WHERE chat_id = ?", (chat_id,))
        else:
            ids = list(self._chat_history.get(chat_id, []))
            self._chat_history[chat_id] = []

        for message_id in ids:
            try:
                await message.bot.delete_message(chat_id, message_id)
            except Exception:
                continue

        try:
            await message.delete()
        except Exception:
            pass

        return bridge_id

    async def drop_empty_chat_bridge(self, message: Message | None, bridge_id: int | None) -> None:
        if message is None or bridge_id is None:
            return
        try:
            await message.bot.delete_message(message.chat.id, bridge_id)
        except Exception:
            pass

    async def send_clean_message(self, message: Message, text: str, **kwargs) -> Message:
        bridge_id = await self.cleanup_chat(message)
        if "reply_markup" not in kwargs:
            uid = message.from_user.id if message.from_user else 0
            kwargs["reply_markup"] = self._main_keyboard_provider(uid)
        sent = await message.answer(text, **kwargs)
        await self.track_bot_message(sent)
        await self.drop_empty_chat_bridge(message, bridge_id)
        return sent

    async def send_flow_step(self, message: Message, text: str, inline_markup: InlineKeyboardMarkup) -> None:
        bridge_id = await self.cleanup_chat(message)
        nav = await message.answer("Навигация: используйте «⬅ Назад».", reply_markup=self._flow_keyboard_provider())
        await self.track_bot_message(nav)
        step = await message.answer(text, reply_markup=inline_markup)
        await self.track_bot_message(step)
        await self.drop_empty_chat_bridge(message, bridge_id)

    async def edit_or_send_clean(self, callback: CallbackQuery, text: str, **kwargs) -> None:
        # Reply-клавиатура не поддерживается в editMessageText — только inline.
        rm = kwargs.get("reply_markup")
        if isinstance(rm, ReplyKeyboardMarkup):
            if callback.message:
                chat_id = callback.message.chat.id
                bridge_id = await self.cleanup_chat(callback.message)
                sent = await callback.bot.send_message(chat_id=chat_id, text=text, reply_markup=rm)
                await self.track_bot_message(sent)
                await self.drop_empty_chat_bridge(callback.message, bridge_id)
            return

        # Если явно не передали новую inline-разметку, сохраняем текущую,
        # чтобы кнопки не пропадали после валидационных ошибок.
        if "reply_markup" not in kwargs and callback.message and callback.message.reply_markup:
            kwargs["reply_markup"] = callback.message.reply_markup
        try:
            await callback.message.edit_text(text, **kwargs)
            await self.track_bot_message(callback.message)
        except Exception:
            bridge_id = await self.cleanup_chat(callback.message)
            if "reply_markup" not in kwargs:
                uid = callback.from_user.id if callback.from_user else 0
                kwargs["reply_markup"] = self._main_keyboard_provider(uid)
            sent = await callback.message.answer(text, **kwargs)
            await self.track_bot_message(sent)
            await self.drop_empty_chat_bridge(callback.message, bridge_id)
