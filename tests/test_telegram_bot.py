from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import SendMessage
from aiogram.types import Chat, Message, Update, User

from tgbot_manage_addresslist.settings import Settings
from tgbot_manage_addresslist.telegram_bot import BotDependencies, register_handlers


class FakeAddressListManager:
    def __init__(self) -> None:
        self.fetch_calls = 0

    async def fetch_address_lists(self) -> list[str]:
        self.fetch_calls += 1
        return ["GERMANY", "OFFICE"]


async def test_ip_message_without_start_command_still_gets_reply(monkeypatch) -> None:
    sent_methods: list[SendMessage] = []

    async def fake_make_request(self, bot, method, timeout=None):  # type: ignore[no-untyped-def]
        sent_methods.append(method)
        return True

    monkeypatch.setattr(AiohttpSession, "make_request", fake_make_request)

    manager = FakeAddressListManager()
    settings = Settings(
        telegram_bot_token="token",
        allowed_telegram_user_ids=(123,),
        mikrotik_host="192.0.2.1",
        mikrotik_port=22,
        mikrotik_username="bot",
        mikrotik_password="secret",
        log_level="INFO",
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    register_handlers(dispatcher, BotDependencies(settings=settings, address_list_manager=manager))
    bot = Bot("42:TEST")

    update = Update(
        update_id=1,
        message=Message(
            message_id=1,
            date=0,
            chat=Chat(id=123, type="private"),
            from_user=User(id=123, is_bot=False, first_name="Test"),
            text="1.1.1.1",
        ),
    )

    await dispatcher.feed_update(bot, update)
    await bot.session.close()

    assert manager.fetch_calls == 1
    assert len(sent_methods) == 1
    assert sent_methods[0].text == "Выберите существующий address-list или создайте новый."
