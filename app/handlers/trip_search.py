"""Поиск поездок: старт, префиксы S*, геолокация на шаге пункта отправления."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.chat_ui import ChatUiService
from app.config import Settings
from app.geo_suggestion import handle_start_locality_geo
from app.repo import Repo
from app.states import TripSearch
from app.trip_flow import TripFlowOrchestrator
from app.ui import KeyboardFactory

router = Router()


@router.message(F.text.in_(["Найти поездки"]))
async def find_trips_start(
    message: Message,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
) -> None:
    user = repo.users.get_user(message.from_user.id)
    await chat_ui.delete_user_message(message)
    if not user:
        await chat_ui.close_flow(chat_id=message.chat.id, bot=message.bot)
        u = repo.users.get_user(message.from_user.id)
        await chat_ui.replace_with_notice(
            chat_id=message.chat.id,
            bot=message.bot,
            text="Сначала зарегистрируйся через /start.",
            reply_keyboard=keyboards.main_keyboard(is_driver=repo.users.is_active_driver(message.from_user.id)),
        )
        return
    await flow.begin(message, state, repo, mode="search")


@router.callback_query(F.data.startswith("Sfl:"))
async def search_pick_start_locality(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
) -> None:
    await flow.pick_locality(callback, state, repo, mode="search", is_start=True)


@router.callback_query(F.data.startswith("Sfd:"))
async def search_pick_start_district(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
) -> None:
    await flow.pick_district(callback, state, repo, mode="search", is_start=True)


@router.callback_query(F.data.startswith("Sfa:"))
async def search_pick_start_admin(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
) -> None:
    await flow.pick_admin(callback, state, repo, mode="search", is_start=True)


@router.callback_query(F.data.startswith("Sfp:"))
async def search_pick_start_stop(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
) -> None:
    await flow.pick_start_stop(callback, state, repo, mode="search")


@router.callback_query(F.data.startswith("Stl:"))
async def search_pick_end_locality(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
) -> None:
    await flow.pick_locality(callback, state, repo, mode="search", is_start=False)


@router.callback_query(F.data.startswith("Std:"))
async def search_pick_end_district(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
) -> None:
    await flow.pick_district(callback, state, repo, mode="search", is_start=False)


@router.callback_query(F.data.startswith("Sta:"))
async def search_pick_end_admin(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
) -> None:
    await flow.pick_admin(callback, state, repo, mode="search", is_start=False)


@router.callback_query(F.data.startswith("Stp:"))
async def search_pick_end_stop(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
) -> None:
    await flow.pick_end_stop(callback, state, repo, mode="search")


@router.message(StateFilter(TripSearch.start_district), F.location)
async def search_start_district_geo(
    message: Message,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
    settings: Settings,
    keyboards: KeyboardFactory,
) -> None:
    await handle_start_locality_geo(
        message, state, repo, mode="search", flow=flow, settings=settings, keyboards=keyboards
    )
