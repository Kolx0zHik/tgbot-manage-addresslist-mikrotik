from __future__ import annotations

import pytest

from tgbot_manage_addresslist.settings import Settings


def test_settings_from_env_parses_multiple_mikrotiks(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "TG_BOT_TOKEN": "token",
        "ALLOWED_TELEGRAM_USER_IDS": "100,200,300",
        "ADMIN_TELEGRAM_USER_IDS": "100",
        "MIKROTIK_IDS": "mt1,mt2",
        "MIKROTIK_MT1_NAME": "Office",
        "MIKROTIK_MT1_HOST": "192.0.2.10",
        "MIKROTIK_MT1_PORT": "22",
        "MIKROTIK_MT1_USERNAME": "office-bot",
        "MIKROTIK_MT1_PASSWORD": "secret-1",
        "MIKROTIK_MT2_NAME": "Warehouse",
        "MIKROTIK_MT2_HOST": "192.0.2.20",
        "MIKROTIK_MT2_PORT": "2222",
        "MIKROTIK_MT2_USERNAME": "warehouse-bot",
        "MIKROTIK_MT2_PASSWORD": "secret-2",
        "USER_MIKROTIK_ACCESS_200": "mt1",
        "USER_MIKROTIK_ACCESS_300": "mt2",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    settings = Settings.from_env()

    assert settings.admin_telegram_user_ids == (100,)
    assert tuple(item.id for item in settings.mikrotiks) == ("mt1", "mt2")
    assert settings.mikrotiks_by_id["mt1"].name == "Office"
    assert settings.mikrotiks_by_id["mt2"].port == 2222
    assert settings.user_mikrotik_access == {200: ("mt1",), 300: ("mt2",)}


def test_settings_from_env_rejects_regular_user_without_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {
        "TG_BOT_TOKEN": "token",
        "ALLOWED_TELEGRAM_USER_IDS": "100,200",
        "ADMIN_TELEGRAM_USER_IDS": "100",
        "MIKROTIK_IDS": "mt1",
        "MIKROTIK_MT1_NAME": "Office",
        "MIKROTIK_MT1_HOST": "192.0.2.10",
        "MIKROTIK_MT1_PORT": "22",
        "MIKROTIK_MT1_USERNAME": "office-bot",
        "MIKROTIK_MT1_PASSWORD": "secret-1",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(ValueError, match="must have at least one assigned MikroTik"):
        Settings.from_env()


def test_settings_from_env_rejects_unknown_mikrotik_in_user_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {
        "TG_BOT_TOKEN": "token",
        "ALLOWED_TELEGRAM_USER_IDS": "100,200",
        "ADMIN_TELEGRAM_USER_IDS": "100",
        "MIKROTIK_IDS": "mt1",
        "MIKROTIK_MT1_NAME": "Office",
        "MIKROTIK_MT1_HOST": "192.0.2.10",
        "MIKROTIK_MT1_PORT": "22",
        "MIKROTIK_MT1_USERNAME": "office-bot",
        "MIKROTIK_MT1_PASSWORD": "secret-1",
        "USER_MIKROTIK_ACCESS_200": "mt2",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(ValueError, match="Unknown MikroTik id"):
        Settings.from_env()
