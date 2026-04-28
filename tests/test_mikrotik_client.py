from __future__ import annotations

import pytest

from tgbot_manage_addresslist.mikrotik import CommandResult, MikroTikSSHClient
from tgbot_manage_addresslist.settings import MikroTikSettings


class StubMikroTikSSHClient(MikroTikSSHClient):
    def __init__(self, result: CommandResult | list[CommandResult]) -> None:
        settings = MikroTikSettings(
            id="mt1",
            name="Office",
            host="router",
            port=22,
            username="user",
            password="pass",
        )
        super().__init__(settings)
        self._results = result if isinstance(result, list) else [result]
        self.commands: list[str] = []

    async def _run(self, command: str) -> CommandResult:
        self.commands.append(command)
        return self._results.pop(0)


@pytest.mark.asyncio
async def test_add_address_treats_routeros_failure_in_stdout_as_error() -> None:
    client = StubMikroTikSSHClient(
        CommandResult(
            stdout="failure: already have such entry",
            stderr="",
            exit_status=0,
        )
    )

    error = await client.add_address("to-VPN", "77.222.40.195")

    assert error == "failure: already have such entry"


@pytest.mark.asyncio
async def test_fetch_address_lists_uses_router_specific_settings() -> None:
    client = StubMikroTikSSHClient(
        CommandResult(
            stdout='0 list="office-list" address=192.0.2.10',
            stderr="",
            exit_status=0,
        )
    )

    result = await client.fetch_address_lists()

    assert result == ["office-list"]


@pytest.mark.asyncio
async def test_ensure_mangle_rule_adds_vpn_table_rule_with_comment() -> None:
    client = StubMikroTikSSHClient(CommandResult(stdout="", stderr="", exit_status=0))

    await client.ensure_mangle_rule("to-VPN")

    assert client.commands == [
        (
            '/ip firewall mangle add chain=prerouting dst-address-list="to-VPN" '
            'action=mark-routing new-routing-mark="VPN_Table" passthrough=yes '
            'comment="tgbot_manage_addresslist: route to-VPN via VPN_Table"'
        )
    ]


@pytest.mark.asyncio
async def test_delete_mangle_rule_removes_rule_by_comment() -> None:
    client = StubMikroTikSSHClient(CommandResult(stdout="", stderr="", exit_status=0))

    await client.delete_mangle_rule("to-VPN")

    assert client.commands == [
        (
            '/ip firewall mangle remove [find comment='
            '"tgbot_manage_addresslist: route to-VPN via VPN_Table"]'
        )
    ]
