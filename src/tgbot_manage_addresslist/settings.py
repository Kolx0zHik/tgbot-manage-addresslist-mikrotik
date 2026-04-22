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


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    allowed_telegram_user_ids: tuple[int, ...]
    mikrotik_host: str
    mikrotik_port: int
    mikrotik_username: str
    mikrotik_password: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            telegram_bot_token=_require_env("TG_BOT_TOKEN"),
            allowed_telegram_user_ids=_parse_user_ids(_require_env("ALLOWED_TELEGRAM_USER_IDS")),
            mikrotik_host=_require_env("MIKROTIK_HOST"),
            mikrotik_port=int(os.getenv("MIKROTIK_PORT", "22")),
            mikrotik_username=_require_env("MIKROTIK_USERNAME"),
            mikrotik_password=_require_env("MIKROTIK_PASSWORD"),
        )
