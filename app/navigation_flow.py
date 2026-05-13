"""Кнопка «Назад» (callback и reply) поверх anchor-API (этап 4)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.chat_ui import UNSET, ChatUiService
from app.flow_mode_cfg import (
    FLOW_MODE_CFG,
    ROUTE_STEP_KEYS,
    STEP_TO_STATE_ATTR,
)


class NavigationFlow:
    """Возврат назад: callback `back:*` и reply «⬅ Назад». Все обновления через `chat_ui.update_flow`."""

    def __init__(
        self,
        *,
        registration_state: Any,
        trip_search_state: Any,
        trip_create_state: Any,
        chat_ui: ChatUiService,
        main_keyboard: Callable[..., Any],
        role_switch_keyboard: Callable[..., Any],
        localities_keyboard: Callable[..., Any],
        districts_keyboard: Callable[..., Any],
        stops_keyboard: Callable[..., Any],
        time_keyboard: Callable[..., Any],
        seats_keyboard: Callable[..., Any],
        trip_calendar_factory: Callable[..., Any],
        mode_cfg: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.registration_state = registration_state
        self.trip_search_state = trip_search_state
        self.trip_create_state = trip_create_state
        self._mode_cfg = mode_cfg if mode_cfg is not None else FLOW_MODE_CFG
        self._chat_ui = chat_ui
        self._main_keyboard = main_keyboard
        self._role_switch_keyboard = role_switch_keyboard
        self._localities_keyboard = localities_keyboard
        self._districts_keyboard = districts_keyboard
        self._stops_keyboard = stops_keyboard
        self._time_keyboard = time_keyboard
        self._seats_keyboard = seats_keyboard
        self._trip_calendar_factory = trip_calendar_factory

    def _trip_groups(self) -> tuple[Any, Any]:
        return self.trip_search_state, self.trip_create_state

    def _parse_route_target(self, target: str) -> tuple[str, str] | None:
        for mode in ("search", "create"):
            prefix = f"{mode}_"
            if target.startswith(prefix):
                rest = target[len(prefix) :]
                if rest in ROUTE_STEP_KEYS:
                    return mode, rest
        return None

    async def _update_callback_flow(
        self,
        callback: Any,
        flow_kind: str,
        text: str,
        inline_markup: Any,
        *,
        reply_keyboard: Any = UNSET,
    ) -> None:
        if not callback.message:
            return
        await self._chat_ui.update_flow(
            chat_id=callback.message.chat.id,
            bot=callback.bot,
            flow_kind=flow_kind,
            text=text,
            inline_markup=inline_markup,
            reply_keyboard=reply_keyboard,
        )

    async def _update_message_flow(
        self,
        message: Any,
        flow_kind: str,
        text: str,
        inline_markup: Any,
        *,
        reply_keyboard: Any = UNSET,
    ) -> None:
        await self._chat_ui.update_flow(
            chat_id=message.chat.id,
            bot=message.bot,
            flow_kind=flow_kind,
            text=text,
            inline_markup=inline_markup,
            reply_keyboard=reply_keyboard,
        )

    async def _route_callback_step(
        self,
        mode: str,
        step: str,
        callback: Any,
        state: Any,
        repo: Any,
    ) -> None:
        cfg = self._mode_cfg[mode]
        sg = cfg["state_group"]
        data = await state.get_data()
        await state.set_state(getattr(sg, STEP_TO_STATE_ATTR[step]))
        flow_kind = mode

        if step == "start_locality":
            locs = repo.routes.list_localities()
            await self._update_callback_flow(
                callback,
                flow_kind,
                cfg["entry_text"],
                self._localities_keyboard(cfg["start_locality_prefix"], locs),
                reply_keyboard=UNSET,
            )
            return

        if step == "start_district":
            locality = data.get("start_locality")
            if not locality:
                return
            districts = repo.routes.list_districts(str(locality))
            await self._update_callback_flow(
                callback,
                flow_kind,
                f"{locality}: выбери район:",
                self._districts_keyboard(cfg["start_district_prefix"], districts),
            )
            return

        if step == "start_admin":
            locality = data.get("start_locality")
            district = data.get("start_district", "")
            if locality is None:
                return
            admin_areas = repo.routes.list_admin_areas(str(locality), str(district))
            await self._update_callback_flow(
                callback,
                flow_kind,
                "Выбери административный район:",
                self._districts_keyboard(cfg["start_admin_prefix"], admin_areas),
            )
            return

        if step == "start_stop":
            locality = data.get("start_locality")
            district = data.get("start_district", "")
            admin_area = data.get("start_admin_area", "")
            if locality is None:
                return
            stops = repo.routes.list_stops(str(locality), str(district), str(admin_area))
            await self._update_callback_flow(
                callback,
                flow_kind,
                "Выбери остановку посадки:",
                self._stops_keyboard(stops, cfg["start_stop_prefix"]),
            )
            return

        if step == "end_locality":
            locs = repo.routes.list_localities()
            await self._update_callback_flow(
                callback,
                flow_kind,
                cfg["end_entry_text"],
                self._localities_keyboard(cfg["end_locality_prefix"], locs),
            )
            return

        if step == "end_district":
            locality = data.get("end_locality")
            if not locality:
                return
            districts = repo.routes.list_districts(str(locality))
            await self._update_callback_flow(
                callback,
                flow_kind,
                f"{locality}: выбери район (конечная):",
                self._districts_keyboard(cfg["end_district_prefix"], districts),
            )
            return

        if step == "end_admin":
            locality = data.get("end_locality")
            district = data.get("end_district", "")
            if locality is None:
                return
            admin_areas = repo.routes.list_admin_areas(str(locality), str(district))
            await self._update_callback_flow(
                callback,
                flow_kind,
                "Выбери административный район (конечная):",
                self._districts_keyboard(cfg["end_admin_prefix"], admin_areas),
            )
            return

        if step == "end_stop":
            locality = data.get("end_locality")
            district = data.get("end_district", "")
            admin_area = data.get("end_admin_area", "")
            if locality is None:
                return
            stops = repo.routes.list_stops(str(locality), str(district), str(admin_area))
            await self._update_callback_flow(
                callback,
                flow_kind,
                "Выбери остановку высадки:",
                self._stops_keyboard(stops, cfg["end_stop_prefix"]),
            )

    async def _go_to_main_menu(self, *, chat_id: int, bot: Any, repo: Any, tg_user_id: int) -> None:
        await self._chat_ui.close_flow(chat_id=chat_id, bot=bot)
        await self._chat_ui.replace_with_notice(
            chat_id=chat_id, bot=bot, text="Главное меню", reply_keyboard=self._main_keyboard(repo, tg_user_id)
        )

    async def handle_callback_back(self, callback: Any, state: Any, repo: Any) -> None:
        target = callback.data.split(":", 1)[1]

        if target == "menu":
            await state.clear()
            if callback.message:
                await self._go_to_main_menu(
                    chat_id=callback.message.chat.id,
                    bot=callback.bot,
                    repo=repo,
                    tg_user_id=callback.from_user.id,
                )
            await callback.answer()
            return

        if target == "switch_role_start":
            user = repo.users.get_user(callback.from_user.id)
            if not user:
                await state.clear()
                if callback.message:
                    await self._go_to_main_menu(
                        chat_id=callback.message.chat.id,
                        bot=callback.bot,
                        repo=repo,
                        tg_user_id=callback.from_user.id,
                    )
                await callback.answer()
                return
            await state.set_state(self.registration_state.waiting_role_switch_date)
            await self._update_callback_flow(
                callback,
                "registration",
                f"Текущая роль: {user['role']}.\nВыбери новую роль:",
                self._role_switch_keyboard(user["role"]),
                reply_keyboard=None,
            )
            await callback.answer()
            return

        parsed = self._parse_route_target(target)
        if parsed:
            mode, step = parsed
            await self._route_callback_step(mode, step, callback, state, repo)
            await callback.answer()
            return

        if target == "create_date":
            await state.set_state(self.trip_create_state.trip_date)
            await self._update_callback_flow(
                callback,
                "create",
                "Выбери дату поездки (календарь):",
                await self._trip_calendar_factory().start_calendar(),
            )
            await state.update_data(calendar_target="create")
            await callback.answer()
            return

        if target == "create_time":
            await state.set_state(self.trip_create_state.departure_time)
            await self._update_callback_flow(
                callback,
                "create",
                "Выбери время отправления:",
                self._time_keyboard("create_time"),
            )
            await callback.answer()
            return

        if target == "create_seats":
            await state.set_state(self.trip_create_state.seats)
            await self._update_callback_flow(
                callback,
                "create",
                "Выбери количество пассажиров:",
                self._seats_keyboard(),
            )
            await callback.answer()
            return

        await callback.answer("Нечего откатывать", show_alert=True)

    async def handle_reply_back(self, message: Any, state: Any, repo: Any) -> None:
        current = await state.get_state()
        data = await state.get_data()
        tg_uid = message.from_user.id if getattr(message, "from_user", None) else 0
        if not current:
            await self._go_to_main_menu(chat_id=message.chat.id, bot=message.bot, repo=repo, tg_user_id=tg_uid)
            return

        cur = str(current)
        is_search = "TripSearch" in cur
        is_create = "TripCreate" in cur
        if not (is_search or is_create):
            await state.clear()
            await self._go_to_main_menu(chat_id=message.chat.id, bot=message.bot, repo=repo, tg_user_id=tg_uid)
            return

        if cur.endswith("start_locality"):
            await state.clear()
            await self._go_to_main_menu(chat_id=message.chat.id, bot=message.bot, repo=repo, tg_user_id=tg_uid)
            return

        cs, cc = self._trip_groups()
        mode = "search" if is_search else "create"
        cfg = self._mode_cfg[mode]
        sg = cs if is_search else cc

        if cur.endswith("start_district"):
            locs = repo.routes.list_localities()
            await state.set_state(sg.start_locality)
            await self._update_message_flow(
                message,
                mode,
                cfg["entry_text"],
                self._localities_keyboard(cfg["start_locality_prefix"], locs),
            )
            return

        if cur.endswith("start_admin_area"):
            locality = data.get("start_locality")
            if locality:
                districts = repo.routes.list_districts(str(locality))
                await state.set_state(sg.start_district)
                await self._update_message_flow(
                    message,
                    mode,
                    f"{locality}: выбери район:",
                    self._districts_keyboard(cfg["start_district_prefix"], districts),
                )
            return

        if cur.endswith("start_stop"):
            locality = data.get("start_locality")
            district = data.get("start_district", "")
            if locality is not None:
                admin_areas = repo.routes.list_admin_areas(str(locality), str(district))
                await state.set_state(sg.start_admin_area)
                await self._update_message_flow(
                    message,
                    mode,
                    "Выбери административный район:",
                    self._districts_keyboard(cfg["start_admin_prefix"], admin_areas),
                )
            return

        if cur.endswith("end_locality"):
            locality = data.get("start_locality")
            district = data.get("start_district", "")
            admin_area = data.get("start_admin_area", "")
            if locality is not None:
                stops = repo.routes.list_stops(str(locality), str(district), str(admin_area))
                await state.set_state(sg.start_stop)
                await self._update_message_flow(
                    message,
                    mode,
                    "Выбери остановку посадки:",
                    self._stops_keyboard(stops, cfg["start_stop_prefix"]),
                )
            return

        if cur.endswith("end_district"):
            locs = repo.routes.list_localities()
            await state.set_state(sg.end_locality)
            await self._update_message_flow(
                message,
                mode,
                cfg["end_entry_text"],
                self._localities_keyboard(cfg["end_locality_prefix"], locs),
            )
            return

        if cur.endswith("end_admin_area"):
            locality = data.get("end_locality")
            if locality:
                districts = repo.routes.list_districts(str(locality))
                await state.set_state(sg.end_district)
                await self._update_message_flow(
                    message,
                    mode,
                    f"{locality}: выбери район (конечная):",
                    self._districts_keyboard(cfg["end_district_prefix"], districts),
                )
            return

        if cur.endswith("end_stop"):
            locality = data.get("end_locality")
            district = data.get("end_district", "")
            if locality is not None:
                admin_areas = repo.routes.list_admin_areas(str(locality), str(district))
                await state.set_state(sg.end_admin_area)
                await self._update_message_flow(
                    message,
                    mode,
                    "Выбери административный район (конечная):",
                    self._districts_keyboard(cfg["end_admin_prefix"], admin_areas),
                )
            return

        if cur.endswith("trip_date"):
            locality = data.get("end_locality")
            district = data.get("end_district", "")
            admin_area = data.get("end_admin_area", "")
            if locality is not None:
                stops = repo.routes.list_stops(str(locality), str(district), str(admin_area))
                await state.set_state(sg.end_stop)
                await self._update_message_flow(
                    message,
                    mode,
                    "Выбери остановку высадки:",
                    self._stops_keyboard(stops, cfg["end_stop_prefix"]),
                )
            return

        if cur.endswith("departure_time"):
            await state.set_state(cc.trip_date)
            await state.update_data(calendar_target="create")
            await self._update_message_flow(
                message,
                "create",
                "Выбери дату поездки (календарь):",
                await self._trip_calendar_factory().start_calendar(),
            )
            return

        if cur.endswith("seats"):
            await state.set_state(cc.departure_time)
            await self._update_message_flow(
                message,
                "create",
                "Выбери время отправления:",
                self._time_keyboard("create_time"),
            )
            return

        if cur.endswith("price"):
            await state.set_state(cc.seats)
            await self._update_message_flow(
                message,
                "create",
                "Выбери количество пассажиров:",
                self._seats_keyboard(),
            )
            return

        await state.clear()
        await self._go_to_main_menu(chat_id=message.chat.id, bot=message.bot, repo=repo, tg_user_id=tg_uid)
