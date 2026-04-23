from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Environment variable {name} is required")
    return value


def _parse_user_ids(raw: str) -> tuple[int, ...]:
    user_ids: list[int] = []
    for item in raw.split(","):
        stripped = item.strip()
        if stripped:
            user_ids.append(int(stripped))
    if not user_ids:
        raise ValueError("ALLOWED_TELEGRAM_USER_IDS must contain at least one user id")
    return tuple(user_ids)


def _parse_csv_items(raw: str, *, field_name: str) -> tuple[str, ...]:
    items = tuple(item.strip() for item in raw.split(",") if item.strip())
    if not items:
        raise ValueError(f"{field_name} must contain at least one value")
    return items


@dataclass(frozen=True, slots=True)
class MikroTikSettings:
    id: str
    name: str
    host: str
    port: int
    username: str
    password: str


def _parse_mikrotiks() -> tuple[MikroTikSettings, ...]:
    mikrotik_ids = tuple(
        item.lower()
        for item in _parse_csv_items(_require_env("MIKROTIK_IDS"), field_name="MIKROTIK_IDS")
    )
    routers: list[MikroTikSettings] = []

    for mikrotik_id in mikrotik_ids:
        env_id = mikrotik_id.upper()
        routers.append(
            MikroTikSettings(
                id=mikrotik_id,
                name=_require_env(f"MIKROTIK_{env_id}_NAME"),
                host=_require_env(f"MIKROTIK_{env_id}_HOST"),
                port=int(os.getenv(f"MIKROTIK_{env_id}_PORT", "22")),
                username=_require_env(f"MIKROTIK_{env_id}_USERNAME"),
                password=_require_env(f"MIKROTIK_{env_id}_PASSWORD"),
            )
        )

    return tuple(routers)


def _parse_user_mikrotik_access(
    *,
    allowed_user_ids: tuple[int, ...],
    admin_user_ids: tuple[int, ...],
    known_mikrotik_ids: set[str],
) -> dict[int, tuple[str, ...]]:
    access: dict[int, tuple[str, ...]] = {}

    for user_id in allowed_user_ids:
        if user_id in admin_user_ids:
            continue

        raw = os.getenv(f"USER_MIKROTIK_ACCESS_{user_id}", "").strip()
        if not raw:
            raise ValueError(f"Telegram user {user_id} must have at least one assigned MikroTik")
        mikrotik_ids = tuple(
            item.lower()
            for item in _parse_csv_items(raw, field_name=f"USER_MIKROTIK_ACCESS_{user_id}")
        )
        unknown_ids = [item for item in mikrotik_ids if item not in known_mikrotik_ids]
        if unknown_ids:
            raise ValueError(f"Unknown MikroTik id for user {user_id}: {', '.join(unknown_ids)}")
        access[user_id] = mikrotik_ids

    return access


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    allowed_telegram_user_ids: tuple[int, ...]
    admin_telegram_user_ids: tuple[int, ...]
    mikrotiks: tuple[MikroTikSettings, ...]
    mikrotiks_by_id: dict[str, MikroTikSettings]
    user_mikrotik_access: dict[int, tuple[str, ...]]
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        allowed_telegram_user_ids = _parse_user_ids(_require_env("ALLOWED_TELEGRAM_USER_IDS"))
        admin_telegram_user_ids = _parse_user_ids(_require_env("ADMIN_TELEGRAM_USER_IDS"))
        admin_user_ids = set(admin_telegram_user_ids)
        allowed_user_ids = set(allowed_telegram_user_ids)
        if not admin_user_ids.issubset(allowed_user_ids):
            raise ValueError("ADMIN_TELEGRAM_USER_IDS must be a subset of ALLOWED_TELEGRAM_USER_IDS")

        mikrotiks = _parse_mikrotiks()
        mikrotiks_by_id = {item.id: item for item in mikrotiks}
        user_mikrotik_access = _parse_user_mikrotik_access(
            allowed_user_ids=allowed_telegram_user_ids,
            admin_user_ids=admin_telegram_user_ids,
            known_mikrotik_ids=set(mikrotiks_by_id),
        )

        regular_user_ids = allowed_user_ids - admin_user_ids
        for user_id in regular_user_ids:
            if not user_mikrotik_access.get(user_id):
                raise ValueError(f"Telegram user {user_id} must have at least one assigned MikroTik")

        return cls(
            telegram_bot_token=_require_env("TG_BOT_TOKEN"),
            allowed_telegram_user_ids=allowed_telegram_user_ids,
            admin_telegram_user_ids=admin_telegram_user_ids,
            mikrotiks=mikrotiks,
            mikrotiks_by_id=mikrotiks_by_id,
            user_mikrotik_access=user_mikrotik_access,
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        )
