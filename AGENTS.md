# AGENTS.md

## Purpose

This repository hosts a Telegram bot that manages MikroTik firewall address lists over SSH.

## Project Rules

- Keep secrets out of git. Never commit real Telegram tokens, SSH private keys, hostnames, usernames, or allowed user IDs.
- All runtime configuration must come from environment variables or mounted secret files.
- Prefer small, focused modules over large files.
- Cover core business logic with tests before extending integrations.
- When touching Docker or GitHub workflows, preserve private-repo compatibility and GHCR publishing.

## Architecture Notes

- `src/tgbot_manage_addresslist/config/` contains environment-driven settings.
- `src/tgbot_manage_addresslist/validation/` contains IP parsing and validation.
- `src/tgbot_manage_addresslist/mikrotik/` contains SSH command execution and RouterOS output parsing.
- `src/tgbot_manage_addresslist/services/` contains business logic for address-list management.
- `src/tgbot_manage_addresslist/bot/` contains Telegram handlers, keyboards, and FSM states.

## Agent Expectations

- Verify behavior with tests before claiming the task is complete.
- If a command can delete MikroTik data, require an explicit confirmation step in the bot flow.
- Keep user-facing messages short and explicit, especially for partial-success reports.
