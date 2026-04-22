from __future__ import annotations

from tgbot_manage_addresslist.services.address_list_manager import AddressListManager


class FakeMikroTikClient:
    def __init__(self) -> None:
        self.add_errors: dict[tuple[str, str], str | None] = {}
        self.deleted_lists: list[str] = []

    async def fetch_address_lists(self) -> list[str]:
        return ["GERMANY", "OFFICE"]

    async def add_address(self, list_name: str, ip_address: str) -> str | None:
        return self.add_errors.get((list_name, ip_address))

    async def delete_address_list(self, list_name: str) -> int:
        self.deleted_lists.append(list_name)
        return 3


async def test_add_ips_reports_partial_success() -> None:
    client = FakeMikroTikClient()
    client.add_errors[("GERMANY", "2.2.2.2")] = "already have such entry"
    client.add_errors[("GERMANY", "3.3.3.3")] = "failure"
    manager = AddressListManager(client)

    result = await manager.add_ips(
        list_name="GERMANY",
        valid_ips=["1.1.1.1", "2.2.2.2", "3.3.3.3"],
        invalid_tokens=["bad-ip"],
    )

    assert result.added == ["1.1.1.1"]
    assert result.duplicates == ["2.2.2.2"]
    assert result.invalid_tokens == ["bad-ip"]
    assert [(item.ip_address, item.reason) for item in result.errors] == [("3.3.3.3", "failure")]


async def test_delete_list_returns_removed_count() -> None:
    client = FakeMikroTikClient()
    manager = AddressListManager(client)

    result = await manager.delete_list("GERMANY")

    assert result.list_name == "GERMANY"
    assert result.removed_count == 3
    assert client.deleted_lists == ["GERMANY"]
