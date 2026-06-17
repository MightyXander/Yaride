"""Тесты для push_main_menu_after_restart — проверка поведения рассылки меню."""

from __future__ import annotations

import os
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from app.bot_support import push_main_menu_after_restart


class PushMainMenuAfterRestartTests(IsolatedAsyncioTestCase):
    """Тесты для функции push_main_menu_after_restart."""

    async def test_no_push_by_default(self) -> None:
        """По умолчанию (без YARIDE_PUSH_MENU_ON_START) рассылка НЕ происходит."""
        # Убедимся, что env-флаг не установлен
        os.environ.pop("YARIDE_PUSH_MENU_ON_START", None)

        bot = AsyncMock()
        repo = MagicMock()
        repo.users.list_all_tg_user_ids.return_value = [123, 456, 789]

        # Вызываем функцию — при дефолте False ничего не должно отправиться
        await push_main_menu_after_restart(bot, repo)

        # Проверяем, что send_message НЕ вызывался
        bot.send_message.assert_not_called()

    async def test_push_when_enabled(self) -> None:
        """Если YARIDE_PUSH_MENU_ON_START=true, рассылка происходит."""
        os.environ["YARIDE_PUSH_MENU_ON_START"] = "true"

        bot = AsyncMock()
        repo = MagicMock()
        repo.users.list_all_tg_user_ids.return_value = [123, 456]

        with patch("app.bot_support.main_keyboard") as mock_keyboard:
            mock_keyboard.return_value = MagicMock()

            await push_main_menu_after_restart(bot, repo)

            # Проверяем, что send_message вызывался для каждого пользователя
            self.assertEqual(bot.send_message.call_count, 2)

            # Проверяем, что отправлено сообщение с текстом о перезапуске
            call_args = bot.send_message.call_args_list
            for call in call_args:
                args, kwargs = call
                self.assertIn("Бот перезапущен", args[1])

        # Очищаем env после теста
        os.environ.pop("YARIDE_PUSH_MENU_ON_START", None)

    async def test_no_push_when_disabled_explicitly(self) -> None:
        """Если YARIDE_PUSH_MENU_ON_START=false, рассылка НЕ происходит."""
        os.environ["YARIDE_PUSH_MENU_ON_START"] = "false"

        bot = AsyncMock()
        repo = MagicMock()
        repo.users.list_all_tg_user_ids.return_value = [123]

        await push_main_menu_after_restart(bot, repo)

        bot.send_message.assert_not_called()

        # Очищаем env после теста
        os.environ.pop("YARIDE_PUSH_MENU_ON_START", None)
