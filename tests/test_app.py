from __future__ import annotations

import logging

import pytest

from tgbot_manage_addresslist.app import log_startup_health_checks
from tgbot_manage_addresslist.settings import MikroTikSettings


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
