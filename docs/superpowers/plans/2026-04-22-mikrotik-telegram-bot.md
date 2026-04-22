# MikroTik Telegram Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a private Dockerized Telegram bot that manages MikroTik address-lists over SSH.

**Architecture:** The bot uses `aiogram` FSM handlers for Telegram conversations, a small service layer for address-list operations, and an async SSH client for RouterOS command execution. Validation and RouterOS parsing stay in isolated modules so they can be tested without a live router.

**Tech Stack:** Python 3.12, aiogram, asyncssh, pytest, Docker, GitHub Actions, GHCR

---

### Task 1: Validation module

**Files:**
- Create: `src/tgbot_manage_addresslist/validation/ip_lists.py`
- Test: `tests/test_validation.py`

- [ ] Write failing tests for extracting, validating, and deduplicating IP input.
- [ ] Run the validation tests and confirm failure.
- [ ] Implement the validation module with minimal behavior.
- [ ] Re-run validation tests and confirm pass.

### Task 2: MikroTik parsing and command formatting

**Files:**
- Create: `src/tgbot_manage_addresslist/mikrotik/client.py`
- Test: `tests/test_mikrotik_client.py`

- [ ] Write failing tests for parsing `list=` values and escaping RouterOS strings.
- [ ] Run the parser tests and confirm failure.
- [ ] Implement parsing and command-building helpers.
- [ ] Re-run parser tests and confirm pass.

### Task 3: Service layer

**Files:**
- Create: `src/tgbot_manage_addresslist/services/address_list_manager.py`
- Test: `tests/test_address_list_manager.py`

- [ ] Write failing tests for partial-success add behavior and delete behavior.
- [ ] Run the service tests and confirm failure.
- [ ] Implement the service layer with structured result objects.
- [ ] Re-run service tests and confirm pass.

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
- [ ] Verify tests and build succeed locally.
- [ ] Initialize git, create a private GitHub repository, and push the project.
