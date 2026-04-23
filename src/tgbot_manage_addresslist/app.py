from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from tgbot_manage_addresslist.logic import AddressListManager
from tgbot_manage_addresslist.mikrotik import MikroTikSSHClient
from tgbot_manage_addresslist.settings import Settings
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
            BotCommand(command="start", description="Открыть меню"),
            BotCommand(command="delete_list", description="Удалить address-list"),
            BotCommand(command="cancel", description="Отменить сценарий"),
            BotCommand(command="help", description="Показать помощь"),
        ]
    )


async def run() -> None:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher(storage=MemoryStorage())
    manager = AddressListManager(MikroTikSSHClient(settings))
    deps = BotDependencies(settings=settings, address_list_manager=manager)
    register_handlers(dispatcher, deps)
    await setup_bot_commands(bot)

    logger.info("Starting Telegram bot polling")
    try:
        address_lists = await manager.fetch_address_lists()
    except Exception:
        logger.exception("Initial MikroTik SSH check failed")
    else:
        logger.info("Initial MikroTik SSH check succeeded, found %s address-lists", len(address_lists))

    try:
        await dispatcher.start_polling(bot)
    finally:
        logger.info("Stopping Telegram bot polling")
        await bot.session.close()


def main() -> None:
    asyncio.run(run())
