# MikroTik Telegram Bot Design

## Goal

Build a private Telegram bot that lets authorized users add IP addresses into MikroTik firewall address-lists and delete a full address-list with confirmation.

## Scope

- Telegram bot with allowlisted users only
- SSH key based connection to MikroTik
- fetch existing address-lists from MikroTik at runtime
- add valid IPs into a chosen or new list
- partial success reporting for invalid or duplicate entries
- delete a full list after an explicit confirmation step
- Docker-based runtime
- private GitHub repository with GHCR image publishing

## Architecture

- `aiogram` handles Telegram polling, FSM, commands, and inline keyboards.
- `asyncssh` handles command execution on MikroTik.
- A validation module extracts candidate IP tokens and classifies valid and invalid values.
- A service layer translates validated input into MikroTik operations and returns structured result summaries.

## User Flows

### Add IPs

1. User sends `/start`.
2. Bot checks the Telegram user ID against the allowlist.
3. Bot asks for IP addresses.
4. User sends IPs separated by spaces, commas, or new lines.
5. Bot validates input and fetches existing address-lists from MikroTik.
6. User chooses an existing list or presses create-new.
7. Bot adds valid IPs one by one.
8. Bot sends a final report with added IPs, duplicates, invalid inputs, and errors.

### Delete Full Address-List

1. User sends `/delete_list`.
2. Bot checks authorization.
3. Bot fetches existing address-lists from MikroTik.
4. User chooses a list.
5. Bot asks for confirmation with inline buttons.
6. Bot deletes all entries for the chosen list.
7. Bot reports how many entries were removed.

## Safety

- No credentials are stored in git.
- The bot requires explicit Telegram allowlisting.
- Delete operations require a confirmation step.
- SSH host verification is performed through a mounted `known_hosts` file.

## Delivery Artifacts

- `AGENTS.md`
- Python package in `src/`
- tests in `tests/`
- Dockerfile and Compose file
- GitHub Actions workflow for GHCR publishing
- private GitHub repository bootstrap
