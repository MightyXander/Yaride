"""Обёртки bot_support вокруг anchor-методов ChatUiService."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock


def _install_fake_container(chat_ui_stub: object) -> None:
    """Заменяет bot_support._c на минимальный контейнер с переданным chat_ui."""
    import app.bot_support as bs

    bs._c = SimpleNamespace(chat_ui=chat_ui_stub)


def _restore_container() -> None:
    import app.bot_support as bs

    bs._c = None


class AnchorWrappersDelegateToChatUi(IsolatedAsyncioTestCase):
    async def asyncTearDown(self) -> None:
        _restore_container()

    async def test_open_flow_delegates_with_keyword_args(self) -> None:
        chat_ui = SimpleNamespace(
            open_flow=AsyncMock(return_value=123),
            update_flow=AsyncMock(return_value=0),
            close_flow=AsyncMock(return_value=None),
        )
        _install_fake_container(chat_ui)

        from app.bot_support import open_flow

        result = await open_flow(
            chat_id=10,
            bot="BOT",
            flow_kind="favorites",
            text="hi",
            inline_markup="KB",
        )

        self.assertEqual(result, 123)
        chat_ui.open_flow.assert_awaited_once()
        call = chat_ui.open_flow.await_args
        self.assertEqual(call.kwargs["chat_id"], 10)
        self.assertEqual(call.kwargs["bot"], "BOT")
        self.assertEqual(call.kwargs["flow_kind"], "favorites")
        self.assertEqual(call.kwargs["text"], "hi")
        self.assertEqual(call.kwargs["inline_markup"], "KB")
        self.assertIsNone(call.kwargs["reply_keyboard"])

    async def test_update_flow_delegates(self) -> None:
        chat_ui = SimpleNamespace(
            open_flow=AsyncMock(return_value=0),
            update_flow=AsyncMock(return_value=77),
            close_flow=AsyncMock(return_value=None),
        )
        _install_fake_container(chat_ui)

        from app.bot_support import update_flow

        result = await update_flow(
            chat_id=10,
            bot="BOT",
            flow_kind="favorites",
            text="step",
            inline_markup=None,
        )

        self.assertEqual(result, 77)
        chat_ui.update_flow.assert_awaited_once()
        call = chat_ui.update_flow.await_args
        self.assertEqual(call.kwargs["chat_id"], 10)
        self.assertEqual(call.kwargs["bot"], "BOT")
        self.assertEqual(call.kwargs["flow_kind"], "favorites")
        self.assertEqual(call.kwargs["text"], "step")
        self.assertIsNone(call.kwargs["inline_markup"])

    async def test_close_flow_delegates(self) -> None:
        chat_ui = SimpleNamespace(
            open_flow=AsyncMock(return_value=0),
            update_flow=AsyncMock(return_value=0),
            close_flow=AsyncMock(return_value=None),
        )
        _install_fake_container(chat_ui)

        from app.bot_support import close_flow

        await close_flow(chat_id=10, bot="BOT", keep_message_id=5)

        chat_ui.close_flow.assert_awaited_once_with(chat_id=10, bot="BOT", keep_message_id=5)
