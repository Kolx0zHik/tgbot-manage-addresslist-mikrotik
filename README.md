# Telegram MikroTik Address List Bot

Telegram bot for managing MikroTik firewall `address-list` entries over SSH.

## Features

- accepts a list of IP addresses from Telegram
- shows existing address-lists fetched from MikroTik
- adds valid IPs into an existing or newly named address-list
- reports invalid IPs, duplicates, and MikroTik-side errors separately
- deletes a full address-list with confirmation
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

Mount your SSH private key and `known_hosts` file into the container, for example:

- `./secrets/id_ed25519:/run/secrets/mikrotik_ssh_key:ro`
- `./secrets/known_hosts:/run/secrets/known_hosts:ro`

Required variables:

- `TG_BOT_TOKEN`
- `ALLOWED_TELEGRAM_USER_IDS`
- `MIKROTIK_HOST`
- `MIKROTIK_USERNAME`
- `MIKROTIK_SSH_PRIVATE_KEY_PATH`
- `MIKROTIK_SSH_KNOWN_HOSTS_PATH`

## Local Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
pytest
python -m tgbot_manage_addresslist
```

## Guided Setup

The easiest way is the interactive installer:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python setup_bot.py
```

The installer asks for Telegram and MikroTik values, generates an SSH key, writes `.env`, creates a dedicated MikroTik user, imports the public key for that user, records `known_hosts`, and can optionally start `docker compose` for you.

## Docker Run

```bash
cp .env.example .env
docker compose up --build -d
docker compose logs -f bot
```

## Bot Commands

- `/start` - begin adding IP addresses
- `/delete_list` - delete a full address-list after confirmation
- `/cancel` - cancel the active dialog
- `/help` - show help

## RouterOS Commands Used

- list address-lists: `/ip firewall address-list print terse without-paging`
- add entry: `/ip firewall address-list add list="NAME" address="IP"`
- delete full list: `/ip firewall address-list remove [find list="NAME"]`

## Security Notes

- Keep the repository private while bootstrapping.
- Do not commit `.env`, SSH keys, or host fingerprints.
- Restrict the SSH key on the MikroTik side to the minimum required account.
- Keep `known_hosts` validation enabled in production.
