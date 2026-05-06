from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from app.trip_flow import TripFlowOrchestrator


class _FakeState:
    def __init__(self) -> None:
        self.data: dict[str, object] = {}
        self.last_state = None
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True
        self.data.clear()

    async def set_state(self, state) -> None:
        self.last_state = state

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def get_data(self) -> dict[str, object]:
        return dict(self.data)


class _FakeCalendar:
    async def start_calendar(self):
        return "CALENDAR_MARKUP"


class _FakeCallback:
    def __init__(self, data: str) -> None:
        self.data = data
        self.answer = AsyncMock()


class _FakeRepo:
    def __init__(self) -> None:
        self._localities = ["A", "B"]
        self._districts = ["D1"]

    def list_localities(self):
        return list(self._localities)

    def list_districts(self, _locality):
        return list(self._districts)

    def list_admin_areas(self, _locality, _district):
        return ["Center"]

    def list_stops(self, _locality, _district, _admin_area):
        return [{"id": 10, "title": "Stop"}]


class TripFlowOrchestratorTests(IsolatedAsyncioTestCase):
    def _build_orchestrator(self):
        send_flow_step = AsyncMock()
        edit_or_send_clean = AsyncMock()
        mode_cfg = {
            "search": {
                "state_group": SimpleNamespace(
                    start_locality="search_start_locality",
                    start_district="search_start_district",
                    start_admin_area="search_start_admin_area",
                    start_stop="search_start_stop",
                    end_locality="search_end_locality",
                    end_district="search_end_district",
                    end_admin_area="search_end_admin_area",
                    end_stop="search_end_stop",
                    trip_date="search_trip_date",
                ),
                "start_locality_prefix": "Sfl",
                "start_district_prefix": "Sfd",
                "start_admin_prefix": "Sfa",
                "start_stop_prefix": "Sfp",
                "end_locality_prefix": "Stl",
                "end_district_prefix": "Std",
                "end_admin_prefix": "Sta",
                "end_stop_prefix": "Stp",
                "start_locality_back": "search_start_locality",
                "start_district_back": "search_start_district",
                "start_admin_back": "search_start_admin",
                "start_stop_back": "search_start_stop",
                "end_locality_back": "search_end_locality",
                "end_district_back": "search_end_district",
                "end_admin_back": "search_end_admin",
                "end_stop_back": "search_end_stop",
                "entry_text": "ENTRY_SEARCH",
                "end_entry_text": "END_ENTRY_SEARCH",
            },
            "create": {
                "state_group": SimpleNamespace(
                    start_locality="create_start_locality",
                    start_district="create_start_district",
                    start_admin_area="create_start_admin_area",
                    start_stop="create_start_stop",
                    end_locality="create_end_locality",
                    end_district="create_end_district",
                    end_admin_area="create_end_admin_area",
                    end_stop="create_end_stop",
                    trip_date="create_trip_date",
                ),
                "start_locality_prefix": "Cfl",
                "start_district_prefix": "Cfd",
                "start_admin_prefix": "Cfa",
                "start_stop_prefix": "Cfp",
                "end_locality_prefix": "Ctl",
                "end_district_prefix": "Ctd",
                "end_admin_prefix": "Cta",
                "end_stop_prefix": "Ctp",
                "start_locality_back": "create_start_locality",
                "start_district_back": "create_start_district",
                "start_admin_back": "create_start_admin",
                "start_stop_back": "create_start_stop",
                "end_locality_back": "create_end_locality",
                "end_district_back": "create_end_district",
                "end_admin_back": "create_end_admin",
                "end_stop_back": "create_end_stop",
                "entry_text": "ENTRY_CREATE",
                "end_entry_text": "END_ENTRY_CREATE",
            },
        }
        orchestrator = TripFlowOrchestrator(
            mode_cfg=mode_cfg,
            send_flow_step=send_flow_step,
            edit_or_send_clean=edit_or_send_clean,
            add_back_button=lambda markup, back: ("BACK", markup, back),
            localities_keyboard=lambda prefix, localities: ("LOC", prefix, tuple(localities)),
            districts_keyboard=lambda prefix, districts: ("DIST", prefix, tuple(districts)),
            stops_keyboard=lambda stops, prefix: ("STOP", prefix, tuple((s["id"], s["title"]) for s in stops)),
            trip_calendar_factory=lambda: _FakeCalendar(),
        )
        return orchestrator, send_flow_step, edit_or_send_clean

    async def test_begin_sets_start_state_and_renders_entry(self) -> None:
        orchestrator, send_flow_step, _ = self._build_orchestrator()
        state = _FakeState()
        repo = _FakeRepo()

        await orchestrator.begin(message=object(), state=state, repo=repo, mode="search")

        self.assertTrue(state.cleared)
        self.assertEqual(state.last_state, "search_start_locality")
        send_flow_step.assert_awaited_once()
        self.assertEqual(send_flow_step.await_args.args[1], "ENTRY_SEARCH")

    async def test_pick_locality_updates_end_state(self) -> None:
        orchestrator, _, edit_or_send_clean = self._build_orchestrator()
        state = _FakeState()
        callback = _FakeCallback("Stl:1")
        repo = _FakeRepo()

        await orchestrator.pick_locality(callback=callback, state=state, repo=repo, mode="search", is_start=False)

        self.assertEqual(state.data["end_locality"], "B")
        self.assertEqual(state.last_state, "search_end_district")
        callback.answer.assert_awaited_once()
        self.assertIn("(конечная)", edit_or_send_clean.await_args.args[1])

    async def test_pick_end_stop_sets_trip_date_and_calendar_target(self) -> None:
        orchestrator, _, edit_or_send_clean = self._build_orchestrator()
        state = _FakeState()
        callback = _FakeCallback("Ctp:77")

        await orchestrator.pick_end_stop(callback=callback, state=state, mode="create")

        self.assertEqual(state.data["end_point"], 77)
        self.assertEqual(state.data["calendar_target"], "create")
        self.assertEqual(state.last_state, "create_trip_date")
        callback.answer.assert_awaited_once()
        self.assertEqual(edit_or_send_clean.await_args.kwargs["reply_markup"][2], "create_end_stop")
