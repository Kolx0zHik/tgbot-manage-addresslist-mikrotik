from pathlib import Path

from tgbot_manage_addresslist.installer import (
    BootstrapConfig,
    build_bootstrap_script,
    build_env_content,
)


def test_build_env_content_renders_expected_runtime_settings() -> None:
    config = BootstrapConfig(
        telegram_bot_token="token",
        allowed_telegram_user_ids=(1, 2),
        mikrotik_host="192.168.88.1",
        mikrotik_port=22,
        admin_username="admin",
        bot_username="tg-bot",
        group_name="tg-bot-group",
        compose_project_name="mikrotik-bot",
        image_name="tgbot-manage-addresslist-mikrotik:local",
        auto_start=True,
    )

    content = build_env_content(config)

    assert "TG_BOT_TOKEN=token" in content
    assert "ALLOWED_TELEGRAM_USER_IDS=1,2" in content
    assert "MIKROTIK_HOST=192.168.88.1" in content
    assert "MIKROTIK_USERNAME=tg-bot" in content
    assert "COMPOSE_PROJECT_NAME=mikrotik-bot" in content
    assert "IMAGE_NAME=tgbot-manage-addresslist-mikrotik:local" in content


def test_build_bootstrap_script_creates_group_user_and_imports_key() -> None:
    script = build_bootstrap_script(
        group_name="tg-bot-group",
        bot_username="tg-bot",
        bot_password="temporary-password",
        public_key_filename="tg-bot.pub",
    )

    assert '/user group add name="tg-bot-group"' in script
    assert 'policy=ssh,read,write,test,password' in script
    assert '/user add name="tg-bot" group="tg-bot-group" password="temporary-password"' in script
    assert '/user ssh-keys import public-key-file="tg-bot.pub" user="tg-bot"' in script
    assert '/file remove [find where name="tg-bot.pub"]' in script


def test_bootstrap_config_paths_are_derived_from_project_root() -> None:
    config = BootstrapConfig(
        telegram_bot_token="token",
        allowed_telegram_user_ids=(1,),
        mikrotik_host="router.example",
        mikrotik_port=22,
        admin_username="admin",
        bot_username="tg-bot",
        group_name="tg-bot-group",
        compose_project_name="mikrotik-bot",
        image_name="tgbot-manage-addresslist-mikrotik:local",
        auto_start=False,
    )

    paths = config.derived_paths(Path("/tmp/project"))

    assert paths["private_key_path"] == Path("/tmp/project/secrets/id_ed25519")
    assert paths["public_key_path"] == Path("/tmp/project/secrets/id_ed25519.pub")
    assert paths["known_hosts_path"] == Path("/tmp/project/secrets/known_hosts")
    assert paths["env_path"] == Path("/tmp/project/.env")
