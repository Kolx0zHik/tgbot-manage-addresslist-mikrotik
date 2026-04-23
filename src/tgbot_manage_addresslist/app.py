from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from tgbot_manage_addresslist.logic import (
    AddressListManager,
    AddressListService,
    UserAccessResolver,
)
from tgbot_manage_addresslist.mikrotik import MikroTikSSHClient
from tgbot_manage_addresslist.settings import MikroTikSettings, Settings
from tgbot_manage_addresslist.telegram_bot import BotDependencies, register_handlers


logger = logging.getLogger(__name__)


def configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def setup_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Открыть главное меню"),
        ]
    )


async def log_startup_health_checks(
    service: AddressListService,
    mikrotiks: tuple[MikroTikSettings, ...],
) -> None:
    for mikrotik in mikrotiks:
        try:
            address_lists = await service.fetch_address_lists(mikrotik.id)
        except Exception:
            logger.exception(
                "Initial MikroTik SSH check failed for id=%s name=%s",
                mikrotik.id,
                mikrotik.name,
            )
        else:
            logger.info(
                "Initial MikroTik SSH check succeeded for id=%s name=%s found=%s",
                mikrotik.id,
                mikrotik.name,
                len(address_lists),
            )


def build_dependencies(settings: Settings) -> BotDependencies:
    managers_by_id = {
        mikrotik.id: AddressListManager(MikroTikSSHClient(mikrotik))
        for mikrotik in settings.mikrotiks
    }
    return BotDependencies(
        settings=settings,
        address_list_service=AddressListService(managers_by_id),
        user_access_resolver=UserAccessResolver(settings),
    )


async def run() -> None:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher(storage=MemoryStorage())
    deps = build_dependencies(settings)
    register_handlers(dispatcher, deps)
    await setup_bot_commands(bot)

    logger.info("Starting Telegram bot polling")
    await log_startup_health_checks(deps.address_list_service, settings.mikrotiks)

    try:
        await dispatcher.start_polling(bot)
    finally:
        logger.info("Stopping Telegram bot polling")
        await bot.session.close()


def main() -> None:
    asyncio.run(run())
