"""Anchor-based chat UI service (этап 4).

Модель:
- На chat хранится один anchor — inline-сообщение, которое держит текущий шаг flow.
- Рядом с anchor может жить опциональное reply-aux сообщение, несущее reply-клавиатуру (например, «⬅ Назад»).
- Переход между шагами — `edit_message_text` anchor'а (никаких массовых `delete_message`).
- Переход в главное меню — `close_flow` + отдельное «пост-flow» сообщение с reply-клавиатурой меню.
- Пользовательские сообщения удаляются точечно через `delete_user_message`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message, ReplyKeyboardMarkup

from app.db import Database


class _Unset:
    """Sentinel: «параметр не передан» (отличается от явного None)."""

    __slots__ = ()


UNSET: Any = _Unset()

NOTICE_FLOW_KIND = "_notice"
"""Системный flow_kind для одиночных «notice»-сообщений (главное меню, итоги действия).

Гарантируется, что в чате одновременно живёт максимум один notice: следующий `open_flow`
с любым обычным `flow_kind` удалит его, как любую смену flow.
"""


class ChatUiService:
    """Anchor-based chat UI."""

    def __init__(
        self,
        main_keyboard_provider: Callable[[int], ReplyKeyboardMarkup],
        flow_keyboard_provider: Callable[[], ReplyKeyboardMarkup],
        *,
        database: Database | None = None,
    ) -> None:
        self._main_keyboard_provider = main_keyboard_provider
        self._flow_keyboard_provider = flow_keyboard_provider
        self._db = database
        self._anchor_memory: dict[int, dict[str, Any]] = {}

    # ── reply-клавиатура по умолчанию (одно сервисное сообщение на flow) ────

    def flow_keyboard(self) -> ReplyKeyboardMarkup:
        return self._flow_keyboard_provider()

    def main_keyboard(self, tg_user_id: int) -> ReplyKeyboardMarkup:
        return self._main_keyboard_provider(tg_user_id)

    # ── низкоуровневое хранилище anchor'ов ──────────────────────────────────

    def _load_anchor(self, chat_id: int) -> dict[str, Any] | None:
        if self._db is None:
            row = self._anchor_memory.get(chat_id)
            return dict(row) if row else None
        with self._db.transaction() as conn:
            row = conn.execute(
                """
                SELECT anchor_message_id, flow_kind, reply_aux_message_id
                FROM chat_anchors WHERE chat_id = ?
                """,
                (chat_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "anchor_message_id": int(row["anchor_message_id"]),
            "flow_kind": str(row["flow_kind"]),
            "reply_aux_message_id": int(row["reply_aux_message_id"])
            if row["reply_aux_message_id"] is not None
            else None,
        }

    def _save_anchor(
        self,
        chat_id: int,
        *,
        anchor_message_id: int,
        flow_kind: str,
        reply_aux_message_id: int | None,
    ) -> None:
        if self._db is None:
            self._anchor_memory[chat_id] = {
                "anchor_message_id": anchor_message_id,
                "flow_kind": flow_kind,
                "reply_aux_message_id": reply_aux_message_id,
            }
            return
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO chat_anchors(chat_id, anchor_message_id, flow_kind, reply_aux_message_id, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id) DO UPDATE SET
                    anchor_message_id = excluded.anchor_message_id,
                    flow_kind = excluded.flow_kind,
                    reply_aux_message_id = excluded.reply_aux_message_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (chat_id, anchor_message_id, flow_kind, reply_aux_message_id),
            )

    def _delete_anchor(self, chat_id: int) -> None:
        if self._db is None:
            self._anchor_memory.pop(chat_id, None)
            return
        with self._db.transaction() as conn:
            conn.execute("DELETE FROM chat_anchors WHERE chat_id = ?", (chat_id,))

    # ── reply-aux helpers ───────────────────────────────────────────────────

    @staticmethod
    async def _safe_delete(bot: Bot, chat_id: int, message_id: int | None) -> None:
        if message_id is None:
            return
        try:
            await bot.delete_message(chat_id, message_id)
        except Exception:
            pass

    async def _apply_reply_aux(
        self,
        *,
        chat_id: int,
        bot: Bot,
        reply_keyboard: ReplyKeyboardMarkup | None,
        reply_hint: str,
        prev_aux_id: int | None,
    ) -> int | None:
        """Перерисовать reply-aux согласно reply_keyboard. None убирает сообщение, иначе посылает заново."""
        if reply_keyboard is None:
            await self._safe_delete(bot, chat_id, prev_aux_id)
            return None
        await self._safe_delete(bot, chat_id, prev_aux_id)
        sent = await bot.send_message(chat_id=chat_id, text=reply_hint, reply_markup=reply_keyboard)
        return int(sent.message_id)

    # ── flow API ────────────────────────────────────────────────────────────

    async def open_flow(
        self,
        *,
        chat_id: int,
        bot: Bot,
        flow_kind: str,
        text: str,
        inline_markup: InlineKeyboardMarkup | None = None,
        reply_keyboard: ReplyKeyboardMarkup | None = None,
        reply_hint: str = "Кнопки навигации ниже:",
    ) -> int:
        """Открыть anchor нового шага flow.

        - нет anchor → отправить новое сообщение;
        - тот же flow_kind → edit_message_text (fallback на send при TelegramBadRequest);
        - другой flow_kind → удалить предыдущий anchor + reply-aux, отправить новое.

        `reply_keyboard`:
        - None — reply-aux нет/удаляется (по умолчанию);
        - markup — отправить служебное reply-сообщение с этой клавиатурой.
        """
        prev = self._load_anchor(chat_id)

        if prev is None:
            sent = await bot.send_message(chat_id=chat_id, text=text, reply_markup=inline_markup)
            aux_id = await self._apply_reply_aux(
                chat_id=chat_id, bot=bot, reply_keyboard=reply_keyboard, reply_hint=reply_hint, prev_aux_id=None
            )
            self._save_anchor(
                chat_id,
                anchor_message_id=int(sent.message_id),
                flow_kind=flow_kind,
                reply_aux_message_id=aux_id,
            )
            return int(sent.message_id)

        prev_anchor = int(prev["anchor_message_id"])
        prev_kind = str(prev["flow_kind"])
        prev_aux = prev["reply_aux_message_id"]

        if prev_kind == flow_kind:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id, message_id=prev_anchor, text=text, reply_markup=inline_markup
                )
                aux_id = await self._apply_reply_aux(
                    chat_id=chat_id, bot=bot, reply_keyboard=reply_keyboard, reply_hint=reply_hint, prev_aux_id=prev_aux
                )
                self._save_anchor(
                    chat_id,
                    anchor_message_id=prev_anchor,
                    flow_kind=flow_kind,
                    reply_aux_message_id=aux_id,
                )
                return prev_anchor
            except TelegramBadRequest:
                await self._safe_delete(bot, chat_id, prev_aux)
                self._delete_anchor(chat_id)
                sent = await bot.send_message(chat_id=chat_id, text=text, reply_markup=inline_markup)
                aux_id = await self._apply_reply_aux(
                    chat_id=chat_id, bot=bot, reply_keyboard=reply_keyboard, reply_hint=reply_hint, prev_aux_id=None
                )
                self._save_anchor(
                    chat_id,
                    anchor_message_id=int(sent.message_id),
                    flow_kind=flow_kind,
                    reply_aux_message_id=aux_id,
                )
                return int(sent.message_id)

        await self._safe_delete(bot, chat_id, prev_anchor)
        await self._safe_delete(bot, chat_id, prev_aux)
        self._delete_anchor(chat_id)
        sent = await bot.send_message(chat_id=chat_id, text=text, reply_markup=inline_markup)
        aux_id = await self._apply_reply_aux(
            chat_id=chat_id, bot=bot, reply_keyboard=reply_keyboard, reply_hint=reply_hint, prev_aux_id=None
        )
        self._save_anchor(
            chat_id,
            anchor_message_id=int(sent.message_id),
            flow_kind=flow_kind,
            reply_aux_message_id=aux_id,
        )
        return int(sent.message_id)

    async def update_flow(
        self,
        *,
        chat_id: int,
        bot: Bot,
        flow_kind: str,
        text: str,
        inline_markup: InlineKeyboardMarkup | None = None,
        reply_keyboard: Any = UNSET,
        reply_hint: str = "Кнопки навигации ниже:",
    ) -> int:
        """Обновить anchor через edit_message_text.

        - нет anchor → fallback к send_message;
        - есть anchor → edit; при TelegramBadRequest — fallback к send_message;
        - `reply_keyboard=UNSET` — текущее reply-aux не трогать;
        - `reply_keyboard=None` — удалить reply-aux;
        - `reply_keyboard=markup` — переустановить reply-aux.
        """
        prev = self._load_anchor(chat_id)

        if prev is None:
            sent = await bot.send_message(chat_id=chat_id, text=text, reply_markup=inline_markup)
            aux_kw = None if reply_keyboard is UNSET else reply_keyboard
            aux_id = await self._apply_reply_aux(
                chat_id=chat_id, bot=bot, reply_keyboard=aux_kw, reply_hint=reply_hint, prev_aux_id=None
            )
            self._save_anchor(
                chat_id,
                anchor_message_id=int(sent.message_id),
                flow_kind=flow_kind,
                reply_aux_message_id=aux_id,
            )
            return int(sent.message_id)

        prev_anchor = int(prev["anchor_message_id"])
        prev_aux = prev["reply_aux_message_id"]
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=prev_anchor, text=text, reply_markup=inline_markup)
            if reply_keyboard is UNSET:
                aux_id = prev_aux
            else:
                aux_id = await self._apply_reply_aux(
                    chat_id=chat_id,
                    bot=bot,
                    reply_keyboard=reply_keyboard,
                    reply_hint=reply_hint,
                    prev_aux_id=prev_aux,
                )
            self._save_anchor(
                chat_id,
                anchor_message_id=prev_anchor,
                flow_kind=flow_kind,
                reply_aux_message_id=aux_id,
            )
            return prev_anchor
        except TelegramBadRequest:
            await self._safe_delete(bot, chat_id, prev_aux)
            self._delete_anchor(chat_id)
            sent = await bot.send_message(chat_id=chat_id, text=text, reply_markup=inline_markup)
            aux_kw = None if reply_keyboard is UNSET else reply_keyboard
            aux_id = await self._apply_reply_aux(
                chat_id=chat_id, bot=bot, reply_keyboard=aux_kw, reply_hint=reply_hint, prev_aux_id=None
            )
            self._save_anchor(
                chat_id,
                anchor_message_id=int(sent.message_id),
                flow_kind=flow_kind,
                reply_aux_message_id=aux_id,
            )
            return int(sent.message_id)

    async def close_flow(self, *, chat_id: int, bot: Bot, keep_message_id: int | None = None) -> None:
        """Завершить flow: удалить anchor (если не keep) и reply-aux. Запись стирается."""
        prev = self._load_anchor(chat_id)
        if prev is None:
            return
        prev_anchor = int(prev["anchor_message_id"])
        prev_aux = prev["reply_aux_message_id"]
        if keep_message_id != prev_anchor:
            await self._safe_delete(bot, chat_id, prev_anchor)
        await self._safe_delete(bot, chat_id, prev_aux)
        self._delete_anchor(chat_id)

    # ── вспомогательные операции ───────────────────────────────────────────

    async def replace_with_notice(
        self,
        *,
        chat_id: int,
        bot: Bot,
        text: str,
        inline_markup: InlineKeyboardMarkup | None = None,
        reply_keyboard: ReplyKeyboardMarkup | None = None,
        reply_hint: str = "Главное меню:",
    ) -> int:
        """Заменить любой текущий anchor + reply-aux на одиночное notice-сообщение.

        Notice — это anchor с системным `flow_kind=NOTICE_FLOW_KIND`. Следующий обычный
        `open_flow` (любого другого kind) удалит его автоматически — в чате не накапливаются
        итоговые сообщения вида «Поездка создана», «Регистрация завершена», «Бронь отменена».

        Если предыдущий anchor — тоже notice, текст переедактируется на месте без delete+send.
        """
        return await self.open_flow(
            chat_id=chat_id,
            bot=bot,
            flow_kind=NOTICE_FLOW_KIND,
            text=text,
            inline_markup=inline_markup,
            reply_keyboard=reply_keyboard,
            reply_hint=reply_hint,
        )

    @staticmethod
    async def delete_user_message(message: Message) -> None:
        """Точечное удаление пользовательского сообщения (без массового cleanup)."""
        try:
            await message.delete()
        except Exception:
            pass
