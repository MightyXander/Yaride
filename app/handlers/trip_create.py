"""Создание поездки: старт, префиксы C*, время/места/цена, геолокация на шаге отправления."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot_support import STALE_CREATE_FLOW
from app.chat_ui import ChatUiService
from app.config import Settings
from app.geo_suggestion import handle_start_locality_geo
from app.driver_access import DRIVER_MOD_PENDING, DRIVER_MOD_REJECTED, driver_moderation_status, is_approved_driver
from app.repo import Repo
from app.states import TripCreate
from app.trip_flow import TripFlowOrchestrator
from app.ui import KeyboardFactory

router = Router()

FLOW_KIND = "create"


@router.message(StateFilter(TripCreate.start_district), F.location)
async def create_start_district_geo(
    message: Message,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
    settings: Settings,
    keyboards: KeyboardFactory,
) -> None:
    await handle_start_locality_geo(
        message, state, repo, mode="create", flow=flow, settings=settings, keyboards=keyboards
    )


@router.message(F.text == "Создать поездку")
async def create_trip_start(
    message: Message,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
) -> None:
    user = repo.users.get_user(message.from_user.id)
    await chat_ui.delete_user_message(message)
    u = repo.users.get_user(message.from_user.id)
    mk = keyboards.main_keyboard(is_driver=repo.users.is_active_driver(message.from_user.id))
    if not user:
        await chat_ui.close_flow(chat_id=message.chat.id, bot=message.bot)
        await chat_ui.replace_with_notice(
            chat_id=message.chat.id,
            bot=message.bot,
            text="Сначала зарегистрируйся через /start.",
            reply_keyboard=mk,
        )
        return
    if not is_approved_driver(user):
        notice = "Создавать поездки может только одобренный водитель."
        status = driver_moderation_status(user)
        if status == DRIVER_MOD_PENDING:
            notice = "Заявка водителя на модерации. Создание поездок откроется после одобрения администратором."
        elif status == DRIVER_MOD_REJECTED:
            notice = "Заявка водителя отклонена. Подай заявку заново через профиль."
        await chat_ui.close_flow(chat_id=message.chat.id, bot=message.bot)
        await chat_ui.replace_with_notice(
            chat_id=message.chat.id,
            bot=message.bot,
            text=notice,
            reply_keyboard=mk,
        )
        return
    await flow.begin(message, state, repo, mode="create")


@router.callback_query(F.data.startswith("Cfl:"))
async def create_pick_start_locality(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
) -> None:
    await flow.pick_locality(callback, state, repo, mode="create", is_start=True)


@router.callback_query(F.data.startswith("Cfd:"))
async def create_pick_start_district(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
) -> None:
    await flow.pick_district(callback, state, repo, mode="create", is_start=True)


@router.callback_query(F.data.startswith("Cfa:"))
async def create_pick_start_admin(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
) -> None:
    await flow.pick_admin(callback, state, repo, mode="create", is_start=True)


@router.callback_query(F.data.startswith("Cfp:"))
async def create_pick_start_stop(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
) -> None:
    await flow.pick_start_stop(callback, state, repo, mode="create")


@router.callback_query(F.data.startswith("Ctl:"))
async def create_pick_end_locality(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
) -> None:
    await flow.pick_locality(callback, state, repo, mode="create", is_start=False)


@router.callback_query(F.data.startswith("Ctd:"))
async def create_pick_end_district(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
) -> None:
    await flow.pick_district(callback, state, repo, mode="create", is_start=False)


@router.callback_query(F.data.startswith("Cta:"))
async def create_pick_end_admin(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
) -> None:
    await flow.pick_admin(callback, state, repo, mode="create", is_start=False)


@router.callback_query(F.data.startswith("Ctp:"))
async def create_pick_end_stop(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
) -> None:
    await flow.pick_end_stop(callback, state, repo, mode="create")


@router.callback_query(F.data.startswith("create_time:"))
async def create_set_time(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
) -> None:
    data = await state.get_data()
    if "trip_date" not in data:
        if callback.message:
            u = repo.users.get_user(callback.from_user.id)
            await chat_ui.close_flow(chat_id=callback.message.chat.id, bot=callback.bot)
            await chat_ui.replace_with_notice(
                chat_id=callback.message.chat.id,
                bot=callback.bot,
                text=STALE_CREATE_FLOW,
                reply_keyboard=keyboards.main_keyboard(is_driver=repo.users.is_active_driver(message.from_user.id)),
            )
        await state.clear()
        await callback.answer()
        return
    departure_time = callback.data.split(":", 1)[1]
    await state.update_data(departure_time=departure_time)
    await state.set_state(TripCreate.seats)
    if callback.message:
        await chat_ui.update_flow(
            chat_id=callback.message.chat.id,
            bot=callback.bot,
            flow_kind=FLOW_KIND,
            text="Выбери количество пассажиров:",
            inline_markup=keyboards.seats_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("create_seats:"))
async def create_set_seats(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
    settings: Settings,
) -> None:
    data = await state.get_data()
    if "trip_date" not in data or "departure_time" not in data:
        if callback.message:
            u = repo.users.get_user(callback.from_user.id)
            await chat_ui.close_flow(chat_id=callback.message.chat.id, bot=callback.bot)
            await chat_ui.replace_with_notice(
                chat_id=callback.message.chat.id,
                bot=callback.bot,
                text=STALE_CREATE_FLOW,
                reply_keyboard=keyboards.main_keyboard(is_driver=repo.users.is_active_driver(message.from_user.id)),
            )
        await state.clear()
        await callback.answer()
        return
    try:
        seats = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректные данные кнопки.", show_alert=True)
        return
    if seats not in settings.seats_choices:
        allowed_seats = ", ".join(str(s) for s in settings.seats_choices)
        if callback.message:
            await chat_ui.update_flow(
                chat_id=callback.message.chat.id,
                bot=callback.bot,
                flow_kind=FLOW_KIND,
                text=f"Допустимо только: {allowed_seats}.",
                inline_markup=keyboards.seats_keyboard(),
            )
        await callback.answer()
        return
    await state.update_data(seats=seats)
    await state.set_state(TripCreate.price)
    if callback.message:
        await chat_ui.update_flow(
            chat_id=callback.message.chat.id,
            bot=callback.bot,
            flow_kind=FLOW_KIND,
            text="Выбери цену поездки:",
            inline_markup=keyboards.price_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("create_price:"))
async def create_set_price(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
    settings: Settings,
) -> None:
    try:
        price = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректные данные кнопки.", show_alert=True)
        return
    if price not in settings.price_choices:
        allowed_prices = ", ".join(str(p) for p in settings.price_choices)
        if callback.message:
            await chat_ui.update_flow(
                chat_id=callback.message.chat.id,
                bot=callback.bot,
                flow_kind=FLOW_KIND,
                text=f"Доступные цены: {allowed_prices}.",
                inline_markup=keyboards.price_keyboard(),
            )
        await callback.answer()
        return
    data = await state.get_data()
    required_keys = ("start_point", "end_point", "trip_date", "departure_time", "seats")
    if any(k not in data or data[k] is None for k in required_keys):
        if callback.message:
            u = repo.users.get_user(callback.from_user.id)
            await chat_ui.close_flow(chat_id=callback.message.chat.id, bot=callback.bot)
            await chat_ui.replace_with_notice(
                chat_id=callback.message.chat.id,
                bot=callback.bot,
                text=STALE_CREATE_FLOW,
                reply_keyboard=keyboards.main_keyboard(is_driver=repo.users.is_active_driver(message.from_user.id)),
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
            u = repo.users.get_user(callback.from_user.id)
            await chat_ui.close_flow(chat_id=callback.message.chat.id, bot=callback.bot)
            await chat_ui.replace_with_notice(
                chat_id=callback.message.chat.id,
                bot=callback.bot,
                text=str(exc),
                reply_keyboard=keyboards.main_keyboard(is_driver=repo.users.is_active_driver(message.from_user.id)),
            )
        await state.clear()
        await callback.answer()
        return

    await state.clear()
    if callback.message:
        u = repo.users.get_user(callback.from_user.id)
        await chat_ui.close_flow(chat_id=callback.message.chat.id, bot=callback.bot)
        await chat_ui.replace_with_notice(
            chat_id=callback.message.chat.id,
            bot=callback.bot,
            text=f"Поездка #{trip_id} создана и доступна для поиска.",
            reply_keyboard=keyboards.main_keyboard(is_driver=repo.users.is_active_driver(message.from_user.id)),
        )
    await callback.answer()
