"""Единый конфиг режимов search/create для TripFlowOrchestrator и NavigationFlow."""

from __future__ import annotations

from app.states import TripCreate, TripSearch

FLOW_MODE_CFG = {
    "search": {
        "state_group": TripSearch,
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
        "entry_text": "Откуда едем: выбери район посадки:",
        "end_entry_text": "Куда едем: выбери район высадки:",
    },
    "create": {
        "state_group": TripCreate,
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
        "entry_text": "Старт поездки: выбери район посадки:",
        "end_entry_text": "Финиш поездки: выбери район высадки:",
    },
}

# Шаги маршрута в callback target: {mode}_{step_key}
ROUTE_STEP_KEYS = (
    "start_locality",
    "start_district",
    "start_admin",
    "start_stop",
    "end_locality",
    "end_district",
    "end_admin",
    "end_stop",
)

# Имя атрибута StatesGroup для шага (start_admin в callback → start_admin_area в FSM)
STEP_TO_STATE_ATTR = {
    "start_locality": "start_locality",
    "start_district": "start_district",
    "start_admin": "start_admin_area",
    "start_stop": "start_stop",
    "end_locality": "end_locality",
    "end_district": "end_district",
    "end_admin": "end_admin_area",
    "end_stop": "end_stop",
}

# Ключ в FLOW_MODE_CFG[mode] для родительского callback «Назад».
# После удаления шага выбора города: start_district — первый шаг, end_district идёт сразу после start_stop.
STEP_PARENT_CFG_KEY = {
    "start_locality": None,
    "start_district": None,
    "start_admin": "start_district_back",
    "start_stop": "start_admin_back",
    "end_locality": None,
    "end_district": "start_stop_back",
    "end_admin": "end_district_back",
    "end_stop": "end_admin_back",
}
