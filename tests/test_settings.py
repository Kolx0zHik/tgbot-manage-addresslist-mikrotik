import os

from tgbot_manage_addresslist.settings import Settings


def test_settings_from_env_uses_password_auth(monkeypatch) -> None:
    monkeypatch.setenv("TG_BOT_TOKEN", "token")
    monkeypatch.setenv("ALLOWED_TELEGRAM_USER_IDS", "1, 2")
    monkeypatch.setenv("MIKROTIK_HOST", "192.168.88.1")
    monkeypatch.setenv("MIKROTIK_PORT", "22")
    monkeypatch.setenv("MIKROTIK_USERNAME", "tg-bot")
    monkeypatch.setenv("MIKROTIK_PASSWORD", "secret")

    settings = Settings.from_env()

    assert settings.telegram_bot_token == "token"
    assert settings.allowed_telegram_user_ids == (1, 2)
    assert settings.mikrotik_host == "192.168.88.1"
    assert settings.mikrotik_port == 22
    assert settings.mikrotik_username == "tg-bot"
    assert settings.mikrotik_password == "secret"
