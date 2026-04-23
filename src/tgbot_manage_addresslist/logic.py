from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address, ip_network
import re

from tgbot_manage_addresslist.mikrotik import MikroTikClientProtocol


TOKEN_SPLIT_RE = re.compile(r"[\s,;]+")


@dataclass(frozen=True, slots=True)
class ParsedIpInput:
    valid_ips: list[str]
    invalid_tokens: list[str]


def parse_ip_input(raw_text: str) -> ParsedIpInput:
    valid_ips: list[str] = []
    invalid_tokens: list[str] = []
    seen: set[str] = set()

    for token in TOKEN_SPLIT_RE.split(raw_text.strip()):
        if not token:
            continue
        try:
            normalized = str(ip_address(token))
        except ValueError:
            try:
                normalized = str(ip_network(token, strict=True))
            except ValueError:
                invalid_tokens.append(token)
                continue
        if normalized in seen:
            continue
        seen.add(normalized)
        valid_ips.append(normalized)

    return ParsedIpInput(valid_ips=valid_ips, invalid_tokens=invalid_tokens)


@dataclass(frozen=True, slots=True)
class AddOperationError:
    ip_address: str
    reason: str


@dataclass(frozen=True, slots=True)
class AddOperationResult:
    list_name: str
    added: list[str]
    duplicates: list[str]
    invalid_tokens: list[str]
    errors: list[AddOperationError]


@dataclass(frozen=True, slots=True)
class DeleteOperationResult:
    list_name: str
    removed_count: int


class AddressListManager:
    def __init__(self, mikrotik_client: MikroTikClientProtocol) -> None:
        self._mikrotik_client = mikrotik_client

    async def fetch_address_lists(self) -> list[str]:
        return await self._mikrotik_client.fetch_address_lists()

    async def add_ips(
        self,
        list_name: str,
        valid_ips: list[str],
        invalid_tokens: list[str],
    ) -> AddOperationResult:
        added: list[str] = []
        duplicates: list[str] = []
        errors: list[AddOperationError] = []

        for current_ip in valid_ips:
            error = await self._mikrotik_client.add_address(list_name, current_ip)
            if error is None:
                added.append(current_ip)
                continue
            lowered_error = error.lower()
            if "already have such entry" in lowered_error or "already exists" in lowered_error:
                duplicates.append(current_ip)
                continue
            errors.append(AddOperationError(ip_address=current_ip, reason=error))

        return AddOperationResult(
            list_name=list_name,
            added=added,
            duplicates=duplicates,
            invalid_tokens=invalid_tokens,
            errors=errors,
        )

    async def delete_list(self, list_name: str) -> DeleteOperationResult:
        removed_count = await self._mikrotik_client.delete_address_list(list_name)
        return DeleteOperationResult(list_name=list_name, removed_count=removed_count)
