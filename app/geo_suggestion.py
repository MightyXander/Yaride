"""Гео-подсказки на шаге выбора пункта отправления.

Логика перенесена из app.bot_support, чтобы убрать зависимость хендлеров
от глобальных переменных модуля: теперь все зависимости передаются явно.
"""

from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, Message

from app.config import Settings
from app.repo import Repo
from app.trip_flow import (
    GEO_USER_LOCATION_IDS_KEY,
    TripFlowOrchestrator,
    delete_tracked_user_geo_messages,
)
from app.ui import KeyboardFactory

GEO_SUGGEST_MESSAGE_KEY = "geo_suggest_message_id"


async def _safe_delete(bot: Bot, chat_id: int, message_id: int) -> None:
    """Удалить сообщение, игнорируя ошибки (уже удалено / недоступно)."""
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass


async def _send_or_edit_suggestions(
    message: Message,
    prev_mid: int | None,
    text: str,
    markup: InlineKeyboardMarkup,
) -> int:
    """Отдельное сообщение «Ближайшие остановки» (не anchor): edit при наличии, иначе send."""
    bot = message.bot
    chat_id = message.chat.id
    if prev_mid is not None:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=prev_mid, text=text, reply_markup=markup)
            return prev_mid
        except TelegramBadRequest:
            await _safe_delete(bot, chat_id, prev_mid)
    sent = await message.answer(text, reply_markup=markup)
    return sent.message_id


async def handle_start_locality_geo(
    message: Message,
    state: FSMContext,
    repo: Repo,
    *,
    mode: str,
    flow: TripFlowOrchestrator,
    settings: Settings,
    keyboards: KeyboardFactory,
) -> None:
    """Геолокация на шаге выбора отправления: показать топ остановок или перейти к городу."""
    loc = message.location
    if loc is None:
        return
    lat = float(loc.latitude)
    lng = float(loc.longitude)

    data = await state.get_data()
    prev_mid_raw = data.get(GEO_SUGGEST_MESSAGE_KEY)
    prev_mid: int | None = int(prev_mid_raw) if prev_mid_raw is not None else None

    loc_ids = list(data.get(GEO_USER_LOCATION_IDS_KEY) or [])
    loc_ids.append(message.message_id)
    await state.update_data(**{GEO_USER_LOCATION_IDS_KEY: loc_ids})

    ranked = repo.routes.nearest_stops_global(
        lat, lng, limit=settings.geo_suggest_limit, max_km=settings.geo_suggest_max_km
    )
    if ranked:
        txt = (
            "Ближайшие остановки посадки к твоей точке (км по прямой до точки остановки "
            "в каталоге, не время в пути). "
            "Выбери кнопку ниже или продолжи выбор населённого пункта кнопками в сообщении выше."
        )
        mid = await _send_or_edit_suggestions(
            message, prev_mid, txt, keyboards.geo_suggested_start_stops_keyboard(ranked, mode)
        )
        await state.update_data(**{GEO_SUGGEST_MESSAGE_KEY: mid})
        return

    if prev_mid is not None:
        await _safe_delete(message.bot, message.chat.id, prev_mid)
    await state.update_data(**{GEO_SUGGEST_MESSAGE_KEY: None})

    await delete_tracked_user_geo_messages(message.bot, message.chat.id, state)
    await flow.apply_start_locality_from_geo(message, state, repo, mode, "Ярославль")
