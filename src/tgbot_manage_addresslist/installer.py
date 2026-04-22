from __future__ import annotations

import asyncio
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
import secrets
import shlex
import subprocess
import sys

import asyncssh

from tgbot_manage_addresslist.mikrotik.client import routeros_quote


DEFAULT_GROUP_POLICIES = "ssh,read,write,test,password"


@dataclass(frozen=True, slots=True)
class BootstrapConfig:
    telegram_bot_token: str
    allowed_telegram_user_ids: tuple[int, ...]
    mikrotik_host: str
    mikrotik_port: int
    admin_username: str
    bot_username: str
    group_name: str
    compose_project_name: str
    image_name: str
    auto_start: bool

    def derived_paths(self, project_root: Path) -> dict[str, Path]:
        secrets_dir = project_root / "secrets"
        return {
            "secrets_dir": secrets_dir,
            "private_key_path": secrets_dir / "id_ed25519",
            "public_key_path": secrets_dir / "id_ed25519.pub",
            "known_hosts_path": secrets_dir / "known_hosts",
            "env_path": project_root / ".env",
        }


def build_env_content(config: BootstrapConfig) -> str:
    user_ids = ",".join(str(user_id) for user_id in config.allowed_telegram_user_ids)
    return "\n".join(
        [
            f"TG_BOT_TOKEN={config.telegram_bot_token}",
            f"ALLOWED_TELEGRAM_USER_IDS={user_ids}",
            f"MIKROTIK_HOST={config.mikrotik_host}",
            f"MIKROTIK_PORT={config.mikrotik_port}",
            f"MIKROTIK_USERNAME={config.bot_username}",
            "MIKROTIK_SSH_PRIVATE_KEY_PATH=/run/secrets/mikrotik_ssh_key",
            "MIKROTIK_SSH_KNOWN_HOSTS_PATH=/run/secrets/known_hosts",
            f"COMPOSE_PROJECT_NAME={config.compose_project_name}",
            f"IMAGE_NAME={config.image_name}",
            "",
        ]
    )


def build_bootstrap_script(
    *,
    group_name: str,
    bot_username: str,
    bot_password: str,
    public_key_filename: str,
) -> str:
    group_name_q = routeros_quote(group_name)
    bot_username_q = routeros_quote(bot_username)
    bot_password_q = routeros_quote(bot_password)
    public_key_filename_q = routeros_quote(public_key_filename)

    return "\n".join(
        [
            f':if ([:len [/user group find where name={group_name_q}]] = 0) do={{'
            f'/user group add name={group_name_q} policy={DEFAULT_GROUP_POLICIES}'
            f'}} else={{'
            f'/user group set [find where name={group_name_q}] policy={DEFAULT_GROUP_POLICIES}'
            f'}}',
            f':if ([:len [/user find where name={bot_username_q}]] = 0) do={{'
            f'/user add name={bot_username_q} group={group_name_q} password={bot_password_q}'
            f'}} else={{'
            f'/user set [find where name={bot_username_q}] group={group_name_q} password={bot_password_q}'
            f'}}',
            f'/user ssh-keys import public-key-file={public_key_filename_q} user={bot_username_q}',
            f'/file remove [find where name={public_key_filename_q}]',
        ]
    )


def _prompt(text: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    if value:
        return value
    if default is not None:
        return default
    return _prompt(text, default)


def _prompt_yes_no(text: str, default: bool) -> bool:
    default_label = "Y/n" if default else "y/N"
    value = input(f"{text} [{default_label}]: ").strip().lower()
    if not value:
        return default
    if value in {"y", "yes", "д", "да"}:
        return True
    if value in {"n", "no", "н", "нет"}:
        return False
    return _prompt_yes_no(text, default)


def _parse_user_ids(raw: str) -> tuple[int, ...]:
    values: list[int] = []
    for part in raw.replace(" ", "").split(","):
        if not part:
            continue
        values.append(int(part))
    if not values:
        raise ValueError("At least one Telegram user ID is required")
    return tuple(values)


def _run_command(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def _ensure_ssh_key(private_key_path: Path) -> None:
    if private_key_path.exists() and private_key_path.with_suffix(".pub").exists():
        return

    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    key = asyncssh.generate_private_key("ssh-ed25519")
    private_key_path.write_text(key.export_private_key(format_name="openssh"), encoding="utf-8")
    private_key_path.with_suffix(".pub").write_text(
        key.export_public_key(format_name="openssh"), encoding="utf-8"
    )
    private_key_path.chmod(0o600)
    private_key_path.with_suffix(".pub").chmod(0o644)


def _write_known_hosts(host: str, port: int, known_hosts_path: Path, *, cwd: Path) -> None:
    result = subprocess.run(
        ["ssh-keyscan", "-p", str(port), "-H", host],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    if not result.stdout.strip():
        raise RuntimeError("ssh-keyscan did not return any host key data")
    known_hosts_path.write_text(result.stdout, encoding="utf-8")
    known_hosts_path.chmod(0o644)


async def _bootstrap_mikrotik(
    *,
    config: BootstrapConfig,
    admin_password: str,
    public_key_path: Path,
) -> None:
    remote_pubkey_name = f"{config.bot_username}.pub"
    temporary_password = secrets.token_urlsafe(18)
    bootstrap_script = build_bootstrap_script(
        group_name=config.group_name,
        bot_username=config.bot_username,
        bot_password=temporary_password,
        public_key_filename=remote_pubkey_name,
    )

    async with asyncssh.connect(
        host=config.mikrotik_host,
        port=config.mikrotik_port,
        username=config.admin_username,
        password=admin_password,
        known_hosts=None,
    ) as connection:
        async with connection.start_sftp_client() as sftp:
            await sftp.put(str(public_key_path), remote_pubkey_name)
        result = await connection.run(bootstrap_script, check=False)
        if result.exit_status != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "MikroTik bootstrap failed")


async def _validate_bot_login(config: BootstrapConfig, private_key_path: Path, known_hosts_path: Path) -> None:
    async with asyncssh.connect(
        host=config.mikrotik_host,
        port=config.mikrotik_port,
        username=config.bot_username,
        client_keys=[str(private_key_path)],
        known_hosts=str(known_hosts_path),
    ) as connection:
        result = await connection.run("/ip firewall address-list print count-only", check=False)
        if result.exit_status != 0:
            raise RuntimeError(result.stderr.strip() or "Bot user validation failed")


def _run_compose(project_root: Path) -> None:
    _run_command(["docker", "compose", "up", "-d", "--build"], cwd=project_root)


def _print_summary(config: BootstrapConfig, paths: dict[str, Path]) -> None:
    print("")
    print("Setup complete.")
    print(f"MikroTik host: {config.mikrotik_host}:{config.mikrotik_port}")
    print(f"Bot user: {config.bot_username}")
    print(f".env written to: {paths['env_path']}")
    print(f"SSH key: {paths['private_key_path']}")
    print(f"known_hosts: {paths['known_hosts_path']}")
    print("")
    print("Next command if you want to start manually:")
    print("docker compose up -d --build")


def _collect_config() -> tuple[BootstrapConfig, str]:
    print("Interactive MikroTik Telegram bot setup")
    telegram_bot_token = _prompt("Telegram bot token")
    allowed_telegram_user_ids = _parse_user_ids(
        _prompt("Allowed Telegram user IDs (comma separated)")
    )
    mikrotik_host = _prompt("MikroTik host or IP")
    mikrotik_port = int(_prompt("MikroTik SSH port", "22"))
    admin_username = _prompt("MikroTik admin username", "admin")
    admin_password = getpass("MikroTik admin password: ").strip()
    bot_username = _prompt("Bot MikroTik username", "tg-bot")
    group_name = _prompt("MikroTik group name for bot user", "tg-bot-group")
    compose_project_name = _prompt(
        "Docker Compose project name", "tgbot-manage-addresslist-mikrotik"
    )
    image_name = _prompt("Docker image name", "tgbot-manage-addresslist-mikrotik:local")
    auto_start = _prompt_yes_no("Start docker compose automatically after setup?", True)

    return (
        BootstrapConfig(
            telegram_bot_token=telegram_bot_token,
            allowed_telegram_user_ids=allowed_telegram_user_ids,
            mikrotik_host=mikrotik_host,
            mikrotik_port=mikrotik_port,
            admin_username=admin_username,
            bot_username=bot_username,
            group_name=group_name,
            compose_project_name=compose_project_name,
            image_name=image_name,
            auto_start=auto_start,
        ),
        admin_password,
    )


def run_setup(project_root: Path) -> None:
    config, admin_password = _collect_config()
    paths = config.derived_paths(project_root)

    paths["secrets_dir"].mkdir(parents=True, exist_ok=True)
    _ensure_ssh_key(paths["private_key_path"])
    _write_known_hosts(config.mikrotik_host, config.mikrotik_port, paths["known_hosts_path"], cwd=project_root)
    paths["env_path"].write_text(build_env_content(config), encoding="utf-8")

    asyncio.run(
        _bootstrap_mikrotik(
            config=config,
            admin_password=admin_password,
            public_key_path=paths["public_key_path"],
        )
    )
    asyncio.run(
        _validate_bot_login(
            config=config,
            private_key_path=paths["private_key_path"],
            known_hosts_path=paths["known_hosts_path"],
        )
    )

    if config.auto_start:
        _run_compose(project_root)

    _print_summary(config, paths)


def main() -> None:
    try:
        run_setup(Path(__file__).resolve().parents[2])
    except KeyboardInterrupt:
        print("\nSetup cancelled by user.", file=sys.stderr)
        raise SystemExit(130) from None
    except Exception as exc:
        print(f"\nSetup failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
