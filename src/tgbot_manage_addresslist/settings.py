from __future__ import annotations

import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv

MIKROTIK_ENV_RE = re.compile(r"^MIKROTIK_(\d+)_")


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
        raise ValueError("User id list must contain at least one user id")
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


def _parse_mikrotik_indices() -> tuple[int, ...]:
    indices = sorted(
        {
            int(match.group(1))
            for name in os.environ
            if (match := MIKROTIK_ENV_RE.match(name)) is not None
        }
    )
    if not indices:
        raise ValueError("Environment variable MIKROTIK_1_NAME is required")

    expected = list(range(1, indices[-1] + 1))
    if indices != expected:
        for expected_index in expected:
            if expected_index not in indices:
                raise ValueError(f"Environment variable MIKROTIK_{expected_index}_NAME is required")

    return tuple(indices)


def _parse_mikrotiks() -> tuple[MikroTikSettings, ...]:
    mikrotik_indices = _parse_mikrotik_indices()
    routers: list[MikroTikSettings] = []

    for mikrotik_index in mikrotik_indices:
        prefix = f"MIKROTIK_{mikrotik_index}"
        routers.append(
            MikroTikSettings(
                id=str(mikrotik_index),
                name=_require_env(f"{prefix}_NAME"),
                host=_require_env(f"{prefix}_HOST"),
                port=int(os.getenv(f"{prefix}_PORT", "22")),
                username=_require_env(f"{prefix}_USERNAME"),
                password=_require_env(f"{prefix}_PASSWORD"),
            )
        )

    return tuple(routers)


def _parse_user_mikrotik_access(
    mikrotiks: tuple[MikroTikSettings, ...],
) -> dict[int, tuple[str, ...]]:
    access: dict[int, list[str]] = {}

    for mikrotik in mikrotiks:
        raw_user_ids = _require_env(f"MIKROTIK_{mikrotik.id}_TELEGRAM_USER_IDS")
        for user_id in _parse_user_ids(raw_user_ids):
            access.setdefault(user_id, [])
            if mikrotik.id not in access[user_id]:
                access[user_id].append(mikrotik.id)

    return {user_id: tuple(mikrotik_ids) for user_id, mikrotik_ids in access.items()}


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
        admin_telegram_user_ids = _parse_user_ids(_require_env("ADMIN_TELEGRAM_USER_IDS"))
        mikrotiks = _parse_mikrotiks()
        mikrotiks_by_id = {item.id: item for item in mikrotiks}
        user_mikrotik_access = _parse_user_mikrotik_access(mikrotiks)
        allowed_telegram_user_ids = tuple(
            sorted(set(admin_telegram_user_ids) | set(user_mikrotik_access))
        )

        return cls(
            telegram_bot_token=_require_env("TG_BOT_TOKEN"),
            allowed_telegram_user_ids=allowed_telegram_user_ids,
            admin_telegram_user_ids=admin_telegram_user_ids,
            mikrotiks=mikrotiks,
            mikrotiks_by_id=mikrotiks_by_id,
            user_mikrotik_access=user_mikrotik_access,
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        )
