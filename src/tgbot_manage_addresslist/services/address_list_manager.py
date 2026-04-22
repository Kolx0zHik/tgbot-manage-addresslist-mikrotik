from __future__ import annotations

from dataclasses import dataclass

from tgbot_manage_addresslist.mikrotik.client import MikroTikClientProtocol


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

        for ip_address in valid_ips:
            error = await self._mikrotik_client.add_address(list_name, ip_address)
            if error is None:
                added.append(ip_address)
                continue
            normalized_error = error.lower()
            if "already have such entry" in normalized_error or "already exists" in normalized_error:
                duplicates.append(ip_address)
                continue
            errors.append(AddOperationError(ip_address=ip_address, reason=error))

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
