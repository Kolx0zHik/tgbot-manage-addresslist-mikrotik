from __future__ import annotations

import pytest

from tgbot_manage_addresslist.mikrotik import CommandResult, MikroTikSSHClient
from tgbot_manage_addresslist.settings import Settings


class StubMikroTikSSHClient(MikroTikSSHClient):
    def __init__(self, result: CommandResult) -> None:
        settings = Settings(
            telegram_bot_token="token",
            allowed_telegram_user_ids=(1,),
            mikrotik_host="router",
            mikrotik_port=22,
            mikrotik_username="user",
            mikrotik_password="pass",
            log_level="INFO",
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
