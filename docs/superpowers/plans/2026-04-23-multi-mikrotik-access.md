# Multi-MikroTik Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add env-only support for multiple MikroTik routers with admin-all access, per-user router visibility, and router-first Telegram navigation.

**Architecture:** Keep single-router RouterOS parsing and address-list mutation logic intact, but add a router registry in settings and application wiring so each operation resolves through a selected `mikrotik_id`. Rework the Telegram FSM to start from router selection, carry selected router context through the add/delete flows, and preserve the current stale-button, `/start`, and explicit-delete-confirmation safeguards.

**Tech Stack:** Python 3.12, aiogram, asyncssh, pytest, Docker

---

### Task 1: Add multi-MikroTik settings parsing

**Files:**
- Modify: `src/tgbot_manage_addresslist/settings.py`
- Create: `tests/test_settings.py`

- [ ] **Step 1: Write the failing settings tests**

```python
from __future__ import annotations

import pytest

from tgbot_manage_addresslist.settings import Settings


def test_settings_from_env_parses_multiple_mikrotiks(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "TG_BOT_TOKEN": "token",
        "ALLOWED_TELEGRAM_USER_IDS": "100,200,300",
        "ADMIN_TELEGRAM_USER_IDS": "100",
        "MIKROTIK_IDS": "mt1,mt2",
        "MIKROTIK_MT1_NAME": "Office",
        "MIKROTIK_MT1_HOST": "192.0.2.10",
        "MIKROTIK_MT1_PORT": "22",
        "MIKROTIK_MT1_USERNAME": "office-bot",
        "MIKROTIK_MT1_PASSWORD": "secret-1",
        "MIKROTIK_MT2_NAME": "Warehouse",
        "MIKROTIK_MT2_HOST": "192.0.2.20",
        "MIKROTIK_MT2_PORT": "2222",
        "MIKROTIK_MT2_USERNAME": "warehouse-bot",
        "MIKROTIK_MT2_PASSWORD": "secret-2",
        "USER_MIKROTIK_ACCESS_200": "mt1",
        "USER_MIKROTIK_ACCESS_300": "mt2",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    settings = Settings.from_env()

    assert settings.admin_telegram_user_ids == (100,)
    assert tuple(item.id for item in settings.mikrotiks) == ("mt1", "mt2")
    assert settings.mikrotiks_by_id["mt1"].name == "Office"
    assert settings.mikrotiks_by_id["mt2"].port == 2222
    assert settings.user_mikrotik_access == {200: ("mt1",), 300: ("mt2",)}


def test_settings_from_env_rejects_regular_user_without_access(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "TG_BOT_TOKEN": "token",
        "ALLOWED_TELEGRAM_USER_IDS": "100,200",
        "ADMIN_TELEGRAM_USER_IDS": "100",
        "MIKROTIK_IDS": "mt1",
        "MIKROTIK_MT1_NAME": "Office",
        "MIKROTIK_MT1_HOST": "192.0.2.10",
        "MIKROTIK_MT1_PORT": "22",
        "MIKROTIK_MT1_USERNAME": "office-bot",
        "MIKROTIK_MT1_PASSWORD": "secret-1",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(ValueError, match="must have at least one assigned MikroTik"):
        Settings.from_env()


def test_settings_from_env_rejects_unknown_mikrotik_in_user_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {
        "TG_BOT_TOKEN": "token",
        "ALLOWED_TELEGRAM_USER_IDS": "100,200",
        "ADMIN_TELEGRAM_USER_IDS": "100",
        "MIKROTIK_IDS": "mt1",
        "MIKROTIK_MT1_NAME": "Office",
        "MIKROTIK_MT1_HOST": "192.0.2.10",
        "MIKROTIK_MT1_PORT": "22",
        "MIKROTIK_MT1_USERNAME": "office-bot",
        "MIKROTIK_MT1_PASSWORD": "secret-1",
        "USER_MIKROTIK_ACCESS_200": "mt2",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(ValueError, match="Unknown MikroTik id"):
        Settings.from_env()
```

- [ ] **Step 2: Run the settings tests to verify RED**

Run: `pytest tests/test_settings.py -v`
Expected: FAIL because `Settings` does not yet expose `admin_telegram_user_ids`, `mikrotiks`, `mikrotiks_by_id`, or `user_mikrotik_access`.

- [ ] **Step 3: Implement multi-router settings parsing**

```python
from dataclasses import dataclass
import os


@dataclass(frozen=True, slots=True)
class MikroTikSettings:
    id: str
    name: str
    host: str
    port: int
    username: str
    password: str


def _parse_csv_items(raw: str, *, field_name: str) -> tuple[str, ...]:
    items = tuple(item.strip() for item in raw.split(",") if item.strip())
    if not items:
        raise ValueError(f"{field_name} must contain at least one value")
    return items


def _parse_mikrotiks() -> tuple[MikroTikSettings, ...]:
    mikrotik_ids = tuple(item.lower() for item in _parse_csv_items(_require_env("MIKROTIK_IDS"), field_name="MIKROTIK_IDS"))
    routers: list[MikroTikSettings] = []
    for mikrotik_id in mikrotik_ids:
        env_id = mikrotik_id.upper()
        routers.append(
            MikroTikSettings(
                id=mikrotik_id,
                name=_require_env(f"MIKROTIK_{env_id}_NAME"),
                host=_require_env(f"MIKROTIK_{env_id}_HOST"),
                port=int(os.getenv(f"MIKROTIK_{env_id}_PORT", "22")),
                username=_require_env(f"MIKROTIK_{env_id}_USERNAME"),
                password=_require_env(f"MIKROTIK_{env_id}_PASSWORD"),
            )
        )
    return tuple(routers)


def _parse_user_mikrotik_access(
    *,
    allowed_user_ids: tuple[int, ...],
    admin_user_ids: tuple[int, ...],
    known_mikrotik_ids: set[str],
) -> dict[int, tuple[str, ...]]:
    access: dict[int, tuple[str, ...]] = {}
    for user_id in allowed_user_ids:
        if user_id in admin_user_ids:
            continue
        raw = _require_env(f"USER_MIKROTIK_ACCESS_{user_id}")
        mikrotik_ids = tuple(item.lower() for item in _parse_csv_items(raw, field_name=f"USER_MIKROTIK_ACCESS_{user_id}"))
        unknown_ids = [item for item in mikrotik_ids if item not in known_mikrotik_ids]
        if unknown_ids:
            raise ValueError(f"Unknown MikroTik id for user {user_id}: {', '.join(unknown_ids)}")
        access[user_id] = mikrotik_ids
    return access
```

Add these fields to `Settings`:

```python
admin_telegram_user_ids: tuple[int, ...]
mikrotiks: tuple[MikroTikSettings, ...]
mikrotiks_by_id: dict[str, MikroTikSettings]
user_mikrotik_access: dict[int, tuple[str, ...]]
```

Populate them in `from_env()` and validate that admins are a subset of allowed users.

- [ ] **Step 4: Run the settings tests to verify GREEN**

Run: `pytest tests/test_settings.py -v`
Expected: PASS for the new settings cases.

- [ ] **Step 5: Commit**

```bash
git add src/tgbot_manage_addresslist/settings.py tests/test_settings.py
git commit -m "feat: parse multi-mikrotik settings"
```

### Task 2: Add router-aware access resolution and service routing

**Files:**
- Modify: `src/tgbot_manage_addresslist/logic.py`
- Modify: `src/tgbot_manage_addresslist/app.py`
- Create: `tests/test_address_list_manager.py`

- [ ] **Step 1: Write the failing service and access tests**

```python
from __future__ import annotations

import pytest

from tgbot_manage_addresslist.logic import AddressListManager, AddressListService, UserAccessResolver
from tgbot_manage_addresslist.settings import MikroTikSettings, Settings


class StubClient:
    def __init__(self, *, address_lists: list[str] | None = None) -> None:
        self.address_lists = address_lists or []

    async def fetch_address_lists(self) -> list[str]:
        return self.address_lists

    async def add_address(self, list_name: str, ip_address: str) -> str | None:
        return None

    async def delete_address_list(self, list_name: str) -> int:
        return 1


def make_settings() -> Settings:
    mikrotiks = (
        MikroTikSettings(id="mt1", name="Office", host="192.0.2.10", port=22, username="u1", password="p1"),
        MikroTikSettings(id="mt2", name="Warehouse", host="192.0.2.20", port=22, username="u2", password="p2"),
    )
    return Settings(
        telegram_bot_token="token",
        allowed_telegram_user_ids=(100, 200, 300),
        admin_telegram_user_ids=(100,),
        mikrotiks=mikrotiks,
        mikrotiks_by_id={item.id: item for item in mikrotiks},
        user_mikrotik_access={200: ("mt1",), 300: ("mt2",)},
        log_level="INFO",
    )


def test_user_access_resolver_returns_all_routers_for_admin() -> None:
    resolver = UserAccessResolver(make_settings())

    visible = resolver.visible_mikrotiks_for(100)

    assert [item.id for item in visible] == ["mt1", "mt2"]


def test_user_access_resolver_returns_assigned_routers_for_regular_user() -> None:
    resolver = UserAccessResolver(make_settings())

    visible = resolver.visible_mikrotiks_for(200)

    assert [item.id for item in visible] == ["mt1"]


@pytest.mark.asyncio
async def test_address_list_service_routes_calls_by_mikrotik_id() -> None:
    service = AddressListService(
        managers_by_id={
            "mt1": AddressListManager(StubClient(address_lists=["office-list"])),
            "mt2": AddressListManager(StubClient(address_lists=["warehouse-list"])),
        }
    )

    office_lists = await service.fetch_address_lists("mt1")
    warehouse_lists = await service.fetch_address_lists("mt2")

    assert office_lists == ["office-list"]
    assert warehouse_lists == ["warehouse-list"]
```

- [ ] **Step 2: Run the service tests to verify RED**

Run: `pytest tests/test_address_list_manager.py -v`
Expected: FAIL because `AddressListService` and `UserAccessResolver` do not exist yet.

- [ ] **Step 3: Implement router-aware service and access helpers**

```python
class AddressListService:
    def __init__(self, managers_by_id: dict[str, AddressListManager]) -> None:
        self._managers_by_id = managers_by_id

    def _manager_for(self, mikrotik_id: str) -> AddressListManager:
        try:
            return self._managers_by_id[mikrotik_id]
        except KeyError as exc:
            raise ValueError(f"Unknown MikroTik id: {mikrotik_id}") from exc

    async def fetch_address_lists(self, mikrotik_id: str) -> list[str]:
        return await self._manager_for(mikrotik_id).fetch_address_lists()

    async def add_ips(
        self,
        mikrotik_id: str,
        list_name: str,
        valid_ips: list[str],
        invalid_tokens: list[str],
    ) -> AddOperationResult:
        return await self._manager_for(mikrotik_id).add_ips(list_name, valid_ips, invalid_tokens)

    async def delete_list(self, mikrotik_id: str, list_name: str) -> DeleteOperationResult:
        return await self._manager_for(mikrotik_id).delete_list(list_name)


class UserAccessResolver:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def is_allowed(self, user_id: int) -> bool:
        return user_id in self._settings.allowed_telegram_user_ids

    def is_admin(self, user_id: int) -> bool:
        return user_id in self._settings.admin_telegram_user_ids

    def visible_mikrotiks_for(self, user_id: int) -> tuple[MikroTikSettings, ...]:
        if self.is_admin(user_id):
            return self._settings.mikrotiks
        allowed_ids = self._settings.user_mikrotik_access.get(user_id, ())
        return tuple(self._settings.mikrotiks_by_id[item_id] for item_id in allowed_ids)

    def can_access(self, user_id: int, mikrotik_id: str) -> bool:
        return mikrotik_id in {item.id for item in self.visible_mikrotiks_for(user_id)}
```

In `app.py`, build manager instances for all configured routers:

```python
managers_by_id = {
    item.id: AddressListManager(MikroTikSSHClient(item))
    for item in settings.mikrotiks
}
service = AddressListService(managers_by_id)
access_resolver = UserAccessResolver(settings)
```

- [ ] **Step 4: Run the new tests to verify GREEN**

Run: `pytest tests/test_address_list_manager.py -v`
Expected: PASS for access resolution and per-router service routing.

- [ ] **Step 5: Commit**

```bash
git add src/tgbot_manage_addresslist/logic.py src/tgbot_manage_addresslist/app.py tests/test_address_list_manager.py
git commit -m "feat: route access-list operations by mikrotik"
```

### Task 3: Adapt the SSH client and startup wiring for router registries

**Files:**
- Modify: `src/tgbot_manage_addresslist/mikrotik.py`
- Modify: `src/tgbot_manage_addresslist/app.py`
- Modify: `tests/test_mikrotik_client.py`
- Create: `tests/test_app.py`

- [ ] **Step 1: Write the failing startup and SSH tests**

```python
from __future__ import annotations

import pytest

from tgbot_manage_addresslist.mikrotik import CommandResult, MikroTikSSHClient
from tgbot_manage_addresslist.settings import MikroTikSettings


class StubMikroTikSSHClient(MikroTikSSHClient):
    def __init__(self, result: CommandResult) -> None:
        super().__init__(
            MikroTikSettings(
                id="mt1",
                name="Office",
                host="router",
                port=22,
                username="user",
                password="pass",
            )
        )
        self._result = result

    async def _run(self, command: str) -> CommandResult:
        return self._result


@pytest.mark.asyncio
async def test_fetch_address_lists_uses_router_specific_settings() -> None:
    client = StubMikroTikSSHClient(
        CommandResult(
            stdout='0 list="office-list" address=192.0.2.10',
            stderr="",
            exit_status=0,
        )
    )

    result = await client.fetch_address_lists()

    assert result == ["office-list"]
```

Also add an application-level test that startup can build a registry and continue when one check fails:

```python
@pytest.mark.asyncio
async def test_startup_health_check_logs_each_router(monkeypatch, caplog) -> None:
    ...
```

- [ ] **Step 2: Run the relevant tests to verify RED**

Run: `pytest tests/test_mikrotik_client.py tests/test_app.py -v`
Expected: FAIL because the SSH client constructor still depends on the old single-router `Settings` shape and `tests/test_app.py` does not exist yet.

- [ ] **Step 3: Implement router-specific SSH construction and health checks**

```python
class MikroTikSSHClient:
    def __init__(self, settings: MikroTikSettings) -> None:
        self._settings = settings

    async def _run(self, command: str) -> CommandResult:
        logger.info(
            "Connecting to MikroTik over SSH: id=%s name=%s host=%s port=%s user=%s",
            self._settings.id,
            self._settings.name,
            self._settings.host,
            self._settings.port,
            self._settings.username,
        )
        ...
```

In `app.py`, extract a helper:

```python
async def log_startup_health_checks(
    service: AddressListService,
    mikrotiks: tuple[MikroTikSettings, ...],
) -> None:
    for mikrotik in mikrotiks:
        try:
            address_lists = await service.fetch_address_lists(mikrotik.id)
        except Exception:
            logger.exception("Initial MikroTik SSH check failed for id=%s name=%s", mikrotik.id, mikrotik.name)
        else:
            logger.info(
                "Initial MikroTik SSH check succeeded for id=%s name=%s found=%s",
                mikrotik.id,
                mikrotik.name,
                len(address_lists),
            )
```

- [ ] **Step 4: Run the SSH and app tests to verify GREEN**

Run: `pytest tests/test_mikrotik_client.py tests/test_app.py -v`
Expected: PASS for router-specific SSH client construction and per-router startup logging.

- [ ] **Step 5: Commit**

```bash
git add src/tgbot_manage_addresslist/mikrotik.py src/tgbot_manage_addresslist/app.py tests/test_mikrotik_client.py tests/test_app.py
git commit -m "feat: wire ssh clients for multiple mikrotiks"
```

### Task 4: Rework Telegram navigation to be router-first

**Files:**
- Modify: `src/tgbot_manage_addresslist/telegram_bot.py`
- Create: `tests/test_telegram_bot.py`
- Modify: `tests/test_add_flow_state.py`

- [ ] **Step 1: Write the failing Telegram flow tests**

```python
from __future__ import annotations

import pytest

from tgbot_manage_addresslist.telegram_bot import (
    DATA_SELECTED_MIKROTIK_ID,
    DATA_SELECTED_MIKROTIK_NAME,
    _build_mikrotik_selection_keyboard,
    _show_mikrotik_selection_menu,
    _show_mikrotik_actions_menu,
)


def test_build_mikrotik_selection_keyboard_contains_visible_routers() -> None:
    keyboard = _build_mikrotik_selection_keyboard(
        [("mt1", "Office"), ("mt2", "Warehouse")],
        "deadbeef",
    )

    button_texts = [
        button.text
        for row in keyboard.inline_keyboard
        for button in row
    ]

    assert button_texts == ["Office", "Warehouse", "Помощь"]


@pytest.mark.asyncio
async def test_show_mikrotik_actions_menu_persists_selected_router(monkeypatch) -> None:
    ...
    await _show_mikrotik_actions_menu(
        event,
        state,
        mikrotik_id="mt1",
        mikrotik_name="Office",
    )

    data = await state.get_data()
    assert data[DATA_SELECTED_MIKROTIK_ID] == "mt1"
    assert data[DATA_SELECTED_MIKROTIK_NAME] == "Office"
```

Add flow tests should also assert that confirmation text includes the selected router name and that a stale router callback is rejected.

- [ ] **Step 2: Run the Telegram tests to verify RED**

Run: `pytest tests/test_telegram_bot.py tests/test_add_flow_state.py -v`
Expected: FAIL because router-selection helpers, router state keys, and router action menu flow do not exist yet.

- [ ] **Step 3: Implement router-first bot state and screens**

```python
DATA_SELECTED_MIKROTIK_ID = "selected_mikrotik_id"
DATA_SELECTED_MIKROTIK_NAME = "selected_mikrotik_name"

ACTION_SELECT_MIKROTIK = "mselect"
ACTION_ROUTER_ADD = "radd"
ACTION_ROUTER_DELETE = "rdel"
ACTION_ROUTER_BACK = "rback"


class BotFlow(StatesGroup):
    mikrotik_selection = State()
    mikrotik_actions = State()
    add_waiting_list_choice = State()
    add_waiting_new_list_name = State()
    add_waiting_ip_input = State()
    add_waiting_confirmation = State()
    delete_waiting_list_choice = State()
    delete_waiting_confirmation = State()


def _build_mikrotik_selection_keyboard(
    mikrotiks: list[tuple[str, str]],
    session_id: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for mikrotik_id, mikrotik_name in mikrotiks:
        builder.button(
            text=mikrotik_name,
            callback_data=_encode_callback_data(ACTION_SELECT_MIKROTIK, session_id, mikrotik_id),
        )
    builder.button(text="Помощь", callback_data=_encode_callback_data(ACTION_HELP, session_id))
    builder.adjust(1)
    return builder.as_markup()
```

Add router-specific screens:

```python
async def _show_mikrotik_selection_menu(...): ...
async def _show_mikrotik_actions_menu(...): ...
```

Then update:
- `_reset_to_menu()` to show visible routers instead of add/delete actions
- authorization checks to use `UserAccessResolver`
- add/delete flow entry points to require selected router context
- result and confirmation messages to include `mikrotik_name`
- back navigation so router action menu returns to router list

- [ ] **Step 4: Run the Telegram tests to verify GREEN**

Run: `pytest tests/test_telegram_bot.py tests/test_add_flow_state.py -v`
Expected: PASS for router selection, persisted router context, stale callback handling, and router-specific add/delete messaging.

- [ ] **Step 5: Commit**

```bash
git add src/tgbot_manage_addresslist/telegram_bot.py tests/test_telegram_bot.py tests/test_add_flow_state.py
git commit -m "feat: add router-first telegram navigation"
```

### Task 5: Update application composition and command/menu behavior

**Files:**
- Modify: `src/tgbot_manage_addresslist/app.py`
- Modify: `src/tgbot_manage_addresslist/telegram_bot.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Write the failing composition tests**

```python
from __future__ import annotations

from tgbot_manage_addresslist.app import build_dependencies


def test_build_dependencies_creates_service_and_access_resolver(settings) -> None:
    deps = build_dependencies(settings)

    assert set(deps.address_list_service._managers_by_id) == {"mt1", "mt2"}
    assert deps.user_access_resolver.is_admin(100)
```

- [ ] **Step 2: Run the application tests to verify RED**

Run: `pytest tests/test_app.py -v`
Expected: FAIL because `build_dependencies()` and the new dependency fields do not exist yet.

- [ ] **Step 3: Implement dependency assembly**

```python
@dataclass(frozen=True, slots=True)
class BotDependencies:
    settings: Settings
    address_list_service: AddressListService
    user_access_resolver: UserAccessResolver


def build_dependencies(settings: Settings) -> BotDependencies:
    managers_by_id = {
        item.id: AddressListManager(MikroTikSSHClient(item))
        for item in settings.mikrotiks
    }
    return BotDependencies(
        settings=settings,
        address_list_service=AddressListService(managers_by_id),
        user_access_resolver=UserAccessResolver(settings),
    )
```

Update `run()` to use `build_dependencies(settings)` and pass the richer dependencies into `register_handlers`.

- [ ] **Step 4: Run the application tests to verify GREEN**

Run: `pytest tests/test_app.py -v`
Expected: PASS for dependency composition and startup wiring.

- [ ] **Step 5: Commit**

```bash
git add src/tgbot_manage_addresslist/app.py src/tgbot_manage_addresslist/telegram_bot.py tests/test_app.py
git commit -m "refactor: centralize multi-mikrotik dependencies"
```

### Task 6: Refresh docs, env examples, and manual verification notes

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Write a failing docs verification checklist**

```text
Missing until updated:
- .env.example still shows single-router MIKROTIK_HOST/PORT/USERNAME/PASSWORD
- README configuration section still documents single-router setup
- README bot flow still describes action-first navigation
- README manual verification does not mention admin-all vs user-assigned router visibility
```

- [ ] **Step 2: Verify the docs are currently stale**

Run: `grep -n "MIKROTIK_HOST\\|router-first\\|ADMIN_TELEGRAM_USER_IDS" -n .env.example README.md`
Expected: output shows single-router variables and no multi-router admin config yet.

- [ ] **Step 3: Update the docs and env example**

Use this `.env.example` shape:

```env
TG_BOT_TOKEN=replace_me
ALLOWED_TELEGRAM_USER_IDS=111111111,222222222,333333333
ADMIN_TELEGRAM_USER_IDS=111111111
MIKROTIK_IDS=mt1,mt2

MIKROTIK_MT1_NAME=Office
MIKROTIK_MT1_HOST=192.0.2.1
MIKROTIK_MT1_PORT=22
MIKROTIK_MT1_USERNAME=bot-office
MIKROTIK_MT1_PASSWORD=replace_me

MIKROTIK_MT2_NAME=Warehouse
MIKROTIK_MT2_HOST=192.0.2.2
MIKROTIK_MT2_PORT=22
MIKROTIK_MT2_USERNAME=bot-warehouse
MIKROTIK_MT2_PASSWORD=replace_me

USER_MIKROTIK_ACCESS_222222222=mt1
USER_MIKROTIK_ACCESS_333333333=mt2
LOG_LEVEL=INFO
```

Update README to describe:
- router-first menu flow
- admin visibility vs assigned-user visibility
- env-only multi-router config
- manual verification for both admin and regular user scenarios

- [ ] **Step 4: Re-run the docs verification**

Run: `grep -n "ADMIN_TELEGRAM_USER_IDS\\|MIKROTIK_IDS\\|USER_MIKROTIK_ACCESS_" .env.example README.md`
Expected: output shows the new multi-router variables in both files.

- [ ] **Step 5: Commit**

```bash
git add .env.example README.md
git commit -m "docs: describe multi-mikrotik access"
```

### Task 7: End-to-end verification before completion

**Files:**
- Modify: `tests/test_settings.py`
- Modify: `tests/test_address_list_manager.py`
- Modify: `tests/test_mikrotik_client.py`
- Modify: `tests/test_telegram_bot.py`
- Modify: `tests/test_add_flow_state.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Run the full automated test suite**

Run: `pytest -v`
Expected: PASS with the new settings, service, SSH, app, and Telegram coverage.

- [ ] **Step 2: Run a direct syntax/import verification**

Run: `python -m compileall src tests`
Expected: PASS with no syntax errors.

- [ ] **Step 3: Perform a manual bot-safe verification**

Run with a non-production `.env`:

```bash
python -m tgbot_manage_addresslist
```

Manual checks:
- log in as an admin and confirm all routers are shown first
- log in as a regular user and confirm only assigned routers are shown
- select one router and confirm add/delete actions are router-specific
- verify delete still requires explicit confirmation
- send `/start` from each intermediate step and confirm it resets to router selection
- tap an old router button and confirm the bot rejects the stale menu

- [ ] **Step 4: Record the verification outcome**

Capture the exact commands run and whether the manual check used a real bot session or an equivalent direct manual harness. If manual bot verification cannot be completed, stop and report that limitation instead of claiming the feature is finished.

- [ ] **Step 5: Commit**

```bash
git add tests/test_settings.py tests/test_address_list_manager.py tests/test_mikrotik_client.py tests/test_telegram_bot.py tests/test_add_flow_state.py tests/test_app.py
git commit -m "test: verify multi-mikrotik access flow"
```
