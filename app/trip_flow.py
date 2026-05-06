from __future__ import annotations

from typing import Any, Callable

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message


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
        idx = int(callback.data.split(":")[1])
        localities = repo.list_localities()
        locality = localities[idx]
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
        idx = int(callback.data.split(":")[1])
        data = await state.get_data()

        locality_key = "start_locality" if is_start else "end_locality"
        district_key = "start_district" if is_start else "end_district"
        admin_area_key = "start_admin_area" if is_start else "end_admin_area"
        point_key = "start_point" if is_start else "end_point"
        prefix_admin = cfg["start_admin_prefix"] if is_start else cfg["end_admin_prefix"]
        prefix_stop = cfg["start_stop_prefix"] if is_start else cfg["end_stop_prefix"]
        back_district = cfg["start_district_back"] if is_start else cfg["end_district_back"]
        back_admin = cfg["start_admin_back"] if is_start else cfg["end_admin_back"]

        locality = data[locality_key]
        districts = repo.list_districts(locality)
        district = districts[idx]
        await state.update_data(**{district_key: district})
        admin_areas = repo.list_admin_areas(locality, district)

        if len(admin_areas) > 1:
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
        idx = int(callback.data.split(":")[1])
        data = await state.get_data()
        locality = data["start_locality" if is_start else "end_locality"]
        district = data["start_district" if is_start else "end_district"]
        admin_areas = repo.list_admin_areas(locality, district)
        admin_area = admin_areas[idx]
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
        start_point = int(callback.data.split(":")[1])
        await state.update_data(start_point=start_point)
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

    async def pick_end_stop(self, callback: CallbackQuery, state: FSMContext, mode: str) -> None:
        cfg = self._cfg(mode)
        end_point = int(callback.data.split(":")[1])
        await state.update_data(end_point=end_point)
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
