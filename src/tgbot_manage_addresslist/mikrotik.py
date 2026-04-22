from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol

import asyncssh

from tgbot_manage_addresslist.settings import Settings


LIST_VALUE_RE = re.compile(r'(?:^|\s)list=(?:"((?:[^"\\]|\\.)*)"|(\S+))')
ADDRESS_VALUE_RE = re.compile(r'(?:^|\s)address=(?:"((?:[^"\\]|\\.)*)"|(\S+))')


class MikroTikClientProtocol(Protocol):
    async def fetch_address_lists(self) -> list[str]:
        ...

    async def add_address(self, list_name: str, ip_address: str) -> str | None:
        ...

    async def delete_address_list(self, list_name: str) -> int:
        ...


@dataclass(frozen=True, slots=True)
class CommandResult:
    stdout: str
    stderr: str
    exit_status: int


def _unescape_routeros_value(value: str) -> str:
    return value.replace('\\"', '"').replace("\\\\", "\\")


def routeros_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def parse_address_list_names(output: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for line in output.splitlines():
        match = LIST_VALUE_RE.search(line)
        if not match:
            continue
        raw_value = match.group(1) if match.group(1) is not None else match.group(2)
        assert raw_value is not None
        value = _unescape_routeros_value(raw_value)
        if value not in seen:
            seen.add(value)
            names.append(value)
    return sorted(names)


def parse_addresses(output: str) -> list[str]:
    addresses: list[str] = []
    for line in output.splitlines():
        match = ADDRESS_VALUE_RE.search(line)
        if not match:
            continue
        raw_value = match.group(1) if match.group(1) is not None else match.group(2)
        assert raw_value is not None
        addresses.append(_unescape_routeros_value(raw_value))
    return addresses


class MikroTikSSHClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def _run(self, command: str) -> CommandResult:
        async with asyncssh.connect(
            host=self._settings.mikrotik_host,
            port=self._settings.mikrotik_port,
            username=self._settings.mikrotik_username,
            password=self._settings.mikrotik_password,
            known_hosts=None,
        ) as connection:
            result = await connection.run(command, check=False)
        return CommandResult(
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
            exit_status=result.exit_status,
        )

    async def fetch_address_lists(self) -> list[str]:
        result = await self._run("/ip firewall address-list print terse without-paging")
        if result.exit_status != 0:
            raise RuntimeError(result.stderr or "Failed to fetch MikroTik address-lists")
        return parse_address_list_names(result.stdout)

    async def add_address(self, list_name: str, ip_address: str) -> str | None:
        command = (
            f"/ip firewall address-list add list={routeros_quote(list_name)} "
            f"address={routeros_quote(ip_address)}"
        )
        result = await self._run(command)
        if result.exit_status == 0:
            return None
        return result.stderr or "Unknown MikroTik error"

    async def delete_address_list(self, list_name: str) -> int:
        inspect_command = (
            f"/ip firewall address-list print terse without-paging where list={routeros_quote(list_name)}"
        )
        inspect_result = await self._run(inspect_command)
        if inspect_result.exit_status != 0:
            raise RuntimeError(inspect_result.stderr or "Failed to inspect MikroTik address-list")

        delete_command = f"/ip firewall address-list remove [find list={routeros_quote(list_name)}]"
        delete_result = await self._run(delete_command)
        if delete_result.exit_status != 0:
            raise RuntimeError(delete_result.stderr or "Failed to delete MikroTik address-list")

        return len(parse_addresses(inspect_result.stdout))
