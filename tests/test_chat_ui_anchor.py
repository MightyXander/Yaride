"""Anchor-методы ChatUiService (этап 4): open_flow / update_flow / close_flow.

Тесты не трогают существующие `send_flow_step` / `send_clean_message` / `cleanup_chat` —
старая модель «полной чистки» сохранена и работает как раньше до миграции handler'ов.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import EditMessageText

from app.chat_ui import ChatUiService
from app.db import Database


def _make_bot(*, send_returns: int = 100) -> SimpleNamespace:
    bot = SimpleNamespace()
    bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=send_returns))
    bot.edit_message_text = AsyncMock(return_value=SimpleNamespace(message_id=send_returns))
    bot.delete_message = AsyncMock(return_value=True)
    return bot


def _make_service(db: Database | None = None) -> ChatUiService:
    return ChatUiService(
        main_keyboard_provider=lambda _uid: "MAIN",
        flow_keyboard_provider=lambda: "FLOW",
        database=db,
    )


class OpenFlowTests(IsolatedAsyncioTestCase):
    async def test_open_flow_without_anchor_sends_new_message(self) -> None:
        svc = _make_service()
        bot = _make_bot(send_returns=42)

        mid = await svc.open_flow(chat_id=10, bot=bot, flow_kind="search", text="hi")

        self.assertEqual(mid, 42)
        bot.send_message.assert_awaited_once()
        bot.edit_message_text.assert_not_awaited()
        bot.delete_message.assert_not_awaited()

    async def test_open_flow_with_same_flow_kind_edits_anchor(self) -> None:
        svc = _make_service()
        bot = _make_bot(send_returns=42)

        await svc.open_flow(chat_id=10, bot=bot, flow_kind="search", text="step1")
        bot.send_message.reset_mock()

        mid = await svc.open_flow(chat_id=10, bot=bot, flow_kind="search", text="step2")

        self.assertEqual(mid, 42)
        bot.edit_message_text.assert_awaited_once()
        bot.send_message.assert_not_awaited()
        bot.delete_message.assert_not_awaited()

    async def test_open_flow_with_different_flow_kind_deletes_and_recreates(self) -> None:
        svc = _make_service()
        bot = _make_bot(send_returns=42)
        await svc.open_flow(chat_id=10, bot=bot, flow_kind="search", text="step1")

        bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=99))
        bot.delete_message.reset_mock()
        bot.edit_message_text.reset_mock()

        mid = await svc.open_flow(chat_id=10, bot=bot, flow_kind="create", text="another")

        self.assertEqual(mid, 99)
        bot.delete_message.assert_awaited_once_with(10, 42)
        bot.send_message.assert_awaited_once()
        bot.edit_message_text.assert_not_awaited()


class UpdateFlowTests(IsolatedAsyncioTestCase):
    async def test_update_flow_with_anchor_edits(self) -> None:
        svc = _make_service()
        bot = _make_bot(send_returns=42)
        await svc.open_flow(chat_id=10, bot=bot, flow_kind="search", text="step1")
        bot.send_message.reset_mock()

        await svc.update_flow(chat_id=10, bot=bot, flow_kind="search", text="step2")

        bot.edit_message_text.assert_awaited_once()
        bot.send_message.assert_not_awaited()

    async def test_update_flow_without_anchor_sends_new(self) -> None:
        svc = _make_service()
        bot = _make_bot(send_returns=42)

        await svc.update_flow(chat_id=10, bot=bot, flow_kind="search", text="step1")

        bot.send_message.assert_awaited_once()
        bot.edit_message_text.assert_not_awaited()

    async def test_update_flow_falls_back_to_send_when_edit_raises_bad_request(self) -> None:
        svc = _make_service()
        bot = _make_bot(send_returns=42)
        await svc.open_flow(chat_id=10, bot=bot, flow_kind="search", text="step1")
        bot.send_message.reset_mock()

        bot.edit_message_text = AsyncMock(
            side_effect=TelegramBadRequest(
                method=EditMessageText(chat_id=10, message_id=42, text="x"),
                message="message to edit not found",
            ),
        )
        bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=77))

        await svc.update_flow(chat_id=10, bot=bot, flow_kind="search", text="retry")

        bot.send_message.assert_awaited_once()


class CloseFlowTests(IsolatedAsyncioTestCase):
    async def test_close_flow_with_anchor_deletes_message(self) -> None:
        svc = _make_service()
        bot = _make_bot(send_returns=42)
        await svc.open_flow(chat_id=10, bot=bot, flow_kind="search", text="step1")
        bot.delete_message.reset_mock()

        await svc.close_flow(chat_id=10, bot=bot)

        bot.delete_message.assert_awaited_once_with(10, 42)

    async def test_close_flow_without_anchor_is_noop(self) -> None:
        svc = _make_service()
        bot = _make_bot(send_returns=42)

        await svc.close_flow(chat_id=10, bot=bot)

        bot.delete_message.assert_not_awaited()

    async def test_close_flow_with_keep_message_id_does_not_delete_kept(self) -> None:
        svc = _make_service()
        bot = _make_bot(send_returns=42)
        await svc.open_flow(chat_id=10, bot=bot, flow_kind="search", text="step1")
        bot.delete_message.reset_mock()

        await svc.close_flow(chat_id=10, bot=bot, keep_message_id=42)

        bot.delete_message.assert_not_awaited()

        bot.send_message.reset_mock()
        bot.edit_message_text.reset_mock()
        await svc.open_flow(chat_id=10, bot=bot, flow_kind="search", text="new1")
        bot.send_message.assert_awaited_once()


class AnchorPersistenceTests(IsolatedAsyncioTestCase):
    async def test_anchor_survives_service_restart_when_database_attached(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "anchor.db"
            db = Database(str(db_path))
            try:
                db.init_schema()

                svc1 = _make_service(db=db)
                bot = _make_bot(send_returns=42)
                await svc1.open_flow(chat_id=10, bot=bot, flow_kind="search", text="step1")

                svc2 = _make_service(db=db)
                bot.send_message.reset_mock()
                bot.edit_message_text.reset_mock()

                await svc2.update_flow(chat_id=10, bot=bot, flow_kind="search", text="step2")

                bot.edit_message_text.assert_awaited_once()
                bot.send_message.assert_not_awaited()
            finally:
                db.close()
