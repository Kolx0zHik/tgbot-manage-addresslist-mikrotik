from __future__ import annotations

import pytest

from tgbot_manage_addresslist.settings import Settings


def test_settings_from_env_parses_multiple_mikrotiks(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "TG_BOT_TOKEN": "token",
        "ADMIN_TELEGRAM_USER_IDS": "100",
        "MIKROTIK_1_NAME": "Office",
        "MIKROTIK_1_HOST": "192.0.2.10",
        "MIKROTIK_1_PORT": "22",
        "MIKROTIK_1_USERNAME": "office-bot",
        "MIKROTIK_1_PASSWORD": "secret-1",
        "MIKROTIK_1_TELEGRAM_USER_IDS": "200,300",
        "MIKROTIK_2_NAME": "Warehouse",
        "MIKROTIK_2_HOST": "192.0.2.20",
        "MIKROTIK_2_PORT": "2222",
        "MIKROTIK_2_USERNAME": "warehouse-bot",
        "MIKROTIK_2_PASSWORD": "secret-2",
        "MIKROTIK_2_TELEGRAM_USER_IDS": "300,400",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    settings = Settings.from_env()

    assert settings.admin_telegram_user_ids == (100,)
    assert settings.allowed_telegram_user_ids == (100, 200, 300, 400)
    assert tuple(item.id for item in settings.mikrotiks) == ("1", "2")
    assert settings.mikrotiks_by_id["1"].name == "Office"
    assert settings.mikrotiks_by_id["2"].port == 2222
    assert settings.user_mikrotik_access == {
        200: ("1",),
        300: ("1", "2"),
        400: ("2",),
    }


def test_settings_from_env_rejects_missing_first_mikrotik(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {
        "TG_BOT_TOKEN": "token",
        "ADMIN_TELEGRAM_USER_IDS": "100",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(ValueError, match="MIKROTIK_1_NAME"):
        Settings.from_env()


def test_settings_from_env_rejects_gap_in_mikrotik_sequence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {
        "TG_BOT_TOKEN": "token",
        "ADMIN_TELEGRAM_USER_IDS": "100",
        "MIKROTIK_1_NAME": "Office",
        "MIKROTIK_1_HOST": "192.0.2.10",
        "MIKROTIK_1_PORT": "22",
        "MIKROTIK_1_USERNAME": "office-bot",
        "MIKROTIK_1_PASSWORD": "secret-1",
        "MIKROTIK_1_TELEGRAM_USER_IDS": "200",
        "MIKROTIK_3_NAME": "Warehouse",
        "MIKROTIK_3_HOST": "192.0.2.20",
        "MIKROTIK_3_PORT": "22",
        "MIKROTIK_3_USERNAME": "warehouse-bot",
        "MIKROTIK_3_PASSWORD": "secret-2",
        "MIKROTIK_3_TELEGRAM_USER_IDS": "300",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(ValueError, match="MIKROTIK_2_NAME"):
        Settings.from_env()


def test_settings_from_env_collects_access_from_router_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {
        "TG_BOT_TOKEN": "token",
        "ADMIN_TELEGRAM_USER_IDS": "100",
        "MIKROTIK_1_NAME": "Office",
        "MIKROTIK_1_HOST": "192.0.2.10",
        "MIKROTIK_1_PORT": "22",
        "MIKROTIK_1_USERNAME": "office-bot",
        "MIKROTIK_1_PASSWORD": "secret-1",
        "MIKROTIK_1_TELEGRAM_USER_IDS": "200,300",
        "MIKROTIK_2_NAME": "Warehouse",
        "MIKROTIK_2_HOST": "192.0.2.20",
        "MIKROTIK_2_PORT": "22",
        "MIKROTIK_2_USERNAME": "warehouse-bot",
        "MIKROTIK_2_PASSWORD": "secret-2",
        "MIKROTIK_2_TELEGRAM_USER_IDS": "300",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    settings = Settings.from_env()

    assert settings.user_mikrotik_access[200] == ("1",)
    assert settings.user_mikrotik_access[300] == ("1", "2")
    assert settings.allowed_telegram_user_ids == (100, 200, 300)


def test_settings_from_env_requires_user_list_for_each_router(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {
        "TG_BOT_TOKEN": "token",
        "ADMIN_TELEGRAM_USER_IDS": "100",
        "MIKROTIK_1_NAME": "Office",
        "MIKROTIK_1_HOST": "192.0.2.10",
        "MIKROTIK_1_PORT": "22",
        "MIKROTIK_1_USERNAME": "office-bot",
        "MIKROTIK_1_PASSWORD": "secret-1",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(ValueError, match="MIKROTIK_1_TELEGRAM_USER_IDS"):
        Settings.from_env()
