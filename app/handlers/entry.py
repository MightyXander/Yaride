"""Deep-link вход в Mini App: /start -> WebApp кнопка, /start trip_<id> -> read-only карточка поездки."""

from __future__ import annotations

import html

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.chat_ui import ChatUiService
from app.formatting import format_trip_row
from app.repo import Repo
from app.ui import KeyboardFactory
from webapp_api.serializers import trip_card_to_dict

router = Router()

FLOW_KIND = "entry"


@router.message(Command("start"))
async def entry_start(
    message: Message,
    state: FSMContext,
    repo: Repo,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
    command: CommandObject,
) -> None:
    """
    /start -> приветствие + WebApp-кнопка «Открыть приложение».
    /start trip_<id> -> read-only карточка поездки + WebApp-кнопка.
    """
    await state.clear()
    await chat_ui.delete_user_message(message)

    payload = command.args.strip() if command.args else ""

    # Deep-link: /start trip_<id>
    if payload.startswith("trip_"):
        trip_id_str = payload[5:]
        try:
            trip_id = int(trip_id_str)
        except ValueError:
            await chat_ui.close_flow(chat_id=message.chat.id, bot=message.bot)
            await chat_ui.replace_with_notice(
                chat_id=message.chat.id,
                bot=message.bot,
                text="Некорректная ссылка на поездку.",
                reply_keyboard=keyboards.main_keyboard(is_driver=repo.users.is_active_driver(message.from_user.id)),
            )
            return

        trip_row = repo.trips.get_trip_public_card(trip_id)
        if not trip_row:
            await chat_ui.close_flow(chat_id=message.chat.id, bot=message.bot)
            await chat_ui.replace_with_notice(
                chat_id=message.chat.id,
                bot=message.bot,
                text="Поездка не найдена.",
                reply_keyboard=keyboards.main_keyboard(is_driver=repo.users.is_active_driver(message.from_user.id)),
            )
            return

        # Read-only карточка поездки
        card = trip_card_to_dict(trip_row)
        when = html.escape(card["whenLabel"])
        from_title = html.escape(card["fromTitle"])
        to_title = html.escape(card["toTitle"])
        price = card["priceRub"]
        seats_free = card["seatsFree"]
        driver_name = html.escape(card["driverName"] or "")
        driver_rating = card["driverRating"]

        text = f"""<b>Поездка #{trip_id}</b>

<b>Маршрут:</b> {from_title} → {to_title}
<b>Когда:</b> {when}
<b>Цена:</b> {price} руб
<b>Свободных мест:</b> {seats_free}
<b>Водитель:</b> {driver_name} (⭐ {driver_rating})

Для бронирования откройте приложение ниже."""

        await chat_ui.open_flow(
            chat_id=message.chat.id,
            bot=message.bot,
            flow_kind=FLOW_KIND,
            text=text,
            inline_markup=keyboards.webapp_button_keyboard(),
        )
        return

    # Обычный /start без payload -> приветствие + WebApp кнопка
    user = repo.users.get_user(message.from_user.id)
    name = "друг"
    if user:
        name = str(user["name"] or "").strip() or (message.from_user.first_name or "друг")
    else:
        name = message.from_user.first_name or "друг"

    text = f"""Привет, <b>{html.escape(name)}</b>!

Добро пожаловать в Yaride — сервис совместных поездок.

Откройте приложение, чтобы найти или создать поездку."""

    await chat_ui.open_flow(
        chat_id=message.chat.id,
        bot=message.bot,
        flow_kind=FLOW_KIND,
        text=text,
        inline_markup=keyboards.webapp_button_keyboard(),
    )
