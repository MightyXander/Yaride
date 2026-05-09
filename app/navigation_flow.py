from __future__ import annotations

from typing import Any, Callable


class NavigationFlow:
    """Handles back navigation for callback and reply buttons."""

    def __init__(
        self,
        registration_state: Any,
        trip_search_state: Any,
        trip_create_state: Any,
        edit_or_send_clean: Callable[..., Any],
        send_flow_step: Callable[..., Any],
        send_clean_message: Callable[..., Any],
        main_keyboard: Callable[..., Any],
        role_switch_keyboard: Callable[..., Any],
        add_back_button: Callable[..., Any],
        localities_keyboard: Callable[..., Any],
        districts_keyboard: Callable[..., Any],
        stops_keyboard: Callable[..., Any],
        time_keyboard: Callable[..., Any],
        seats_keyboard: Callable[..., Any],
        trip_calendar_factory: Callable[..., Any],
    ) -> None:
        self.registration_state = registration_state
        self.trip_search_state = trip_search_state
        self.trip_create_state = trip_create_state
        self._edit_or_send_clean = edit_or_send_clean
        self._send_flow_step = send_flow_step
        self._send_clean_message = send_clean_message
        self._main_keyboard = main_keyboard
        self._role_switch_keyboard = role_switch_keyboard
        self._add_back_button = add_back_button
        self._localities_keyboard = localities_keyboard
        self._districts_keyboard = districts_keyboard
        self._stops_keyboard = stops_keyboard
        self._time_keyboard = time_keyboard
        self._seats_keyboard = seats_keyboard
        self._trip_calendar_factory = trip_calendar_factory

    async def handle_callback_back(self, callback: Any, state: Any, repo: Any) -> None:
        target = callback.data.split(":", 1)[1]
        data = await state.get_data()

        if target == "menu":
            await state.clear()
            await self._edit_or_send_clean(
                callback, "Главное меню", reply_markup=self._main_keyboard(repo, callback.from_user.id)
            )
            await callback.answer()
            return

        if target == "switch_role_start":
            user = repo.get_user(callback.from_user.id)
            if not user:
                await state.clear()
                await self._edit_or_send_clean(
                    callback,
                    "Сначала зарегистрируйся через /start.",
                    reply_markup=self._main_keyboard(repo, callback.from_user.id),
                )
                await callback.answer()
                return
            await state.set_state(self.registration_state.waiting_role_switch_date)
            await self._edit_or_send_clean(
                callback,
                f"Текущая роль: {user['role']}.\nВыбери новую роль:",
                reply_markup=self._role_switch_keyboard(user["role"]),
            )
            await callback.answer()
            return

        if target == "search_start_locality":
            await state.set_state(self.trip_search_state.start_locality)
            locs = repo.list_localities()
            await self._edit_or_send_clean(
                callback,
                "Откуда едем: выбери населённый пункт или город:",
                reply_markup=self._add_back_button(self._localities_keyboard("Sfl", locs), "menu"),
            )
        elif target == "search_start_district":
            locality = data.get("start_locality")
            if locality:
                await state.set_state(self.trip_search_state.start_district)
                districts = repo.list_districts(str(locality))
                await self._edit_or_send_clean(
                    callback,
                    f"{locality}: выбери район:",
                    reply_markup=self._add_back_button(
                        self._districts_keyboard("Sfd", districts),
                        "search_start_locality",
                    ),
                )
        elif target == "search_start_admin":
            locality = data.get("start_locality")
            district = data.get("start_district", "")
            if locality is not None:
                await state.set_state(self.trip_search_state.start_admin_area)
                admin_areas = repo.list_admin_areas(str(locality), str(district))
                await self._edit_or_send_clean(
                    callback,
                    "Выбери административный район:",
                    reply_markup=self._add_back_button(
                        self._districts_keyboard("Sfa", admin_areas),
                        "search_start_district",
                    ),
                )
        elif target == "search_start_stop":
            locality = data.get("start_locality")
            district = data.get("start_district", "")
            admin_area = data.get("start_admin_area", "")
            if locality is not None:
                await state.set_state(self.trip_search_state.start_stop)
                stops = repo.list_stops(str(locality), str(district), str(admin_area))
                await self._edit_or_send_clean(
                    callback,
                    "Выбери остановку посадки:",
                    reply_markup=self._add_back_button(
                        self._stops_keyboard(stops, "Sfp"),
                        "search_start_admin",
                    ),
                )
        elif target == "search_end_locality":
            await state.set_state(self.trip_search_state.end_locality)
            locs = repo.list_localities()
            await self._edit_or_send_clean(
                callback,
                "Куда едем: выбери населённый пункт или город:",
                reply_markup=self._add_back_button(self._localities_keyboard("Stl", locs), "search_start_stop"),
            )
        elif target == "search_end_district":
            locality = data.get("end_locality")
            if locality:
                await state.set_state(self.trip_search_state.end_district)
                districts = repo.list_districts(str(locality))
                await self._edit_or_send_clean(
                    callback,
                    f"{locality}: выбери район (конечная):",
                    reply_markup=self._add_back_button(
                        self._districts_keyboard("Std", districts),
                        "search_end_locality",
                    ),
                )
        elif target == "search_end_admin":
            locality = data.get("end_locality")
            district = data.get("end_district", "")
            if locality is not None:
                await state.set_state(self.trip_search_state.end_admin_area)
                admin_areas = repo.list_admin_areas(str(locality), str(district))
                await self._edit_or_send_clean(
                    callback,
                    "Выбери административный район (конечная):",
                    reply_markup=self._add_back_button(
                        self._districts_keyboard("Sta", admin_areas),
                        "search_end_district",
                    ),
                )
        elif target == "search_end_stop":
            locality = data.get("end_locality")
            district = data.get("end_district", "")
            admin_area = data.get("end_admin_area", "")
            if locality is not None:
                await state.set_state(self.trip_search_state.end_stop)
                stops = repo.list_stops(str(locality), str(district), str(admin_area))
                await self._edit_or_send_clean(
                    callback,
                    "Выбери остановку высадки:",
                    reply_markup=self._add_back_button(
                        self._stops_keyboard(stops, "Stp"),
                        "search_end_admin",
                    ),
                )
        elif target == "create_start_locality":
            await state.set_state(self.trip_create_state.start_locality)
            locs = repo.list_localities()
            await self._edit_or_send_clean(
                callback,
                "Старт поездки: выбери населённый пункт или город:",
                reply_markup=self._add_back_button(self._localities_keyboard("Cfl", locs), "menu"),
            )
        elif target == "create_start_district":
            locality = data.get("start_locality")
            if locality:
                await state.set_state(self.trip_create_state.start_district)
                districts = repo.list_districts(str(locality))
                await self._edit_or_send_clean(
                    callback,
                    f"{locality}: выбери район:",
                    reply_markup=self._add_back_button(
                        self._districts_keyboard("Cfd", districts),
                        "create_start_locality",
                    ),
                )
        elif target == "create_start_admin":
            locality = data.get("start_locality")
            district = data.get("start_district", "")
            if locality is not None:
                await state.set_state(self.trip_create_state.start_admin_area)
                admin_areas = repo.list_admin_areas(str(locality), str(district))
                await self._edit_or_send_clean(
                    callback,
                    "Выбери административный район:",
                    reply_markup=self._add_back_button(
                        self._districts_keyboard("Cfa", admin_areas),
                        "create_start_district",
                    ),
                )
        elif target == "create_start_stop":
            locality = data.get("start_locality")
            district = data.get("start_district", "")
            admin_area = data.get("start_admin_area", "")
            if locality is not None:
                await state.set_state(self.trip_create_state.start_stop)
                stops = repo.list_stops(str(locality), str(district), str(admin_area))
                await self._edit_or_send_clean(
                    callback,
                    "Выбери остановку посадки:",
                    reply_markup=self._add_back_button(
                        self._stops_keyboard(stops, "Cfp"),
                        "create_start_admin",
                    ),
                )
        elif target == "create_end_locality":
            await state.set_state(self.trip_create_state.end_locality)
            locs = repo.list_localities()
            await self._edit_or_send_clean(
                callback,
                "Финиш поездки: выбери населённый пункт или город:",
                reply_markup=self._add_back_button(self._localities_keyboard("Ctl", locs), "create_start_stop"),
            )
        elif target == "create_end_district":
            locality = data.get("end_locality")
            if locality:
                await state.set_state(self.trip_create_state.end_district)
                districts = repo.list_districts(str(locality))
                await self._edit_or_send_clean(
                    callback,
                    f"{locality}: выбери район (конечная):",
                    reply_markup=self._add_back_button(
                        self._districts_keyboard("Ctd", districts),
                        "create_end_locality",
                    ),
                )
        elif target == "create_end_admin":
            locality = data.get("end_locality")
            district = data.get("end_district", "")
            if locality is not None:
                await state.set_state(self.trip_create_state.end_admin_area)
                admin_areas = repo.list_admin_areas(str(locality), str(district))
                await self._edit_or_send_clean(
                    callback,
                    "Выбери административный район (конечная):",
                    reply_markup=self._add_back_button(
                        self._districts_keyboard("Cta", admin_areas),
                        "create_end_district",
                    ),
                )
        elif target == "create_end_stop":
            locality = data.get("end_locality")
            district = data.get("end_district", "")
            admin_area = data.get("end_admin_area", "")
            if locality is not None:
                await state.set_state(self.trip_create_state.end_stop)
                stops = repo.list_stops(str(locality), str(district), str(admin_area))
                await self._edit_or_send_clean(
                    callback,
                    "Выбери остановку высадки:",
                    reply_markup=self._add_back_button(
                        self._stops_keyboard(stops, "Ctp"),
                        "create_end_admin",
                    ),
                )
        elif target == "create_date":
            await state.set_state(self.trip_create_state.trip_date)
            await self._edit_or_send_clean(
                callback,
                "Выбери дату поездки (календарь):",
                reply_markup=self._add_back_button(await self._trip_calendar_factory().start_calendar(), "create_end_stop"),
            )
            await state.update_data(calendar_target="create")
        elif target == "create_time":
            await state.set_state(self.trip_create_state.departure_time)
            await self._edit_or_send_clean(
                callback,
                "Выбери время отправления:",
                reply_markup=self._add_back_button(self._time_keyboard("create_time"), "create_date"),
            )
        elif target == "create_seats":
            await state.set_state(self.trip_create_state.seats)
            await self._edit_or_send_clean(
                callback,
                "Выбери количество пассажиров:",
                reply_markup=self._add_back_button(self._seats_keyboard(), "create_time"),
            )
        else:
            await callback.answer("Нечего откатывать", show_alert=True)
            return

        await callback.answer()

    async def handle_reply_back(self, message: Any, state: Any, repo: Any) -> None:
        current = await state.get_state()
        data = await state.get_data()
        tg_uid = message.from_user.id if getattr(message, "from_user", None) else 0
        if not current:
            await self._send_clean_message(message, "Главное меню", reply_markup=self._main_keyboard(repo, tg_uid))
            return

        is_search = "TripSearch" in current
        is_create = "TripCreate" in current
        if not (is_search or is_create):
            await state.clear()
            await self._send_clean_message(message, "Главное меню", reply_markup=self._main_keyboard(repo, tg_uid))
            return

        if current.endswith("start_locality"):
            await state.clear()
            await self._send_clean_message(message, "Главное меню", reply_markup=self._main_keyboard(repo, tg_uid))
            return

        if current.endswith("start_district"):
            locs = repo.list_localities()
            if is_search:
                await state.set_state(self.trip_search_state.start_locality)
                await self._send_flow_step(
                    message,
                    "Откуда едем: выбери населённый пункт или город:",
                    self._localities_keyboard("Sfl", locs),
                )
            else:
                await state.set_state(self.trip_create_state.start_locality)
                await self._send_flow_step(
                    message,
                    "Старт поездки: выбери населённый пункт или город:",
                    self._localities_keyboard("Cfl", locs),
                )
            return

        if current.endswith("start_admin_area"):
            locality = data.get("start_locality")
            if locality:
                districts = repo.list_districts(str(locality))
                if is_search:
                    await state.set_state(self.trip_search_state.start_district)
                    await self._send_flow_step(message, f"{locality}: выбери район:", self._districts_keyboard("Sfd", districts))
                else:
                    await state.set_state(self.trip_create_state.start_district)
                    await self._send_flow_step(message, f"{locality}: выбери район:", self._districts_keyboard("Cfd", districts))
                return

        if current.endswith("start_stop"):
            locality = data.get("start_locality")
            district = data.get("start_district", "")
            if locality is not None:
                admin_areas = repo.list_admin_areas(str(locality), str(district))
                if is_search:
                    await state.set_state(self.trip_search_state.start_admin_area)
                    await self._send_flow_step(
                        message,
                        "Выбери административный район:",
                        self._districts_keyboard("Sfa", admin_areas),
                    )
                else:
                    await state.set_state(self.trip_create_state.start_admin_area)
                    await self._send_flow_step(
                        message,
                        "Выбери административный район:",
                        self._districts_keyboard("Cfa", admin_areas),
                    )
                return

        if current.endswith("end_locality"):
            locality = data.get("start_locality")
            district = data.get("start_district", "")
            admin_area = data.get("start_admin_area", "")
            if locality is not None:
                stops = repo.list_stops(str(locality), str(district), str(admin_area))
                if is_search:
                    await state.set_state(self.trip_search_state.start_stop)
                    await self._send_flow_step(message, "Выбери остановку посадки:", self._stops_keyboard(stops, "Sfp"))
                else:
                    await state.set_state(self.trip_create_state.start_stop)
                    await self._send_flow_step(message, "Выбери остановку посадки:", self._stops_keyboard(stops, "Cfp"))
            return

        if current.endswith("end_district"):
            locs = repo.list_localities()
            if is_search:
                await state.set_state(self.trip_search_state.end_locality)
                await self._send_flow_step(
                    message,
                    "Куда едем: выбери населённый пункт или город:",
                    self._localities_keyboard("Stl", locs),
                )
            else:
                await state.set_state(self.trip_create_state.end_locality)
                await self._send_flow_step(
                    message,
                    "Финиш поездки: выбери населённый пункт или город:",
                    self._localities_keyboard("Ctl", locs),
                )
                return

        if current.endswith("end_admin_area"):
            locality = data.get("end_locality")
            if locality:
                districts = repo.list_districts(str(locality))
                if is_search:
                    await state.set_state(self.trip_search_state.end_district)
                    await self._send_flow_step(
                        message,
                        f"{locality}: выбери район (конечная):",
                        self._districts_keyboard("Std", districts),
                    )
                else:
                    await state.set_state(self.trip_create_state.end_district)
                    await self._send_flow_step(
                        message,
                        f"{locality}: выбери район (конечная):",
                        self._districts_keyboard("Ctd", districts),
                    )
                return

        if current.endswith("end_stop"):
            locality = data.get("end_locality")
            district = data.get("end_district", "")
            if locality is not None:
                admin_areas = repo.list_admin_areas(str(locality), str(district))
                if is_search:
                    await state.set_state(self.trip_search_state.end_admin_area)
                    await self._send_flow_step(
                        message,
                        "Выбери административный район (конечная):",
                        self._districts_keyboard("Sta", admin_areas),
                    )
                else:
                    await state.set_state(self.trip_create_state.end_admin_area)
                    await self._send_flow_step(
                        message,
                        "Выбери административный район (конечная):",
                        self._districts_keyboard("Cta", admin_areas),
                    )
                return

        if current.endswith("trip_date"):
            locality = data.get("end_locality")
            district = data.get("end_district", "")
            admin_area = data.get("end_admin_area", "")
            if locality is not None:
                stops = repo.list_stops(str(locality), str(district), str(admin_area))
                if is_search:
                    await state.set_state(self.trip_search_state.end_stop)
                    await self._send_flow_step(message, "Выбери остановку высадки:", self._stops_keyboard(stops, "Stp"))
                else:
                    await state.set_state(self.trip_create_state.end_stop)
                    await self._send_flow_step(message, "Выбери остановку высадки:", self._stops_keyboard(stops, "Ctp"))
            return

        if current.endswith("departure_time"):
            await state.set_state(self.trip_create_state.trip_date)
            await state.update_data(calendar_target="create")
            await self._send_flow_step(message, "Выбери дату поездки (календарь):", await self._trip_calendar_factory().start_calendar())
            return

        if current.endswith("seats"):
            await state.set_state(self.trip_create_state.departure_time)
            await self._send_flow_step(message, "Выбери время отправления:", self._time_keyboard("create_time"))
            return

        if current.endswith("price"):
            await state.set_state(self.trip_create_state.seats)
            await self._send_flow_step(message, "Выбери количество пассажиров:", self._seats_keyboard())
            return

        await state.clear()
        await self._send_clean_message(message, "Главное меню", reply_markup=self._main_keyboard(repo, tg_uid))
