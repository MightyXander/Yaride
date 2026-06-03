"""Точка входа Telegram-бота: сборка контейнера, роутеры, polling."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.bootstrap import attach_to_dispatcher, build_container
from app.bot_support import configure, push_main_menu_after_restart
from app.handlers.account import router as account_router
from app.handlers.booking import router as booking_router
from app.handlers.calendar import router as calendar_router
from app.handlers.driver_manage import router as driver_manage_router
from app.handlers.fallback import router as fallback_router
from app.handlers.favorites import router as favorites_router
from app.handlers.geo import router as geo_router
from app.handlers.rating import router as rating_router
from app.handlers.registration import router as registration_router
from app.handlers.trip_create import router as trip_create_router
from app.handlers.trip_search import router as trip_search_router
from app.middlewares import BanMiddleware
from app.rating_worker import process_pending_rating_prompts

logger = logging.getLogger(__name__)

router = Router()
router.include_router(registration_router)
router.include_router(account_router)
router.include_router(favorites_router)
router.include_router(trip_search_router)
router.include_router(trip_create_router)
router.include_router(booking_router)
router.include_router(driver_manage_router)
router.include_router(rating_router)
router.include_router(geo_router)
router.include_router(calendar_router)
router.include_router(fallback_router)


async def run() -> None:
    """Точка запуска бота: сборка зависимостей, регистрация роутеров, запуск polling и фоновых задач."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s [%(filename)s:%(lineno)d] %(message)s",
    )
    container = build_container()
    flow, nav = configure(container)
    settings = container.settings
    repo = container.repo

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    attach_to_dispatcher(dp, container, flow=flow, navigation_flow=nav)
    # Бан проверяем до любых хендлеров — забаненный апдейт дальше не проходит.
    dp.update.outer_middleware(BanMiddleware(repo))
    dp.include_router(router)

    # drop_pending_updates=True — сбрасываем накопившиеся апдейты при рестарте,
    # чтобы не обрабатывать устаревшие callback'и с предыдущей сессии.
    await bot.delete_webhook(drop_pending_updates=True)

    async def rating_prompt_loop() -> None:
        """Периодически рассылает запросы оценок после завершённых поездок.

        Начальная задержка нужна, чтобы бот успел полностью инициализироваться перед первым обходом.
        """
        try:
            await asyncio.sleep(settings.rating_prompt_initial_delay_s)
            while True:
                try:
                    await process_pending_rating_prompts(bot, repo)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("rating_prompt_loop")
                try:
                    await asyncio.sleep(settings.rating_prompt_interval_s)
                except asyncio.CancelledError:
                    raise
        except asyncio.CancelledError:
            pass

    background_tasks: set[asyncio.Task[None]] = set()

    def _spawn(coro):
        """Запустить фоновую корутину с отслеживанием — чтобы корректно отменить при завершении."""
        task = asyncio.create_task(coro)
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)
        return task

    _spawn(rating_prompt_loop())
    _spawn(push_main_menu_after_restart(bot, repo))

    try:
        await dp.start_polling(bot)
    finally:
        for t in list(background_tasks):
            t.cancel()
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)
        await bot.session.close()
        container.db.close()
