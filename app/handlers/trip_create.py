"""Создание поездки: старт, префиксы C*, время/места/цена, геолокация на шаге отправления."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.repo import Repo
from app.states import TripCreate

router = Router()

FLOW_KIND = "create"


@router.message(StateFilter(TripCreate.start_locality), F.location)
async def create_start_locality_geo(message: Message, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import _handle_start_locality_geo

    await _handle_start_locality_geo(message, state, repo, mode="create")


@router.message(F.text == "Создать поездку")
async def create_trip_start(message: Message, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import (
        FLOW_ORCHESTRATOR,
        close_flow,
        delete_user_message,
        main_keyboard,
        send_post_flow_message,
    )

    user = repo.users.get_user(message.from_user.id)
    await delete_user_message(message)
    if not user:
        await close_flow(chat_id=message.chat.id, bot=message.bot)
        await send_post_flow_message(
            chat_id=message.chat.id,
            bot=message.bot,
            text="Сначала зарегистрируйся через /start.",
            reply_keyboard=main_keyboard(repo, message.from_user.id),
        )
        return
    if user["role"] != "driver":
        await close_flow(chat_id=message.chat.id, bot=message.bot)
        await send_post_flow_message(
            chat_id=message.chat.id,
            bot=message.bot,
            text="Создавать поездки может только водитель.",
            reply_keyboard=main_keyboard(repo, message.from_user.id),
        )
        return
    await FLOW_ORCHESTRATOR.begin(message, state, repo, mode="create")


@router.callback_query(F.data.startswith("Cfl:"))
async def create_pick_start_locality(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import FLOW_ORCHESTRATOR

    await FLOW_ORCHESTRATOR.pick_locality(callback, state, repo, mode="create", is_start=True)


@router.callback_query(F.data.startswith("Cfd:"))
async def create_pick_start_district(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import FLOW_ORCHESTRATOR

    await FLOW_ORCHESTRATOR.pick_district(callback, state, repo, mode="create", is_start=True)


@router.callback_query(F.data.startswith("Cfa:"))
async def create_pick_start_admin(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import FLOW_ORCHESTRATOR

    await FLOW_ORCHESTRATOR.pick_admin(callback, state, repo, mode="create", is_start=True)


@router.callback_query(F.data.startswith("Cfp:"))
async def create_pick_start_stop(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import FLOW_ORCHESTRATOR

    await FLOW_ORCHESTRATOR.pick_start_stop(callback, state, repo, mode="create")


@router.callback_query(F.data.startswith("Ctl:"))
async def create_pick_end_locality(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import FLOW_ORCHESTRATOR

    await FLOW_ORCHESTRATOR.pick_locality(callback, state, repo, mode="create", is_start=False)


@router.callback_query(F.data.startswith("Ctd:"))
async def create_pick_end_district(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import FLOW_ORCHESTRATOR

    await FLOW_ORCHESTRATOR.pick_district(callback, state, repo, mode="create", is_start=False)


@router.callback_query(F.data.startswith("Cta:"))
async def create_pick_end_admin(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import FLOW_ORCHESTRATOR

    await FLOW_ORCHESTRATOR.pick_admin(callback, state, repo, mode="create", is_start=False)


@router.callback_query(F.data.startswith("Ctp:"))
async def create_pick_end_stop(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import FLOW_ORCHESTRATOR

    await FLOW_ORCHESTRATOR.pick_end_stop(callback, state, repo, mode="create")


@router.callback_query(F.data.startswith("create_time:"))
async def create_set_time(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import (
        STALE_CREATE_FLOW,
        add_back_button,
        close_flow,
        main_keyboard,
        seats_keyboard,
        send_post_flow_message,
        update_flow,
    )

    data = await state.get_data()
    if "trip_date" not in data:
        if callback.message:
            await close_flow(chat_id=callback.message.chat.id, bot=callback.bot)
            await send_post_flow_message(
                chat_id=callback.message.chat.id,
                bot=callback.bot,
                text=STALE_CREATE_FLOW,
                reply_keyboard=main_keyboard(repo, callback.from_user.id),
            )
        await state.clear()
        await callback.answer()
        return
    departure_time = callback.data.split(":", 1)[1]
    await state.update_data(departure_time=departure_time)
    await state.set_state(TripCreate.seats)
    if callback.message:
        await update_flow(
            chat_id=callback.message.chat.id,
            bot=callback.bot,
            flow_kind=FLOW_KIND,
            text="Выбери количество пассажиров:",
            inline_markup=add_back_button(seats_keyboard(), "create_time"),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("create_seats:"))
async def create_set_seats(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import (
        STALE_CREATE_FLOW,
        _active_settings,
        add_back_button,
        close_flow,
        main_keyboard,
        price_keyboard,
        seats_keyboard,
        send_post_flow_message,
        update_flow,
    )

    data = await state.get_data()
    if "trip_date" not in data or "departure_time" not in data:
        if callback.message:
            await close_flow(chat_id=callback.message.chat.id, bot=callback.bot)
            await send_post_flow_message(
                chat_id=callback.message.chat.id,
                bot=callback.bot,
                text=STALE_CREATE_FLOW,
                reply_keyboard=main_keyboard(repo, callback.from_user.id),
            )
        await state.clear()
        await callback.answer()
        return
    try:
        seats = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректные данные кнопки.", show_alert=True)
        return
    cfg = _active_settings()
    if seats not in cfg.seats_choices:
        allowed_seats = ", ".join(str(s) for s in cfg.seats_choices)
        if callback.message:
            await update_flow(
                chat_id=callback.message.chat.id,
                bot=callback.bot,
                flow_kind=FLOW_KIND,
                text=f"Допустимо только: {allowed_seats}.",
                inline_markup=add_back_button(seats_keyboard(), "create_time"),
            )
        await callback.answer()
        return
    await state.update_data(seats=seats)
    await state.set_state(TripCreate.price)
    if callback.message:
        await update_flow(
            chat_id=callback.message.chat.id,
            bot=callback.bot,
            flow_kind=FLOW_KIND,
            text="Выбери цену поездки:",
            inline_markup=add_back_button(price_keyboard(), "create_seats"),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("create_price:"))
async def create_set_price(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import (
        STALE_CREATE_FLOW,
        _active_settings,
        add_back_button,
        close_flow,
        main_keyboard,
        price_keyboard,
        send_post_flow_message,
        update_flow,
    )

    try:
        price = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректные данные кнопки.", show_alert=True)
        return
    cfg = _active_settings()
    if price not in cfg.price_choices:
        allowed_prices = ", ".join(str(p) for p in cfg.price_choices)
        if callback.message:
            await update_flow(
                chat_id=callback.message.chat.id,
                bot=callback.bot,
                flow_kind=FLOW_KIND,
                text=f"Доступные цены: {allowed_prices}.",
                inline_markup=add_back_button(price_keyboard(), "create_seats"),
            )
        await callback.answer()
        return
    data = await state.get_data()
    required_keys = ("start_point", "end_point", "trip_date", "departure_time", "seats")
    if any(k not in data or data[k] is None for k in required_keys):
        if callback.message:
            await close_flow(chat_id=callback.message.chat.id, bot=callback.bot)
            await send_post_flow_message(
                chat_id=callback.message.chat.id,
                bot=callback.bot,
                text=STALE_CREATE_FLOW,
                reply_keyboard=main_keyboard(repo, callback.from_user.id),
            )
        await state.clear()
        await callback.answer()
        return
    try:
        trip_id = repo.trips.create_trip(
            tg_driver_id=callback.from_user.id,
            start_point_id=data["start_point"],
            end_point_id=data["end_point"],
            trip_date=data["trip_date"],
            departure_time=data["departure_time"],
            seats_total=data["seats"],
            price_rub=price,
        )
    except ValueError as exc:
        if callback.message:
            await close_flow(chat_id=callback.message.chat.id, bot=callback.bot)
            await send_post_flow_message(
                chat_id=callback.message.chat.id,
                bot=callback.bot,
                text=str(exc),
                reply_keyboard=main_keyboard(repo, callback.from_user.id),
            )
        await state.clear()
        await callback.answer()
        return

    await state.clear()
    if callback.message:
        await close_flow(chat_id=callback.message.chat.id, bot=callback.bot)
        await send_post_flow_message(
            chat_id=callback.message.chat.id,
            bot=callback.bot,
            text=f"Поездка #{trip_id} создана и доступна для поиска.",
            reply_keyboard=main_keyboard(repo, callback.from_user.id),
        )
    await callback.answer()
