"""Этап 4: reply-aux в ChatUiService — служебное сообщение с reply-клавиатурой рядом с anchor."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from app.chat_ui import UNSET, ChatUiService


def _fake_sent(message_id: int):
    return SimpleNamespace(message_id=message_id)


class _StubBot:
    def __init__(self, anchor_id: int = 901, aux_id: int = 902) -> None:
        self._anchor = anchor_id
        self._aux = aux_id
        self.send_message = AsyncMock(side_effect=self._send)
        self.edit_message_text = AsyncMock()
        self.delete_message = AsyncMock()

    async def _send(self, **kwargs):
        if (
            "reply_markup" in kwargs
            and getattr(kwargs.get("reply_markup"), "__class__", type(None)).__name__ == "ReplyKeyboardMarkup"
        ):
            self._aux += 1
            return _fake_sent(self._aux)
        if kwargs.get("reply_markup") is not None and not hasattr(kwargs["reply_markup"], "keyboard"):
            self._anchor += 1
            return _fake_sent(self._anchor)
        self._anchor += 1
        return _fake_sent(self._anchor)


def _service() -> ChatUiService:
    return ChatUiService(
        main_keyboard_provider=lambda _: SimpleNamespace(),
        flow_keyboard_provider=lambda: SimpleNamespace(),
        database=None,
    )


class _ReplyKeyboard:
    keyboard = [["⬅ Назад"]]


class OpenFlowReplyAuxTests(IsolatedAsyncioTestCase):
    async def test_open_flow_with_reply_keyboard_sends_two_messages_and_stores_aux(self) -> None:
        svc = _service()
        rk = _ReplyKeyboard()
        bot = _StubBot()

        anchor_id = await svc.open_flow(chat_id=10, bot=bot, flow_kind="reg", text="hi", reply_keyboard=rk)

        self.assertEqual(bot.send_message.await_count, 2)
        anchor = svc._load_anchor(10)
        self.assertIsNotNone(anchor)
        self.assertEqual(anchor["anchor_message_id"], anchor_id)
        self.assertIsNotNone(anchor["reply_aux_message_id"])

    async def test_open_flow_same_flow_kind_keeps_aux_when_keyboard_replays(self) -> None:
        svc = _service()
        rk = _ReplyKeyboard()
        bot = _StubBot()
        await svc.open_flow(chat_id=10, bot=bot, flow_kind="reg", text="t1", reply_keyboard=rk)
        prev_aux = svc._load_anchor(10)["reply_aux_message_id"]
        bot.send_message.reset_mock()
        bot.delete_message.reset_mock()

        await svc.open_flow(chat_id=10, bot=bot, flow_kind="reg", text="t2", reply_keyboard=rk)

        bot.edit_message_text.assert_awaited_once()
        bot.delete_message.assert_awaited_once()
        bot.send_message.assert_awaited_once()
        new_aux = svc._load_anchor(10)["reply_aux_message_id"]
        self.assertNotEqual(new_aux, prev_aux)


class UpdateFlowReplyAuxTests(IsolatedAsyncioTestCase):
    async def test_update_flow_unset_reply_keyboard_keeps_aux(self) -> None:
        svc = _service()
        rk = _ReplyKeyboard()
        bot = _StubBot()
        await svc.open_flow(chat_id=10, bot=bot, flow_kind="reg", text="t1", reply_keyboard=rk)
        aux_before = svc._load_anchor(10)["reply_aux_message_id"]
        bot.send_message.reset_mock()
        bot.delete_message.reset_mock()

        await svc.update_flow(chat_id=10, bot=bot, flow_kind="reg", text="t2", reply_keyboard=UNSET)

        bot.edit_message_text.assert_awaited_once()
        bot.send_message.assert_not_called()
        bot.delete_message.assert_not_called()
        self.assertEqual(svc._load_anchor(10)["reply_aux_message_id"], aux_before)

    async def test_update_flow_with_none_removes_aux(self) -> None:
        svc = _service()
        rk = _ReplyKeyboard()
        bot = _StubBot()
        await svc.open_flow(chat_id=10, bot=bot, flow_kind="reg", text="t1", reply_keyboard=rk)
        aux_before = svc._load_anchor(10)["reply_aux_message_id"]
        bot.send_message.reset_mock()
        bot.delete_message.reset_mock()

        await svc.update_flow(chat_id=10, bot=bot, flow_kind="reg", text="t2", reply_keyboard=None)

        bot.delete_message.assert_awaited_once_with(10, aux_before)
        bot.send_message.assert_not_called()
        self.assertIsNone(svc._load_anchor(10)["reply_aux_message_id"])


class CloseFlowReplyAuxTests(IsolatedAsyncioTestCase):
    async def test_close_flow_deletes_anchor_and_aux(self) -> None:
        svc = _service()
        rk = _ReplyKeyboard()
        bot = _StubBot()
        await svc.open_flow(chat_id=10, bot=bot, flow_kind="reg", text="t", reply_keyboard=rk)
        anchor = svc._load_anchor(10)
        anchor_id = anchor["anchor_message_id"]
        aux_id = anchor["reply_aux_message_id"]
        bot.delete_message.reset_mock()

        await svc.close_flow(chat_id=10, bot=bot)

        deletes = sorted([c.args[1] for c in bot.delete_message.await_args_list])
        self.assertEqual(deletes, sorted([anchor_id, aux_id]))
        self.assertIsNone(svc._load_anchor(10))


class ReplaceWithNoticeTests(IsolatedAsyncioTestCase):
    async def test_replace_with_notice_after_flow_deletes_old_anchor_and_creates_notice(self) -> None:
        from app.chat_ui import NOTICE_FLOW_KIND

        svc = _service()
        rk = _ReplyKeyboard()
        bot = _StubBot()
        await svc.open_flow(chat_id=10, bot=bot, flow_kind="search", text="search step", reply_keyboard=rk)
        old_anchor = svc._load_anchor(10)
        old_anchor_id = old_anchor["anchor_message_id"]
        bot.send_message.reset_mock()
        bot.delete_message.reset_mock()
        bot.edit_message_text.reset_mock()

        await svc.replace_with_notice(chat_id=10, bot=bot, text="Поездка #1 создана")

        deleted = sorted(c.args[1] for c in bot.delete_message.await_args_list)
        self.assertIn(old_anchor_id, deleted)
        bot.send_message.assert_awaited_once()
        after = svc._load_anchor(10)
        self.assertEqual(after["flow_kind"], NOTICE_FLOW_KIND)

    async def test_two_consecutive_notices_are_edited_in_place(self) -> None:
        svc = _service()
        bot = _StubBot()
        await svc.replace_with_notice(chat_id=10, bot=bot, text="first notice")
        first = svc._load_anchor(10)["anchor_message_id"]
        bot.send_message.reset_mock()
        bot.delete_message.reset_mock()

        await svc.replace_with_notice(chat_id=10, bot=bot, text="second notice")

        bot.edit_message_text.assert_awaited()
        bot.send_message.assert_not_called()
        bot.delete_message.assert_not_called()
        second = svc._load_anchor(10)["anchor_message_id"]
        self.assertEqual(first, second)

    async def test_open_flow_after_notice_deletes_the_notice(self) -> None:
        svc = _service()
        bot = _StubBot()
        await svc.replace_with_notice(chat_id=10, bot=bot, text="Поездка отменена")
        notice_id = svc._load_anchor(10)["anchor_message_id"]
        bot.delete_message.reset_mock()
        bot.send_message.reset_mock()

        await svc.open_flow(chat_id=10, bot=bot, flow_kind="search", text="новый шаг")

        deleted = [c.args[1] for c in bot.delete_message.await_args_list]
        self.assertIn(notice_id, deleted)
        new_anchor = svc._load_anchor(10)
        self.assertEqual(new_anchor["flow_kind"], "search")
        self.assertNotEqual(new_anchor["anchor_message_id"], notice_id)


class DeleteUserMessageTests(IsolatedAsyncioTestCase):
    async def test_delete_user_message_calls_message_delete_and_swallows_errors(self) -> None:
        svc = _service()
        msg = SimpleNamespace(delete=AsyncMock(side_effect=RuntimeError("ignore")))
        await svc.delete_user_message(msg)
        msg.delete.assert_awaited_once()


if __name__ == "__main__":
    import unittest

    unittest.main()
