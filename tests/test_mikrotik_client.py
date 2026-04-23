from __future__ import annotations

import pytest

from tgbot_manage_addresslist.mikrotik import CommandResult, MikroTikSSHClient
from tgbot_manage_addresslist.settings import MikroTikSettings


class StubMikroTikSSHClient(MikroTikSSHClient):
    def __init__(self, result: CommandResult) -> None:
        settings = MikroTikSettings(
            id="mt1",
            name="Office",
            host="router",
            port=22,
            username="user",
            password="pass",
        )
        super().__init__(settings)
        self._result = result

    async def _run(self, command: str) -> CommandResult:
        return self._result


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
