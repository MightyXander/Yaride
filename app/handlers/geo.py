"""Геолокация на шаге выбора отправления и выбор остановки из подсказки gxs:."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.repo import Repo
from app.trip_flow import TripFlowOrchestrator

router = Router()


@router.callback_query(F.data.startswith("gxs:"))
async def geo_pick_suggested_start_stop(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    flow: TripFlowOrchestrator,
) -> None:
    cur = await state.get_state()
    if cur is None or not str(cur).endswith("start_locality"):
        await callback.answer("Шаг устарел. Начни выбор маршрута заново.", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return
    _, mode, sid = parts
    if mode not in ("search", "create"):
        await callback.answer()
        return
    try:
        pid = int(sid)
    except ValueError:
        await callback.answer()
        return
    await flow.transition_geo_pick_start_stop(callback, state, repo, mode, pid)
