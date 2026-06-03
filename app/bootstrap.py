"""Единая сборка зависимостей для бота (этап 3)."""

from __future__ import annotations

from dataclasses import dataclass

from aiogram import Dispatcher

from app.chat_ui import ChatUiService
from app.config import Settings, load_settings
from app.db import Database
from app.navigation_flow import NavigationFlow
from app.repo import Repo
from app.trip_flow import TripFlowOrchestrator
from app.ui import KeyboardFactory


@dataclass(frozen=True)
class Container:
    """Неизменяемый контейнер DI-зависимостей: создаётся один раз при старте, передаётся во все компоненты."""

    settings: Settings
    db: Database
    repo: Repo
    keyboards: KeyboardFactory
    chat_ui: ChatUiService


def build_container() -> Container:
    """Создать и инициализировать все зависимости бота.

    main_keyboard_provider замыкается на repo, а не принимает его явно, чтобы
    ChatUiService не знал о деталях UserRepository (DIP).
    """
    settings = load_settings()
    db = Database(settings.db_path)
    db.init_schema()
    repo = Repo(db)
    keyboards = KeyboardFactory(settings=settings)

    def main_keyboard_provider(tg_user_id: int):
        user = repo.users.get_user(tg_user_id)
        is_driver = user is not None and user["role"] == "driver"
        return keyboards.main_keyboard(is_driver=is_driver)

    chat_ui = ChatUiService(
        main_keyboard_provider=main_keyboard_provider,
        flow_keyboard_provider=lambda: keyboards.flow_keyboard(),
        database=db,
    )
    return Container(settings=settings, db=db, repo=repo, keyboards=keyboards, chat_ui=chat_ui)


def attach_to_dispatcher(
    dp: Dispatcher,
    container: Container,
    *,
    flow: TripFlowOrchestrator,
    navigation_flow: NavigationFlow,
) -> None:
    """Кладёт зависимости в workflow_data диспетчера (aiogram подмешивает их в kwargs handler'ов)."""
    dp["settings"] = container.settings
    dp["repo"] = container.repo
    dp["keyboards"] = container.keyboards
    dp["chat_ui"] = container.chat_ui
    dp["flow"] = flow
    dp["nav"] = navigation_flow
