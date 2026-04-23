# Inline Safe Flows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the loose Telegram conversation handlers with strict inline-driven flows that reject stale, invalid, and cross-flow user actions.

**Architecture:** Keep the existing bot module but introduce explicit flow/session guards, structured callback payloads, and reusable screen-rendering helpers for menu, add, and delete steps. Preserve the existing MikroTik and business-logic modules so the behavior change stays localized to the Telegram layer.

**Tech Stack:** Python 3.12, aiogram, asyncssh

---

### Task 1: Model safe bot flow state

**Files:**
- Modify: `src/tgbot_manage_addresslist/telegram_bot.py`

- [ ] Define explicit flow names, step names, and callback/session helpers for menu, add, and delete scenarios.
- [ ] Add guard helpers that validate authorization, active session id, active step, and required FSM data before processing callbacks.
- [ ] Keep error responses short and user-facing.

### Task 2: Rebuild button-first screens

**Files:**
- Modify: `src/tgbot_manage_addresslist/telegram_bot.py`

- [ ] Add reusable keyboards for the main menu, list selection, confirmation, and navigation buttons.
- [ ] Render the add flow through dedicated screens instead of implicit state jumps.
- [ ] Render the delete flow through dedicated screens with an explicit destructive warning.

### Task 3: Handle invalid and stale actions

**Files:**
- Modify: `src/tgbot_manage_addresslist/telegram_bot.py`

- [ ] Reject callbacks from stale menus, wrong steps, missing state, or mixed flows with short Telegram alerts.
- [ ] Reject text input that arrives during delete or menu flows with a clear “what is expected now” response.
- [ ] Add a fallback callback handler so unknown callback payloads are handled explicitly.

### Task 4: Refresh docs and commands

**Files:**
- Modify: `README.md`
- Modify: `src/tgbot_manage_addresslist/app.py`

- [ ] Keep bot commands compatible with the new button-first menu.
- [ ] Update README manual verification notes to cover stale-button and wrong-step checks.

### Task 5: Verify and publish

**Files:**
- Modify: `.github/workflows/docker-publish.yml`

- [ ] Run syntax and import verification with `python3`.
- [ ] Perform a direct manual check of bot flow behavior using a small local harness or a real bot-safe run.
- [ ] Extend image publishing so a `test` tag can be pushed from the feature branch without affecting `latest` on `main`.
