from __future__ import annotations

from typing import Any, Callable

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message


def stale_flow_hint(mode: str) -> str:
    """Текст для alert при устаревшем шаге поиска или создания поездки."""
    again = "«Найти поездки»" if mode == "search" else "«Создать поездку»"
    return f"Этот шаг устарел (или открыто старое сообщение с кнопками). Начни заново: {again}."


def _stop_matches_flow_selection(
    pt: Any,
    *,
    locality: str,
    district: str,
    admin_area: str | None,
) -> bool:
    """Проверка, что выбранная остановка соответствует выбранному нас. пункту и району (и подрайону, если есть)."""
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
    """Coordinates shared state transitions for search/create trip flows."""

    def __init__(
        self,
        mode_cfg: dict[str, dict[str, Any]],
        send_flow_step: Callable[..., Any],
        edit_or_send_clean: Callable[..., Any],
        add_back_button: Callable[..., Any],
        localities_keyboard: Callable[..., Any],
        districts_keyboard: Callable[..., Any],
        stops_keyboard: Callable[..., Any],
        trip_calendar_factory: Callable[..., Any],
    ) -> None:
        self._mode_cfg = mode_cfg
        self._send_flow_step = send_flow_step
        self._edit_or_send_clean = edit_or_send_clean
        self._add_back_button = add_back_button
        self._localities_keyboard = localities_keyboard
        self._districts_keyboard = districts_keyboard
        self._stops_keyboard = stops_keyboard
        self._trip_calendar_factory = trip_calendar_factory

    def _cfg(self, mode: str) -> dict[str, Any]:
        return self._mode_cfg[mode]

    async def begin(self, message: Message, state: FSMContext, repo: Any, mode: str) -> None:
        cfg = self._cfg(mode)
        await state.clear()
        localities = repo.list_localities()
        await state.set_state(cfg["state_group"].start_locality)
        await self._send_flow_step(
            message,
            cfg["entry_text"],
            self._add_back_button(self._localities_keyboard(cfg["start_locality_prefix"], localities), "menu"),
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

        localities = repo.list_localities()
        try:
            locality = localities[idx]
        except IndexError:
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return

        key = "start_locality" if is_start else "end_locality"
        next_state = cfg["state_group"].start_district if is_start else cfg["state_group"].end_district
        districts_prefix = cfg["start_district_prefix"] if is_start else cfg["end_district_prefix"]
        back_target = cfg["start_locality_back"] if is_start else cfg["end_locality_back"]
        title_suffix = "" if is_start else " (конечная)"

        await state.update_data(**{key: locality})
        districts = repo.list_districts(locality)
        await state.set_state(next_state)
        await self._edit_or_send_clean(
            callback,
            f"{locality}: выбери район{title_suffix}:",
            reply_markup=self._add_back_button(self._districts_keyboard(districts_prefix, districts), back_target),
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
        back_district = cfg["start_district_back"] if is_start else cfg["end_district_back"]
        back_admin = cfg["start_admin_back"] if is_start else cfg["end_admin_back"]

        locality = data[locality_key]
        districts = repo.list_districts(locality)
        try:
            district = districts[idx]
        except IndexError:
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return
        await state.update_data(**{district_key: district})
        admin_areas = repo.list_admin_areas(locality, district)

        if len(admin_areas) > 1:
            merged_stops: list[Any] = []
            for aa in admin_areas:
                merged_stops.extend(repo.list_stops(locality, district, aa))
            if 1 <= len(merged_stops) <= 6:
                merged_stops.sort(key=lambda x: str(x["title"]))
                await state.update_data(merged_stop_pick=True)
                state_stop = cfg["state_group"].start_stop if is_start else cfg["state_group"].end_stop
                await state.set_state(state_stop)
                hdr = f"Остановка {'посадки' if is_start else 'высадки'} ({district}) — все точки района:"
                await self._edit_or_send_clean(
                    callback,
                    hdr,
                    reply_markup=self._stops_keyboard(merged_stops, prefix_stop)
                    if is_start
                    else self._add_back_button(self._stops_keyboard(merged_stops, prefix_stop), back_district),
                )
                await callback.answer()
                return

            state_value = cfg["state_group"].start_admin_area if is_start else cfg["state_group"].end_admin_area
            await state.set_state(state_value)
            label = district if district else "без района"
            suffix = "" if is_start else " (конечная)"
            await self._edit_or_send_clean(
                callback,
                f"{label}: выбери административный район{suffix}:",
                reply_markup=self._add_back_button(self._districts_keyboard(prefix_admin, admin_areas), back_district),
            )
            await callback.answer()
            return

        admin_area = admin_areas[0]
        await state.update_data(**{admin_area_key: admin_area})
        stops = repo.list_stops(locality, district, admin_area)

        if len(stops) > 1:
            state_value = cfg["state_group"].start_stop if is_start else cfg["state_group"].end_stop
            await state.set_state(state_value)
            await self._edit_or_send_clean(
                callback,
                f"Остановка {'посадки' if is_start else 'высадки'} ({admin_area}):",
                reply_markup=self._stops_keyboard(stops, prefix_stop)
                if is_start
                else self._add_back_button(self._stops_keyboard(stops, prefix_stop), back_admin),
            )
            await callback.answer()
            return

        stop = stops[0]
        await state.update_data(**{point_key: stop["id"]})
        if is_start:
            localities = repo.list_localities()
            await state.set_state(cfg["state_group"].end_locality)
            await self._edit_or_send_clean(
                callback,
                f"Старт: {locality} -> {district} -> {admin_area} -> {stop['title']}.\nТеперь выбери конечный населённый пункт:",
                reply_markup=self._localities_keyboard(cfg["end_locality_prefix"], localities),
            )
        else:
            await state.set_state(cfg["state_group"].trip_date)
            await self._edit_or_send_clean(
                callback,
                f"Конечная: {locality} -> {district} -> {admin_area} -> {stop['title']}.\nВыбери дату поездки (календарь):",
                reply_markup=await self._trip_calendar_factory().start_calendar(),
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
        admin_areas = repo.list_admin_areas(locality, district)
        try:
            admin_area = admin_areas[idx]
        except IndexError:
            await callback.answer(stale_flow_hint(mode), show_alert=True)
            return
        await state.update_data(**{("start_admin_area" if is_start else "end_admin_area"): admin_area})
        stops = repo.list_stops(locality, district, admin_area)

        state_value = cfg["state_group"].start_stop if is_start else cfg["state_group"].end_stop
        await state.set_state(state_value)
        prefix = cfg["start_stop_prefix"] if is_start else cfg["end_stop_prefix"]
        back = cfg["start_admin_back"] if is_start else cfg["end_admin_back"]
        await self._edit_or_send_clean(
            callback,
            f"Остановка {'посадки' if is_start else 'высадки'} ({admin_area}):",
            reply_markup=self._add_back_button(self._stops_keyboard(stops, prefix), back),
        )
        await callback.answer()

    async def pick_start_stop(self, callback: CallbackQuery, state: FSMContext, repo: Any, mode: str) -> None:
        cfg = self._cfg(mode)
        data = await state.get_data()
        if data.get("merged_stop_pick"):
            for key in ("start_locality", "start_district"):
                if key not in data:
                    await callback.answer(stale_flow_hint(mode), show_alert=True)
                    return
        else:
            for key in ("start_locality", "start_district", "start_admin_area"):
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

        pt = repo.get_point(start_point)
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
        localities = repo.list_localities()
        await state.set_state(cfg["state_group"].end_locality)
        await self._edit_or_send_clean(
            callback,
            cfg["end_entry_text"],
            reply_markup=self._add_back_button(
                self._localities_keyboard(cfg["end_locality_prefix"], localities),
                cfg["start_stop_back"],
            ),
        )
        await callback.answer()

    async def pick_end_stop(self, callback: CallbackQuery, state: FSMContext, repo: Any, mode: str) -> None:
        cfg = self._cfg(mode)
        data = await state.get_data()
        if data.get("merged_stop_pick"):
            for key in ("start_point", "end_locality", "end_district"):
                if key not in data:
                    await callback.answer(stale_flow_hint(mode), show_alert=True)
                    return
        else:
            for key in ("start_point", "end_locality", "end_district", "end_admin_area"):
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

        pt = repo.get_point(end_point)
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
        await self._edit_or_send_clean(
            callback,
            "Выбери дату поездки (календарь):",
            reply_markup=self._add_back_button(
                await self._trip_calendar_factory().start_calendar(),
                cfg["end_stop_back"],
            ),
        )
        await state.update_data(calendar_target=mode)
        await callback.answer()
