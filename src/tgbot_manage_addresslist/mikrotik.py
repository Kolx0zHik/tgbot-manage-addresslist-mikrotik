from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Protocol

import asyncssh

from tgbot_manage_addresslist.settings import MikroTikSettings


LIST_VALUE_RE = re.compile(r'(?:^|\s)list=(?:"((?:[^"\\]|\\.)*)"|(\S+))')
ADDRESS_VALUE_RE = re.compile(r'(?:^|\s)address=(?:"((?:[^"\\]|\\.)*)"|(\S+))')
logger = logging.getLogger(__name__)


class MikroTikClientProtocol(Protocol):
    async def fetch_address_lists(self) -> list[str]:
        ...

    async def add_address(self, list_name: str, ip_address: str) -> str | None:
        ...

    async def ensure_mangle_rule(self, list_name: str) -> None:
        ...

    async def delete_address_list(self, list_name: str) -> int:
        ...

    async def delete_mangle_rule(self, list_name: str) -> None:
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


def mangle_rule_comment(list_name: str) -> str:
    return f"tgbot_manage_addresslist: route {list_name} via VPN_Table"


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
    def __init__(self, settings: MikroTikSettings) -> None:
        self._settings = settings

    async def _run(self, command: str) -> CommandResult:
        logger.info(
            "Connecting to MikroTik over SSH: id=%s name=%s host=%s port=%s user=%s",
            self._settings.id,
            self._settings.name,
            self._settings.host,
            self._settings.port,
            self._settings.username,
        )
        try:
            async with asyncssh.connect(
                host=self._settings.host,
                port=self._settings.port,
                username=self._settings.username,
                password=self._settings.password,
                known_hosts=None,
            ) as connection:
                result = await connection.run(command, check=False)
        except Exception:
            logger.exception("MikroTik SSH command failed to run: %s", command)
            raise
        logger.info("MikroTik SSH command finished with exit status %s", result.exit_status)
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
        stdout_lowered = result.stdout.lower()
        if result.exit_status == 0 and not stdout_lowered.startswith("failure:"):
            return None
        return result.stderr or result.stdout or "Unknown MikroTik error"

    async def ensure_mangle_rule(self, list_name: str) -> None:
        command = (
            f"/ip firewall mangle add chain=prerouting src-address-list={routeros_quote(list_name)} "
            f"action=mark-routing new-routing-mark={routeros_quote('VPN_Table')} passthrough=yes "
            f"comment={routeros_quote(mangle_rule_comment(list_name))}"
        )
        result = await self._run(command)
        stdout_lowered = result.stdout.lower()
        if result.exit_status != 0 or stdout_lowered.startswith("failure:"):
            raise RuntimeError(result.stderr or result.stdout or "Failed to add MikroTik mangle rule")

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

    async def delete_mangle_rule(self, list_name: str) -> None:
        command = (
            "/ip firewall mangle remove [find "
            f"comment={routeros_quote(mangle_rule_comment(list_name))}]"
        )
        result = await self._run(command)
        stdout_lowered = result.stdout.lower()
        if result.exit_status != 0 or stdout_lowered.startswith("failure:"):
            raise RuntimeError(result.stderr or result.stdout or "Failed to delete MikroTik mangle rule")
