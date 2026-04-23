# AGENTS.md

## Purpose

This repository hosts a Telegram bot that manages MikroTik firewall address lists over SSH.

## Project Rules

- Keep secrets out of git. Never commit real Telegram tokens, MikroTik passwords, hostnames, usernames, or allowed user IDs.
- All runtime configuration must come from environment variables.
- Prefer small, focused modules over large files.
- When touching Docker or GitHub workflows, preserve private-repo compatibility and GHCR publishing.

## Architecture Notes

- `src/tgbot_manage_addresslist/settings.py` contains environment-driven settings.
- `src/tgbot_manage_addresslist/logic.py` contains IP parsing and address-list business logic.
- `src/tgbot_manage_addresslist/mikrotik.py` contains SSH command execution and RouterOS output parsing.
- `src/tgbot_manage_addresslist/telegram_bot.py` contains Telegram handlers and FSM states.

## Agent Expectations

- Verify behavior with a real bot run or another direct manual check before claiming the task is complete.
- If a command can delete MikroTik data, require an explicit confirmation step in the bot flow.
- Keep user-facing messages short and explicit, especially for partial-success reports.
