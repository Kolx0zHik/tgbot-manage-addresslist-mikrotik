# MikroTik Telegram Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a private Dockerized Telegram bot that manages MikroTik address-lists over SSH.

**Architecture:** The bot uses `aiogram` FSM handlers for Telegram conversations, a small service layer for address-list operations, and an async SSH client for RouterOS command execution. Validation and RouterOS parsing stay in isolated modules so they can be verified independently and exercised through manual bot runs.

**Tech Stack:** Python 3.12, aiogram, asyncssh, Docker, GitHub Actions, GHCR

---

### Task 1: Validation module

**Files:**
- Create: `src/tgbot_manage_addresslist/validation/ip_lists.py`

- [ ] Implement extraction, validation, and deduplication for IP input.
- [ ] Verify the parser manually from the bot flow with valid, duplicate, and invalid values.
- [ ] Implement the validation module with minimal behavior.
- [ ] Re-check the bot flow and confirm the parsed result matches expectations.

### Task 2: MikroTik parsing and command formatting

**Files:**
- Create: `src/tgbot_manage_addresslist/mikrotik/client.py`

- [ ] Implement parsing of `list=` values and escaping for RouterOS strings.
- [ ] Verify the generated commands and parsed list names with representative RouterOS output samples.
- [ ] Implement parsing and command-building helpers.
- [ ] Re-run the same samples and confirm the output is stable.

### Task 3: Service layer

**Files:**
- Create: `src/tgbot_manage_addresslist/services/address_list_manager.py`

- [ ] Implement partial-success add behavior and delete behavior.
- [ ] Exercise add and delete flows manually with duplicate, invalid, and successful inputs.
- [ ] Implement the service layer with structured result objects.
- [ ] Confirm the resulting Telegram messages match the expected summaries.

### Task 4: Telegram bot integration

**Files:**
- Create: `src/tgbot_manage_addresslist/bot/handlers.py`
- Create: `src/tgbot_manage_addresslist/bot/keyboards.py`
- Create: `src/tgbot_manage_addresslist/bot/states.py`
- Create: `src/tgbot_manage_addresslist/app.py`

- [ ] Add FSM states and inline keyboards for add and delete flows.
- [ ] Implement authorization checks and command handlers.
- [ ] Wire service objects into bot startup.
- [ ] Perform a syntax-level import check.

### Task 5: Packaging and operations

**Files:**
- Create: `Dockerfile`
- Create: `compose.yaml`
- Create: `.github/workflows/docker-publish.yml`
- Create: `.env.example`
- Create: `README.md`
- Create: `AGENTS.md`

- [ ] Add Docker runtime files and GHCR workflow.
- [ ] Document secret handling and container startup.
- [ ] Verify the container build succeeds and the bot starts cleanly.
- [ ] Initialize git, create a private GitHub repository, and push the project.
