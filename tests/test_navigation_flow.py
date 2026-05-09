from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from app.navigation_flow import NavigationFlow


class _FakeState:
    def __init__(self) -> None:
        self.data: dict[str, object] = {}
        self.current = None
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True
        self.data.clear()
        self.current = None

    async def set_state(self, state) -> None:
        self.current = state

    async def get_state(self):
        return self.current

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def get_data(self):
        return dict(self.data)


class _FakeCallback:
    def __init__(self, data: str, tg_user_id: int = 1) -> None:
        self.data = data
        self.from_user = SimpleNamespace(id=tg_user_id)
        self.answer = AsyncMock()


class _FakeRepo:
    def get_user(self, _tg_user_id):
        return {"role": "driver"}

    def list_localities(self):
        return ["X"]

    def list_districts(self, _locality):
        return ["D"]

    def list_admin_areas(self, _locality, _district):
        return ["A"]

    def list_stops(self, _locality, _district, _admin):
        return [{"id": 1, "title": "S"}]


class _FakeCalendar:
    async def start_calendar(self):
        return "CAL"


class NavigationFlowTests(IsolatedAsyncioTestCase):
    def _build(self):
        edit_or_send_clean = AsyncMock()
        send_flow_step = AsyncMock()
        send_clean_message = AsyncMock()
        flow = NavigationFlow(
            registration_state=SimpleNamespace(waiting_role_switch_date="waiting_role_switch_date"),
            trip_search_state=SimpleNamespace(
                start_locality="search_start_locality",
                start_district="search_start_district",
                start_admin_area="search_start_admin_area",
                start_stop="search_start_stop",
                end_locality="search_end_locality",
                end_district="search_end_district",
                end_admin_area="search_end_admin_area",
                end_stop="search_end_stop",
            ),
            trip_create_state=SimpleNamespace(
                start_locality="create_start_locality",
                start_district="create_start_district",
                start_admin_area="create_start_admin_area",
                start_stop="create_start_stop",
                end_locality="create_end_locality",
                end_district="create_end_district",
                end_admin_area="create_end_admin_area",
                end_stop="create_end_stop",
                trip_date="create_trip_date",
                departure_time="create_departure_time",
                seats="create_seats",
            ),
            edit_or_send_clean=edit_or_send_clean,
            send_flow_step=send_flow_step,
            send_clean_message=send_clean_message,
            main_keyboard=lambda repo, uid: "MAIN",
            role_switch_keyboard=lambda role: f"ROLE:{role}",
            add_back_button=lambda markup, back: ("BACK", markup, back),
            localities_keyboard=lambda prefix, items: ("LOC", prefix, tuple(items)),
            districts_keyboard=lambda prefix, items: ("DIST", prefix, tuple(items)),
            stops_keyboard=lambda stops, prefix: ("STOP", prefix, tuple(stops)),
            time_keyboard=lambda prefix: ("TIME", prefix),
            seats_keyboard=lambda: "SEATS",
            trip_calendar_factory=lambda: _FakeCalendar(),
        )
        return flow, edit_or_send_clean, send_flow_step, send_clean_message

    async def test_callback_menu_goes_to_main_menu(self):
        flow, edit_or_send_clean, _, _ = self._build()
        state = _FakeState()
        callback = _FakeCallback("back:menu")

        await flow.handle_callback_back(callback, state, _FakeRepo())

        self.assertTrue(state.cleared)
        callback.answer.assert_awaited_once()
        self.assertEqual(edit_or_send_clean.await_args.args[1], "Главное меню")

    async def test_reply_back_without_state_opens_main_menu(self):
        flow, _, _, send_clean_message = self._build()
        state = _FakeState()

        fake_msg = SimpleNamespace(from_user=SimpleNamespace(id=1))
        await flow.handle_reply_back(fake_msg, state, _FakeRepo())

        send_clean_message.assert_awaited_once()
        self.assertEqual(send_clean_message.await_args.args[1], "Главное меню")
