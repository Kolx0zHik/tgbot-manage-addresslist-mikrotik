from __future__ import annotations

import pytest

from tgbot_manage_addresslist.logic import (
    AddressListManager,
    AddressListService,
    UserAccessResolver,
)
from tgbot_manage_addresslist.settings import MikroTikSettings, Settings


class StubClient:
    def __init__(self, *, address_lists: list[str] | None = None) -> None:
        self.address_lists = address_lists or []
        self.calls: list[tuple[str, str] | tuple[str, str, str]] = []

    async def fetch_address_lists(self) -> list[str]:
        return self.address_lists

    async def add_address(self, list_name: str, ip_address: str) -> str | None:
        self.calls.append(("add_address", list_name, ip_address))
        return None

    async def delete_address_list(self, list_name: str) -> int:
        self.calls.append(("delete_address_list", list_name))
        return 1

    async def ensure_mangle_rule(self, list_name: str) -> None:
        self.calls.append(("ensure_mangle_rule", list_name))

    async def delete_mangle_rule(self, list_name: str) -> None:
        self.calls.append(("delete_mangle_rule", list_name))


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


def test_user_access_resolver_returns_all_routers_for_admin() -> None:
    resolver = UserAccessResolver(make_settings())

    visible = resolver.visible_mikrotiks_for(100)

    assert [item.id for item in visible] == ["mt1", "mt2"]


def test_user_access_resolver_returns_assigned_routers_for_regular_user() -> None:
    resolver = UserAccessResolver(make_settings())

    visible = resolver.visible_mikrotiks_for(200)

    assert [item.id for item in visible] == ["mt1"]


@pytest.mark.asyncio
async def test_address_list_service_routes_calls_by_mikrotik_id() -> None:
    service = AddressListService(
        managers_by_id={
            "mt1": AddressListManager(StubClient(address_lists=["office-list"])),
            "mt2": AddressListManager(StubClient(address_lists=["warehouse-list"])),
        }
    )

    office_lists = await service.fetch_address_lists("mt1")
    warehouse_lists = await service.fetch_address_lists("mt2")

    assert office_lists == ["office-list"]
    assert warehouse_lists == ["warehouse-list"]


@pytest.mark.asyncio
async def test_address_list_manager_creates_mangle_rule_before_adding_ips_for_new_list() -> None:
    client = StubClient()
    manager = AddressListManager(client)

    await manager.add_ips(
        "to-VPN",
        ["192.0.2.10"],
        [],
        create_mangle_rule=True,
    )

    assert client.calls == [
        ("ensure_mangle_rule", "to-VPN"),
        ("add_address", "to-VPN", "192.0.2.10"),
    ]


@pytest.mark.asyncio
async def test_address_list_manager_deletes_mangle_rule_when_deleting_list() -> None:
    client = StubClient()
    manager = AddressListManager(client)

    await manager.delete_list("to-VPN")

    assert client.calls == [
        ("delete_address_list", "to-VPN"),
        ("delete_mangle_rule", "to-VPN"),
    ]
