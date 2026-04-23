# Telegram MikroTik Address List Bot

Telegram bot for managing MikroTik firewall `address-list` entries over SSH.

## Features

- button-first Telegram interface with inline keyboards
- accepts a list of IP addresses from Telegram
- shows existing address-lists fetched from MikroTik
- adds valid IPs into an existing or newly named address-list
- reports invalid IPs, duplicates, and MikroTik-side errors separately
- deletes a full address-list with confirmation
- rejects stale buttons, wrong-step text input, and mixed dialog actions with explicit warnings
- restricts access to an allowlist of Telegram user IDs
- runs in Docker
- publishes a container image to `ghcr.io` from GitHub Actions

## Stack

- Python 3.12
- `aiogram` for Telegram bot flows
- `asyncssh` for SSH access to MikroTik
- Docker / Docker Compose

## Configuration

Copy `.env.example` to `.env` and adjust values.

Required variables:

- `TG_BOT_TOKEN`
- `ALLOWED_TELEGRAM_USER_IDS`
- `MIKROTIK_HOST`
- `MIKROTIK_PORT`
- `MIKROTIK_USERNAME`
- `MIKROTIK_PASSWORD`

Optional variables:

- `LOG_LEVEL` - defaults to `INFO`

Create a separate MikroTik user for the bot and put that login/password into `.env`. Do not use your main admin account for day-to-day bot work.

## Local Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
python -m tgbot_manage_addresslist
```

## Manual Verification

- start the bot and confirm the Telegram menu shows `/start`, `/delete_list`, `/cancel`, and `/help`
- send `/start` and verify the bot shows the inline main menu
- choose `Добавить IP`, send one or more test IP addresses, and confirm the bot offers existing address-lists plus `Создать новый address-list`
- during add flow, send random text when the bot expects a button and verify it answers with a short explicit warning
- during delete flow, press an old button from a previous screen and verify the bot reports that the menu is no longer актуально
- send `/delete_list` and confirm the bot asks for explicit deletion confirmation before removing a list

## Docker Run

```bash
cp .env.example .env
docker compose up --build -d
docker compose logs -f tgbot_mikrotik
```

The image name is already fixed in [compose.yaml](/opt/projects/bot_add_ip_mikrotik/compose.yaml), so nothing extra is needed in `.env` for Docker Compose.

## Bot Commands

- `/start` - open the main menu
- `/delete_list` - delete a full address-list after confirmation
- `/cancel` - cancel the active dialog
- `/help` - show help

## RouterOS Commands Used

- list address-lists: `/ip firewall address-list print terse without-paging`
- add entry: `/ip firewall address-list add list="NAME" address="IP"`
- delete full list: `/ip firewall address-list remove [find list="NAME"]`

## Security Notes

- Keep the repository private while bootstrapping.
- Do not commit `.env`.
- Create a dedicated MikroTik user for the bot.
- Give that user only the rights needed to manage `address-list`.
