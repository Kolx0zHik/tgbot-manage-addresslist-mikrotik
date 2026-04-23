from __future__ import annotations

import logging

import pytest

import tgbot_manage_addresslist.app as app_module
from tgbot_manage_addresslist.app import build_dependencies, log_startup_health_checks
from tgbot_manage_addresslist.settings import MikroTikSettings, Settings


class StubAddressListService:
    def __init__(self) -> None:
        self._results = {
            "mt1": ["office-list"],
            "mt2": RuntimeError("router down"),
        }

    async def fetch_address_lists(self, mikrotik_id: str) -> list[str]:
        result = self._results[mikrotik_id]
        if isinstance(result, Exception):
            raise result
        return result


def make_settings() -> Settings:
    mikrotiks = (
        MikroTikSettings(
            id="mt1",
            name="Office",
            host="192.0.2.10",
            port=22,
            username="u1",
            password="p1",
        ),
        MikroTikSettings(
            id="mt2",
            name="Warehouse",
            host="192.0.2.20",
            port=22,
            username="u2",
            password="p2",
        ),
    )
    return Settings(
        telegram_bot_token="token",
        allowed_telegram_user_ids=(100, 200, 300),
        admin_telegram_user_ids=(100,),
        mikrotiks=mikrotiks,
        mikrotiks_by_id={item.id: item for item in mikrotiks},
        user_mikrotik_access={200: ("mt1",), 300: ("mt2",)},
        log_level="INFO",
    )


def test_build_dependencies_creates_service_and_access_resolver() -> None:
    deps = build_dependencies(make_settings())

    assert set(deps.address_list_service._managers_by_id) == {"mt1", "mt2"}
    assert deps.user_access_resolver.is_admin(100)


@pytest.mark.asyncio
async def test_run_does_not_block_on_startup_health_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    started = {"polling": False}

    class StubBot:
        def __init__(self, token: str) -> None:
            self.token = token
            self.session = type("Session", (), {"close": self._close})()

        async def _close(self) -> None:
            return None

    class StubDispatcher:
        def __init__(self, storage=None) -> None:
            self.storage = storage

        async def start_polling(self, bot) -> None:
            started["polling"] = True

    monkeypatch.setattr(app_module.Settings, "from_env", classmethod(lambda cls: make_settings()))
    monkeypatch.setattr(app_module, "Bot", StubBot)
    monkeypatch.setattr(app_module, "Dispatcher", StubDispatcher)
    monkeypatch.setattr(app_module, "setup_bot_commands", lambda bot: _async_noop())
    monkeypatch.setattr(app_module, "register_handlers", lambda dispatcher, deps: None)
    monkeypatch.setattr(
        app_module,
        "log_startup_health_checks",
        lambda service, mikrotiks: _raise_if_called(),
    )

    await app_module.run()

    assert started["polling"] is True


async def _async_noop() -> None:
    return None


async def _raise_if_called() -> None:
    raise AssertionError("startup health checks should not block bot startup")


@pytest.mark.asyncio
async def test_startup_health_check_logs_each_router(caplog: pytest.LogCaptureFixture) -> None:
    service = StubAddressListService()
    mikrotiks = (
        MikroTikSettings(
            id="mt1",
            name="Office",
            host="192.0.2.10",
            port=22,
            username="u1",
            password="p1",
        ),
        MikroTikSettings(
            id="mt2",
            name="Warehouse",
            host="192.0.2.20",
            port=22,
            username="u2",
            password="p2",
        ),
    )

    with caplog.at_level(logging.INFO):
        await log_startup_health_checks(service, mikrotiks)

    assert "Initial MikroTik SSH check succeeded for id=mt1 name=Office found=1" in caplog.text
    assert "Initial MikroTik SSH check failed for id=mt2 name=Warehouse" in caplog.text
