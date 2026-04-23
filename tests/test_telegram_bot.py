from __future__ import annotations

import asyncio

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

import tgbot_manage_addresslist.telegram_bot as telegram_bot
from tgbot_manage_addresslist.telegram_bot import (
    BotFlow,
    DATA_SELECTED_MIKROTIK_ID,
    DATA_SELECTED_MIKROTIK_NAME,
    _build_mikrotik_actions_keyboard,
    _build_mikrotik_selection_keyboard,
    _mikrotik_is_available,
    _show_connecting_to_mikrotik,
    _show_mikrotik_actions_menu,
    _show_mikrotik_selection_menu,
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

    assert button_texts == ["Office", "Warehouse"]


def test_build_mikrotik_actions_keyboard_does_not_contain_help() -> None:
    keyboard = _build_mikrotik_actions_keyboard("deadbeef")

    button_texts = [
        button.text
        for row in keyboard.inline_keyboard
        for button in row
    ]

    assert button_texts == ["Добавить IP", "Удалить address-list", "Назад"]


@pytest.mark.asyncio
async def test_show_mikrotik_selection_menu_sets_router_selection_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=StorageKey(bot_id=1, chat_id=1, user_id=1))
    rendered: dict[str, object] = {}

    async def fake_render_screen(state, event, text, reply_markup=None) -> None:
        rendered["text"] = text
        rendered["reply_markup"] = reply_markup

    class StubAccessResolver:
        def visible_mikrotiks_for(self, user_id: int):
            return (
                type("Router", (), {"id": "mt1", "name": "Office"})(),
                type("Router", (), {"id": "mt2", "name": "Warehouse"})(),
            )

    class StubEvent:
        from_user = type("User", (), {"id": 1})()

    deps = type(
        "Deps",
        (),
        {
            "user_access_resolver": StubAccessResolver(),
        },
    )()

    monkeypatch.setattr(telegram_bot, "_render_screen", fake_render_screen)

    await _show_mikrotik_selection_menu(StubEvent(), state, deps)

    assert await state.get_state() == BotFlow.mikrotik_selection.state
    assert rendered["text"] == "🌐 Выберите MikroTik\nВыберите роутер, с которым хотите работать."


@pytest.mark.asyncio
async def test_show_mikrotik_actions_menu_persists_selected_router(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=StorageKey(bot_id=1, chat_id=1, user_id=1))
    rendered: dict[str, object] = {}

    async def fake_render_screen(state, event, text, reply_markup=None) -> None:
        rendered["text"] = text

    monkeypatch.setattr(telegram_bot, "_render_screen", fake_render_screen)

    await _show_mikrotik_actions_menu(
        object(),
        state,
        mikrotik_id="mt1",
        mikrotik_name="Office",
    )

    data = await state.get_data()
    assert await state.get_state() == BotFlow.mikrotik_actions.state
    assert data[DATA_SELECTED_MIKROTIK_ID] == "mt1"
    assert data[DATA_SELECTED_MIKROTIK_NAME] == "Office"
    assert rendered["text"] == "📍 MikroTik: Office\nЧто хотите сделать?"


@pytest.mark.asyncio
async def test_show_connecting_to_mikrotik_renders_progress_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=StorageKey(bot_id=1, chat_id=1, user_id=1))
    rendered: dict[str, object] = {}

    async def fake_render_screen(state, event, text, reply_markup=None) -> None:
        rendered["text"] = text

    monkeypatch.setattr(telegram_bot, "_render_screen", fake_render_screen)

    await _show_connecting_to_mikrotik(object(), state, mikrotik_name="Office")

    assert rendered["text"] == "🟢 Подключаемся к MikroTik Office..."


@pytest.mark.asyncio
async def test_mikrotik_is_available_returns_false_on_runtime_error() -> None:
    class StubService:
        async def fetch_address_lists(self, mikrotik_id: str) -> list[str]:
            raise RuntimeError("router down")

    deps = type("Deps", (), {"address_list_service": StubService()})()

    result = await _mikrotik_is_available(deps, "mt1")

    assert result is False


@pytest.mark.asyncio
async def test_mikrotik_is_available_returns_false_on_timeout() -> None:
    class StubService:
        async def fetch_address_lists(self, mikrotik_id: str) -> list[str]:
            await asyncio.sleep(10)
            return []

    deps = type("Deps", (), {"address_list_service": StubService()})()

    result = await _mikrotik_is_available(deps, "mt1")

    assert result is False
