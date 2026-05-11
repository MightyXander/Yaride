"""Поиск поездок: старт, префиксы S*, геолокация на шаге пункта отправления."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.repo import Repo
from app.states import TripSearch

router = Router()


@router.message(F.text.in_(["Найти поездки"]))
async def find_trips_start(message: Message, state: FSMContext, repo: Repo) -> None:
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
    await FLOW_ORCHESTRATOR.begin(message, state, repo, mode="search")


@router.callback_query(F.data.startswith("Sfl:"))
async def search_pick_start_locality(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import FLOW_ORCHESTRATOR

    await FLOW_ORCHESTRATOR.pick_locality(callback, state, repo, mode="search", is_start=True)


@router.callback_query(F.data.startswith("Sfd:"))
async def search_pick_start_district(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import FLOW_ORCHESTRATOR

    await FLOW_ORCHESTRATOR.pick_district(callback, state, repo, mode="search", is_start=True)


@router.callback_query(F.data.startswith("Sfa:"))
async def search_pick_start_admin(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import FLOW_ORCHESTRATOR

    await FLOW_ORCHESTRATOR.pick_admin(callback, state, repo, mode="search", is_start=True)


@router.callback_query(F.data.startswith("Sfp:"))
async def search_pick_start_stop(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import FLOW_ORCHESTRATOR

    await FLOW_ORCHESTRATOR.pick_start_stop(callback, state, repo, mode="search")


@router.callback_query(F.data.startswith("Stl:"))
async def search_pick_end_locality(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import FLOW_ORCHESTRATOR

    await FLOW_ORCHESTRATOR.pick_locality(callback, state, repo, mode="search", is_start=False)


@router.callback_query(F.data.startswith("Std:"))
async def search_pick_end_district(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import FLOW_ORCHESTRATOR

    await FLOW_ORCHESTRATOR.pick_district(callback, state, repo, mode="search", is_start=False)


@router.callback_query(F.data.startswith("Sta:"))
async def search_pick_end_admin(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import FLOW_ORCHESTRATOR

    await FLOW_ORCHESTRATOR.pick_admin(callback, state, repo, mode="search", is_start=False)


@router.callback_query(F.data.startswith("Stp:"))
async def search_pick_end_stop(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import FLOW_ORCHESTRATOR

    await FLOW_ORCHESTRATOR.pick_end_stop(callback, state, repo, mode="search")


@router.message(StateFilter(TripSearch.start_locality), F.location)
async def search_start_locality_geo(message: Message, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import _handle_start_locality_geo

    await _handle_start_locality_geo(message, state, repo, mode="search")
