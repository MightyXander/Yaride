"""Проверки доступа водителя: роль + статус модерации в админке."""

from __future__ import annotations

import sqlite3

DRIVER_MOD_PENDING = "pending"
DRIVER_MOD_APPROVED = "approved"
DRIVER_MOD_REJECTED = "rejected"

_DRIVER_MOD_VALUES = frozenset({DRIVER_MOD_PENDING, DRIVER_MOD_APPROVED, DRIVER_MOD_REJECTED})


def driver_moderation_status(row: sqlite3.Row | None) -> str:
    if row is None:
        return DRIVER_MOD_APPROVED
    keys = row.keys()
    if "driver_moderation_status" not in keys:
        return DRIVER_MOD_APPROVED
    status = row["driver_moderation_status"]
    return status if status in _DRIVER_MOD_VALUES else DRIVER_MOD_APPROVED


def is_approved_driver(row: sqlite3.Row | None) -> bool:
    return row is not None and row["role"] == "driver" and driver_moderation_status(row) == DRIVER_MOD_APPROVED


def is_pending_driver(row: sqlite3.Row | None) -> bool:
    return row is not None and row["role"] == "driver" and driver_moderation_status(row) == DRIVER_MOD_PENDING


def is_rejected_driver(row: sqlite3.Row | None) -> bool:
    return row is not None and row["role"] == "driver" and driver_moderation_status(row) == DRIVER_MOD_REJECTED


def moderation_status_label(status: str) -> str:
    return {
        DRIVER_MOD_PENDING: "На модерации",
        DRIVER_MOD_APPROVED: "Одобрен",
        DRIVER_MOD_REJECTED: "Отклонён",
    }.get(status, status)
