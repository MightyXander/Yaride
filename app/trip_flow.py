"""Оркестратор шагов flow поиска и создания поездки на anchor-API (этап 4)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.chat_ui import UNSET, ChatUiService

# Порог, ниже которого несколько admin_area объединяются в одном списке остановок,
# чтобы не добавлять лишний шаг выбора подрайона при маленьком количестве вариантов.
DISTRICT_MERGED_STOPS_MAX = 15

_GEO_SUGGEST_MESSAGE_KEY = "geo_suggest_message_id"

GEO_USER_LOCATION_IDS_KEY = "geo_user_location_message_ids"


async def delete_tracked_user_geo_messages(bot, chat_id: int, state: FSMContext) -> None:
    """Удалить сообщения геолокации пользователя, накопленные за шаг выбора остановки посадки.

    Геосообщения остаются в чате пока пользователь выбирает — удаляем их при переходе на следующий шаг,
    чтобы не засорять историю.
    """
    data = await state.get_data()
    for mid in list(data.get(GEO_USER_LOCATION_IDS_KEY) or []):
        try:
            await bot.delete_message(chat_id, mid)
        except Exception:
            pass
    await state.update_data(**{GEO_USER_LOCATION_IDS_KEY: []})


def stale_flow_hint(mode: str) -> str:
    """Сообщение для callback.answer, когда данные FSM не совпадают с ожидаемыми (устаревшая кнопка)."""
    again = "«Найти поездки»" if mode == "search" else "«Создать поездку»"
    return f"Этот шаг устарел (или открыто старое сообщение с кнопками). Начни заново: {again}."


def _stop_matches_flow_selection(
    pt: Any,
    *,
    locality: str,
    district: str,
    admin_area: str | None,
) -> bool:
    """Проверить, что выбранная остановка соответствует параметрам FSM-шага.

    Защита от подмены: пользователь не должен уйти со страницы одного района
    и подтвердить остановку из другого через старый callback.
    """
    if pt is None:
        return False
    if str(pt["locality"]) != locality:
        return False
    if str(pt["district"] or "").strip() != str(district or "").strip():
        return False
    if admin_area is not None:
        if str(pt["admin_area"] or "").strip() != str(admin_area or "").strip():
            return False
    return True


class TripFlowOrchestrator:
    """Сборка шагов flow поиска/создания поездки поверх ChatUiService.open_flow/update_flow."""

    def __init__(
        self,
        *,
        mode_cfg: dict[str, dict[str, Any]],
        chat_ui: ChatUiService,
        localities_keyboard: Callable[..., Any],
        districts_keyboard: Callable[..., Any],
        stops_keyboard: Callable[..., Any],
        location_reply_keyboard: Callable[[], Any],
        trip_calendar_factory: Callable[..., Any],
    ) -> None:
        self._mode_cfg = mode_cfg
        self._chat_ui = chat_ui
        self._localities_keyboard = localities_keyboard
        self._districts_keyboard = districts_keyboard
        self._stops_keyboard = stops_keyboard
        self._location_reply_keyboard = location_reply_keyboard
        self._trip_calendar_factory = trip_calendar_factory

    def _cfg(self, mode: str) -> dict[str, Any]:
        return self._mode_cfg[mode]

    @staticmethod
    def _flow_kind(mode: str) -> str:
        return mode

    async def _update(
        self,
        callback: CallbackQuery,
        *,
        mode: str,
        text: str,
        inline_markup: InlineKeyboardMarkup,
        reply_keyboard: Any = UNSET,
    ) -> None:
        if not callback.message:
            return
        await self._chat_ui.update_flow(
            chat_id=callback.message.chat.id,
            bot=callback.bot,
            flow_kind=self._flow_kind(mode),
            text=text,
            inline_markup=inline_markup,
            reply_keyboard=reply_keyboard,
        )

    async def begin(self, message: Message, state: FSMContext, repo: Any, mode: str) -> None:
        """Начать новый flow: сбросить FSM, показать клавиатуру геолокации + список населённых пунктов."""
        cfg = self._cfg(mode)
        await state.clear()
        localities = repo.routes.list_localities()
        await state.set_state(cfg["state_group"].start_locality)
        await self._chat_ui.open_flow(
            chat_id=message.chat.id,
            bot=message.bot,
            flow_kind=self._flow_kind(mode),
            text=cfg["entry_text"],
            inline_markup=self._localities_keyboard(cfg["start_locality_prefix"], localities),
            reply_keyboard=self._location_reply_keyboard(),
            reply_hint="📍 Отправь геолокацию — покажем ближайшие остановки посадки. Или выбери город кнопками выше.",
        )

    async def apply_start_locality_from_geo(
        self,
        message: Message,
        state: FSMContext,
        repo: Any,
        mode: str,
        locality: str,
    ) -> None:
        cfg = self._cfg(mode)
        localities = repo.routes.list_localities()
        if locality not in localities:
            await self._chat_ui.update_flow(
                chat_id=message.chat.id,
                bot=message.bot,
                flow_kind=self._flow_kind(mode),
                text="Этого населённого пункта нет в списке маршрутов. Выбери из списка кнопкой.",
                inline_markup=self._localities_keyboard(cfg["start_locality_prefix"], localities),
                reply_keyboard=None,
            )
            return
        await state.update_data(start_locality=locality)
        districts = repo.routes.list_districts(locality)
        await state.set_state(cfg["state_group"].start_district)
        markup = self._districts_keyboard(cfg["start_district_prefix"], districts)
        await self._chat_ui.update_flow(
            chat_id=message.chat.id,
            bot=message.bot,
            flow_kind=self._flow_kind(mode),
            text=f"{locality}: выбери район:",
            inline_markup=markup,
            reply_keyboard=None,
        )

    async def pick_locality(
        self,
        callback: CallbackQuery,
        state: FSMContext,
        repo: Any,
        mode: str,
        is_start: bool,
    ) -> None:
        cfg = self._cfg(mode)
        data_pre = await state.get_data()
        if is_start and callback.message:
            gid = data_pre.get(_GEO_SUGGEST_MESSAGE_KEY)
            await delete_tracked_user_geo_messages(callback.bot, callback.message.chat.id, state)
            if gid is not None:
                try:
                    await callback.bot.delete_message(callback.message.chat.id, int(gid))
                except Exception:
                    pass
                await state.update_data(**{_GEO_SUGGEST_MESSAGE_KEY: None})

        parts = callback.data.split(":", 1)
        if len(parts) < 2:
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return
        try:
            idx = int(parts[1])
        except ValueError:
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return

        if not is_start:
            data_chk = await state.get_data()
            if "start_point" not in data_chk:
                await callback.answer(stale_flow_hint(mode), show_alert=True)
                return

        localities = repo.routes.list_localities()
        try:
            locality = localities[idx]
        except IndexError:
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return

        key = "start_locality" if is_start else "end_locality"
        next_state = cfg["state_group"].start_district if is_start else cfg["state_group"].end_district
        districts_prefix = cfg["start_district_prefix"] if is_start else cfg["end_district_prefix"]
        title_suffix = "" if is_start else " (конечная)"

        await state.update_data(**{key: locality})
        districts = repo.routes.list_districts(locality)
        await state.set_state(next_state)
        await self._update(
            callback,
            mode=mode,
            text=f"{locality}: выбери район{title_suffix}:",
            inline_markup=self._districts_keyboard(districts_prefix, districts),
            reply_keyboard=None if is_start else UNSET,
        )
        await callback.answer()

    async def pick_district(
        self,
        callback: CallbackQuery,
        state: FSMContext,
        repo: Any,
        mode: str,
        is_start: bool,
    ) -> None:
        cfg = self._cfg(mode)
        parts = callback.data.split(":", 1)
        if len(parts) < 2:
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return
        try:
            idx = int(parts[1])
        except ValueError:
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return

        data = await state.get_data()
        locality_key = "start_locality" if is_start else "end_locality"
        if locality_key not in data:
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return

        district_key = "start_district" if is_start else "end_district"
        admin_area_key = "start_admin_area" if is_start else "end_admin_area"
        point_key = "start_point" if is_start else "end_point"
        prefix_admin = cfg["start_admin_prefix"] if is_start else cfg["end_admin_prefix"]
        prefix_stop = cfg["start_stop_prefix"] if is_start else cfg["end_stop_prefix"]

        locality = data[locality_key]
        districts = repo.routes.list_districts(locality)
        try:
            district = districts[idx]
        except IndexError:
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return
        await state.update_data(**{district_key: district})
        admin_areas = repo.routes.list_admin_areas(locality, district)

        if len(admin_areas) > 1:
            merged_stops: list[Any] = []
            for aa in admin_areas:
                merged_stops.extend(repo.routes.list_stops(locality, district, aa))
            if 1 <= len(merged_stops) <= DISTRICT_MERGED_STOPS_MAX:
                merged_stops.sort(key=lambda x: str(x["title"]))
                await state.update_data(merged_stop_pick=True)
                state_stop = cfg["state_group"].start_stop if is_start else cfg["state_group"].end_stop
                await state.set_state(state_stop)
                hdr = f"Остановка {'посадки' if is_start else 'высадки'} ({district}) — все точки района:"
                inline_kb = self._stops_keyboard(merged_stops, prefix_stop)
                await self._update(callback, mode=mode, text=hdr, inline_markup=inline_kb)
                await callback.answer()
                return

            state_value = cfg["state_group"].start_admin_area if is_start else cfg["state_group"].end_admin_area
            await state.set_state(state_value)
            label = district if district else "без района"
            suffix = "" if is_start else " (конечная)"
            await self._update(
                callback,
                mode=mode,
                text=f"{label}: выбери административный район{suffix}:",
                inline_markup=self._districts_keyboard(prefix_admin, admin_areas),
            )
            await callback.answer()
            return

        admin_area = admin_areas[0]
        await state.update_data(**{admin_area_key: admin_area})
        stops = repo.routes.list_stops(locality, district, admin_area)

        if len(stops) > 1:
            state_value = cfg["state_group"].start_stop if is_start else cfg["state_group"].end_stop
            await state.set_state(state_value)
            inline_kb = self._stops_keyboard(stops, prefix_stop)
            await self._update(
                callback,
                mode=mode,
                text=f"Остановка {'посадки' if is_start else 'высадки'} ({admin_area}):",
                inline_markup=inline_kb,
            )
            await callback.answer()
            return

        stop = stops[0]
        await state.update_data(**{point_key: stop["id"]})
        if is_start:
            localities = repo.routes.list_localities()
            await state.set_state(cfg["state_group"].end_locality)
            await self._update(
                callback,
                mode=mode,
                text=(
                    f"Старт: {locality} -> {district} -> {admin_area} -> {stop['title']}.\n"
                    "Теперь выбери конечный населённый пункт:"
                ),
                inline_markup=self._localities_keyboard(cfg["end_locality_prefix"], localities),
            )
        else:
            await state.set_state(cfg["state_group"].trip_date)
            await self._update(
                callback,
                mode=mode,
                text=(
                    f"Конечная: {locality} -> {district} -> {admin_area} -> {stop['title']}.\n"
                    "Выбери дату поездки (календарь):"
                ),
                inline_markup=await self._trip_calendar_factory().start_calendar(),
            )
            await state.update_data(calendar_target=mode)
        await callback.answer()

    async def pick_admin(
        self,
        callback: CallbackQuery,
        state: FSMContext,
        repo: Any,
        mode: str,
        is_start: bool,
    ) -> None:
        cfg = self._cfg(mode)
        parts = callback.data.split(":", 1)
        if len(parts) < 2:
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return
        try:
            idx = int(parts[1])
        except ValueError:
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return

        data = await state.get_data()
        lk = "start_locality" if is_start else "end_locality"
        dk = "start_district" if is_start else "end_district"
        if lk not in data or dk not in data:
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return
        locality = data[lk]
        district = data[dk]
        admin_areas = repo.routes.list_admin_areas(locality, district)
        try:
            admin_area = admin_areas[idx]
        except IndexError:
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return
        await state.update_data(**{("start_admin_area" if is_start else "end_admin_area"): admin_area})
        stops = repo.routes.list_stops(locality, district, admin_area)

        state_value = cfg["state_group"].start_stop if is_start else cfg["state_group"].end_stop
        await state.set_state(state_value)
        prefix = cfg["start_stop_prefix"] if is_start else cfg["end_stop_prefix"]
        await self._update(
            callback,
            mode=mode,
            text=f"Остановка {'посадки' if is_start else 'высадки'} ({admin_area}):",
            inline_markup=self._stops_keyboard(stops, prefix),
        )
        await callback.answer()

    async def pick_start_stop(self, callback: CallbackQuery, state: FSMContext, repo: Any, mode: str) -> None:
        cfg = self._cfg(mode)
        data = await state.get_data()
        required = (
            ("start_locality", "start_district")
            if data.get("merged_stop_pick")
            else (
                "start_locality",
                "start_district",
                "start_admin_area",
            )
        )
        for key in required:
            if key not in data:
                await callback.answer(stale_flow_hint(mode), show_alert=True)
                return

        parts = callback.data.split(":", 1)
        if len(parts) < 2:
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return
        try:
            start_point = int(parts[1])
        except ValueError:
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return

        pt = repo.routes.get_point(start_point)
        loc = str(data["start_locality"])
        dist = str(data["start_district"])
        merged = bool(data.get("merged_stop_pick"))
        admin_need = None if merged else str(data.get("start_admin_area") or "")
        if not _stop_matches_flow_selection(pt, locality=loc, district=dist, admin_area=admin_need):
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return

        extras: dict[str, Any] = {"start_point": start_point}
        if merged:
            if pt:
                extras["start_admin_area"] = str(pt["admin_area"] or "")
            extras["merged_stop_pick"] = False
        await state.update_data(**extras)
        localities = repo.routes.list_localities()
        await state.set_state(cfg["state_group"].end_locality)
        await self._update(
            callback,
            mode=mode,
            text=cfg["end_entry_text"],
            inline_markup=self._localities_keyboard(cfg["end_locality_prefix"], localities),
        )
        await callback.answer()

    async def pick_end_stop(self, callback: CallbackQuery, state: FSMContext, repo: Any, mode: str) -> None:
        cfg = self._cfg(mode)
        data = await state.get_data()
        required = (
            ("start_point", "end_locality", "end_district")
            if data.get("merged_stop_pick")
            else ("start_point", "end_locality", "end_district", "end_admin_area")
        )
        for key in required:
            if key not in data:
                await callback.answer(stale_flow_hint(mode), show_alert=True)
                return

        parts = callback.data.split(":", 1)
        if len(parts) < 2:
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return
        try:
            end_point = int(parts[1])
        except ValueError:
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return

        pt = repo.routes.get_point(end_point)
        loc = str(data["end_locality"])
        dist = str(data["end_district"])
        merged = bool(data.get("merged_stop_pick"))
        admin_need = None if merged else str(data.get("end_admin_area") or "")
        if not _stop_matches_flow_selection(pt, locality=loc, district=dist, admin_area=admin_need):
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return

        extras_end: dict[str, Any] = {"end_point": end_point}
        if merged:
            if pt:
                extras_end["end_admin_area"] = str(pt["admin_area"] or "")
            extras_end["merged_stop_pick"] = False
        await state.update_data(**extras_end)
        await state.set_state(cfg["state_group"].trip_date)
        await self._update(
            callback,
            mode=mode,
            text="Выбери дату поездки (календарь):",
            inline_markup=await self._trip_calendar_factory().start_calendar(),
        )
        await state.update_data(calendar_target=mode)
        await callback.answer()

    async def transition_geo_pick_start_stop(
        self,
        callback: CallbackQuery,
        state: FSMContext,
        repo: Any,
        mode: str,
        start_point: int,
    ) -> None:
        """Принять остановку посадки из геоподсказки (callback gxs:) и перейти к выбору конечной точки.

        Отдельный метод от pick_start_stop, потому что геоподсказка приходит из плавающего сообщения,
        а не из anchor-flow — нужно закрыть его и открыть заново.
        """
        cfg = self._cfg(mode)
        pt = repo.routes.get_point(start_point)
        if pt is None or str(pt["kind"]) != "stop":
            await callback.answer("Остановка не найдена.", show_alert=True)
            return

        data = await state.get_data()
        if callback.message:
            chat_id = callback.message.chat.id
            bot = callback.bot
            await delete_tracked_user_geo_messages(bot, chat_id, state)
            gid_raw = data.get(_GEO_SUGGEST_MESSAGE_KEY)
            if gid_raw is not None:
                try:
                    await bot.delete_message(chat_id, int(gid_raw))
                except Exception:
                    pass

        await state.update_data(
            start_locality=str(pt["locality"]),
            start_district=str(pt["district"] or ""),
            start_admin_area=str(pt["admin_area"] or ""),
            start_point=start_point,
            merged_stop_pick=False,
        )
        await state.update_data(**{_GEO_SUGGEST_MESSAGE_KEY: None})
        localities = repo.routes.list_localities()
        await state.set_state(cfg["state_group"].end_locality)

        if callback.message:
            chat_id = callback.message.chat.id
            bot = callback.bot
            await self._chat_ui.close_flow(chat_id=chat_id, bot=bot)
            await self._chat_ui.open_flow(
                chat_id=chat_id,
                bot=bot,
                flow_kind=self._flow_kind(mode),
                text=cfg["end_entry_text"],
                inline_markup=self._localities_keyboard(cfg["end_locality_prefix"], localities),
                reply_keyboard=None,
            )
        await callback.answer()
