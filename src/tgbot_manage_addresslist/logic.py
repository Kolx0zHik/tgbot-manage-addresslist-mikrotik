from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address, ip_network
import re

from tgbot_manage_addresslist.mikrotik import MikroTikClientProtocol
from tgbot_manage_addresslist.settings import MikroTikSettings, Settings


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
        *,
        create_mangle_rule: bool = False,
    ) -> AddOperationResult:
        added: list[str] = []
        duplicates: list[str] = []
        errors: list[AddOperationError] = []

        if create_mangle_rule:
            await self._mikrotik_client.ensure_mangle_rule(list_name)

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
        await self._mikrotik_client.delete_mangle_rule(list_name)
        return DeleteOperationResult(list_name=list_name, removed_count=removed_count)


class AddressListService:
    def __init__(self, managers_by_id: dict[str, AddressListManager]) -> None:
        self._managers_by_id = managers_by_id

    def _manager_for(self, mikrotik_id: str) -> AddressListManager:
        try:
            return self._managers_by_id[mikrotik_id]
        except KeyError as exc:
            raise ValueError(f"Unknown MikroTik id: {mikrotik_id}") from exc

    async def fetch_address_lists(self, mikrotik_id: str) -> list[str]:
        return await self._manager_for(mikrotik_id).fetch_address_lists()

    async def add_ips(
        self,
        mikrotik_id: str,
        list_name: str,
        valid_ips: list[str],
        invalid_tokens: list[str],
        *,
        create_mangle_rule: bool = False,
    ) -> AddOperationResult:
        return await self._manager_for(mikrotik_id).add_ips(
            list_name,
            valid_ips,
            invalid_tokens,
            create_mangle_rule=create_mangle_rule,
        )

    async def delete_list(self, mikrotik_id: str, list_name: str) -> DeleteOperationResult:
        return await self._manager_for(mikrotik_id).delete_list(list_name)


class UserAccessResolver:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def is_allowed(self, user_id: int) -> bool:
        return user_id in self._settings.allowed_telegram_user_ids

    def is_admin(self, user_id: int) -> bool:
        return user_id in self._settings.admin_telegram_user_ids

    def visible_mikrotiks_for(self, user_id: int) -> tuple[MikroTikSettings, ...]:
        if self.is_admin(user_id):
            return self._settings.mikrotiks

        allowed_ids = self._settings.user_mikrotik_access.get(user_id, ())
        return tuple(self._settings.mikrotiks_by_id[item_id] for item_id in allowed_ids)

    def can_access(self, user_id: int, mikrotik_id: str) -> bool:
        return mikrotik_id in {item.id for item in self.visible_mikrotiks_for(user_id)}
