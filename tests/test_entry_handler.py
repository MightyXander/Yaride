"""Тесты entry handler: /start -> WebApp кнопка, /start trip_<id> -> read-only карточка."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Chat, Message, User

from app.handlers.entry import entry_start
from app.repo import Repo


class EntryHandlerTests(unittest.IsolatedAsyncioTestCase):
    """Тесты на entry handler с deep-link и WebApp кнопкой."""

    async def test_start_without_payload_shows_webapp_button(self) -> None:
        """
        /start без payload -> приветствие + WebApp-кнопка «Открыть приложение».
        """
        message = MagicMock(spec=Message)
        message.from_user = User(id=1, is_bot=False, first_name="Тест")
        message.chat = MagicMock(spec=Chat)
        message.chat.id = 123
        message.bot = MagicMock()

        state = MagicMock(spec=FSMContext)
        state.clear = AsyncMock()

        repo = MagicMock(spec=Repo)
        repo.users = MagicMock()
        repo.users.get_user.return_value = {"name": "Тест", "role": "passenger"}
        repo.users.is_active_driver.return_value = False

        chat_ui = MagicMock()
        chat_ui.delete_user_message = AsyncMock()
        chat_ui.open_flow = AsyncMock()

        keyboards = MagicMock()
        keyboards.webapp_button_keyboard.return_value = MagicMock()

        command = MagicMock(spec=CommandObject)
        command.args = None

        await entry_start(message, state, repo, chat_ui, keyboards, command)

        chat_ui.open_flow.assert_called_once()
        args = chat_ui.open_flow.call_args
        text = args.kwargs["text"]
        self.assertIn("Yaride", text)
        self.assertIn("откройте приложение", text.lower())

    async def test_start_with_trip_payload_shows_readonly_card(self) -> None:
        """
        /start trip_<id> -> read-only карточка поездки + WebApp-кнопка.
        """
        message = MagicMock(spec=Message)
        message.from_user = User(id=1, is_bot=False, first_name="Тест")
        message.chat = MagicMock(spec=Chat)
        message.chat.id = 123
        message.bot = MagicMock()

        state = MagicMock(spec=FSMContext)
        state.clear = AsyncMock()

        trip_row = {
            "id": 42,
            "start_title": "Остановка А",
            "end_title": "Остановка Б",
            "trip_date": "2099-01-01",
            "departure_time": "10:00",
            "time_slot": "2099-01-01 10:00",
            "price_rub": 150,
            "seats_total": 3,
            "seats_booked": 1,
            "status": "open",
            "driver_name": "Иван",
            "driver_rating": 4.5,
            "start_lat": None,
            "start_lng": None,
            "end_lat": None,
            "end_lng": None,
        }

        repo = MagicMock(spec=Repo)
        repo.trips = MagicMock()
        repo.users = MagicMock()
        repo.trips.get_trip_public_card.return_value = trip_row
        repo.users.is_active_driver.return_value = False

        chat_ui = MagicMock()
        chat_ui.delete_user_message = AsyncMock()
        chat_ui.open_flow = AsyncMock()

        keyboards = MagicMock()
        keyboards.webapp_button_keyboard.return_value = MagicMock()

        command = MagicMock(spec=CommandObject)
        command.args = "trip_42"

        await entry_start(message, state, repo, chat_ui, keyboards, command)

        chat_ui.open_flow.assert_called_once()
        args = chat_ui.open_flow.call_args
        text = args.kwargs["text"]
        self.assertIn("Поездка #42", text)
        self.assertIn("Остановка А", text)
        self.assertIn("Остановка Б", text)
        self.assertIn("150 руб", text)
        self.assertIn("для бронирования", text.lower())

    async def test_start_with_invalid_trip_shows_error(self) -> None:
        """
        /start trip_nonexistent -> сообщение «Поездка не найдена».
        """
        message = MagicMock(spec=Message)
        message.from_user = User(id=1, is_bot=False, first_name="Тест")
        message.chat = MagicMock(spec=Chat)
        message.chat.id = 123
        message.bot = MagicMock()

        state = MagicMock(spec=FSMContext)
        state.clear = AsyncMock()

        repo = MagicMock(spec=Repo)
        repo.trips = MagicMock()
        repo.users = MagicMock()
        repo.trips.get_trip_public_card.return_value = None
        repo.users.is_active_driver.return_value = False

        chat_ui = MagicMock()
        chat_ui.delete_user_message = AsyncMock()
        chat_ui.close_flow = AsyncMock()
        chat_ui.replace_with_notice = AsyncMock()

        keyboards = MagicMock()
        keyboards.main_keyboard.return_value = MagicMock()

        command = MagicMock(spec=CommandObject)
        command.args = "trip_999"

        await entry_start(message, state, repo, chat_ui, keyboards, command)

        chat_ui.replace_with_notice.assert_called_once()
        args = chat_ui.replace_with_notice.call_args
        self.assertIn("не найдена", args.kwargs["text"].lower())


if __name__ == "__main__":
    unittest.main()
