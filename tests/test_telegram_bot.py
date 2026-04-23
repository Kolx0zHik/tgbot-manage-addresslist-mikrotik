from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.methods import GetMe, SetMyCommands
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import SendMessage
from aiogram.types import Chat, Message, Update, User

from tgbot_manage_addresslist.app import setup_bot_commands
from tgbot_manage_addresslist.settings import Settings
from tgbot_manage_addresslist.telegram_bot import BotDependencies, register_handlers


class FakeAddressListManager:
    def __init__(self) -> None:
        self.fetch_calls = 0

    async def fetch_address_lists(self) -> list[str]:
        self.fetch_calls += 1
        return ["GERMANY", "OFFICE"]


class FailingAddressListManager:
    async def fetch_address_lists(self) -> list[str]:
        raise ConnectionRefusedError(111, "Connect call failed ('192.168.1.1', 46754)")


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


async def test_ip_message_reports_mikrotik_connection_error(monkeypatch) -> None:
    sent_methods: list[SendMessage] = []

    async def fake_make_request(self, bot, method, timeout=None):  # type: ignore[no-untyped-def]
        sent_methods.append(method)
        return True

    monkeypatch.setattr(AiohttpSession, "make_request", fake_make_request)

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
    register_handlers(dispatcher, BotDependencies(settings=settings, address_list_manager=FailingAddressListManager()))
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

    assert len(sent_methods) == 1
    assert sent_methods[0].text == "Не удалось подключиться к MikroTik. Проверьте SSH_HOST/PORT и доступность роутера."


async def test_setup_bot_commands_registers_expected_menu(monkeypatch) -> None:
    sent_methods: list[object] = []

    async def fake_make_request(self, bot, method, timeout=None):  # type: ignore[no-untyped-def]
        sent_methods.append(method)
        if isinstance(method, GetMe):
            return User(id=42, is_bot=True, first_name="TestBot", username="test_bot")
        return True

    monkeypatch.setattr(AiohttpSession, "make_request", fake_make_request)

    bot = Bot("42:TEST")
    await setup_bot_commands(bot)
    await bot.session.close()

    set_commands = [method for method in sent_methods if isinstance(method, SetMyCommands)]
    assert len(set_commands) == 1
    assert [(command.command, command.description) for command in set_commands[0].commands] == [
        ("start", "Добавить IP"),
        ("delete_list", "Удалить address-list"),
        ("cancel", "Отменить сценарий"),
        ("help", "Показать помощь"),
    ]
