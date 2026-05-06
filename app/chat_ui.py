from __future__ import annotations

from typing import Callable

from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, ReplyKeyboardMarkup


class ChatUiService:
    """Service responsible for clean chat rendering and message history."""

    def __init__(
        self,
        main_keyboard_provider: Callable[[], ReplyKeyboardMarkup],
        flow_keyboard_provider: Callable[[], ReplyKeyboardMarkup],
        history_limit: int = 12,
    ) -> None:
        self._main_keyboard_provider = main_keyboard_provider
        self._flow_keyboard_provider = flow_keyboard_provider
        self._history_limit = history_limit
        self._chat_history: dict[int, list[int]] = {}

    async def track_bot_message(self, message: Message) -> None:
        chat_id = message.chat.id
        ids = self._chat_history.get(chat_id, [])
        ids.append(message.message_id)
        self._chat_history[chat_id] = ids[-self._history_limit :]

    async def cleanup_chat(self, message: Message) -> None:
        chat_id = message.chat.id
        ids = self._chat_history.get(chat_id, [])
        for message_id in ids:
            try:
                await message.bot.delete_message(chat_id, message_id)
            except Exception:
                continue

        self._chat_history[chat_id] = []
        try:
            await message.delete()
        except Exception:
            pass

    async def send_clean_message(self, message: Message, text: str, **kwargs) -> Message:
        await self.cleanup_chat(message)
        if "reply_markup" not in kwargs:
            kwargs["reply_markup"] = self._main_keyboard_provider()
        sent = await message.answer(text, **kwargs)
        await self.track_bot_message(sent)
        return sent

    async def send_flow_step(self, message: Message, text: str, inline_markup: InlineKeyboardMarkup) -> None:
        await self.cleanup_chat(message)
        nav = await message.answer("Навигация: используйте «⬅ Назад».", reply_markup=self._flow_keyboard_provider())
        await self.track_bot_message(nav)
        step = await message.answer(text, reply_markup=inline_markup)
        await self.track_bot_message(step)

    async def edit_or_send_clean(self, callback: CallbackQuery, text: str, **kwargs) -> None:
        # Если явно не передали новую inline-разметку, сохраняем текущую,
        # чтобы кнопки не пропадали после валидационных ошибок.
        if "reply_markup" not in kwargs and callback.message and callback.message.reply_markup:
            kwargs["reply_markup"] = callback.message.reply_markup
        try:
            await callback.message.edit_text(text, **kwargs)
            await self.track_bot_message(callback.message)
        except Exception:
            await self.cleanup_chat(callback.message)
            if "reply_markup" not in kwargs:
                kwargs["reply_markup"] = self._main_keyboard_provider()
            sent = await callback.message.answer(text, **kwargs)
            await self.track_bot_message(sent)
