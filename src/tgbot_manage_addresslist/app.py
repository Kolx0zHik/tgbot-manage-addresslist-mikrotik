from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from tgbot_manage_addresslist.logic import AddressListManager
from tgbot_manage_addresslist.mikrotik import MikroTikSSHClient
from tgbot_manage_addresslist.settings import Settings
from tgbot_manage_addresslist.telegram_bot import BotDependencies, register_handlers


async def run() -> None:
    settings = Settings.from_env()
    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher(storage=MemoryStorage())
    manager = AddressListManager(MikroTikSSHClient(settings))
    deps = BotDependencies(settings=settings, address_list_manager=manager)
    register_handlers(dispatcher, deps)

    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


def main() -> None:
    asyncio.run(run())
