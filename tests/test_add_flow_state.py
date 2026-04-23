from __future__ import annotations

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

import tgbot_manage_addresslist.telegram_bot as telegram_bot
from tgbot_manage_addresslist.telegram_bot import (
    BotFlow,
    DATA_INVALID_TOKENS,
    DATA_SELECTED_LIST,
    DATA_SELECTED_SOURCE,
    DATA_VALID_IPS,
    _contains_cyrillic,
    _show_add_ip_prompt,
    _show_add_confirmation,
)


@pytest.mark.asyncio
async def test_show_add_confirmation_persists_ips_in_state(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=StorageKey(bot_id=1, chat_id=1, user_id=1))

    async def fake_render_screen(state, event, text, reply_markup=None) -> None:
        return None

    monkeypatch.setattr(telegram_bot, "_render_screen", fake_render_screen)

    await _show_add_confirmation(
        object(),
        state,
        list_name="test",
        selected_source="new",
        valid_ips=["8.8.8.8"],
        invalid_tokens=[],
    )

    data = await state.get_data()
    assert await state.get_state() == BotFlow.add_waiting_confirmation.state
    assert data[DATA_SELECTED_LIST] == "test"
    assert data[DATA_VALID_IPS] == ["8.8.8.8"]
    assert data[DATA_INVALID_TOKENS] == []


@pytest.mark.asyncio
async def test_show_add_ip_prompt_resets_pending_ips(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=StorageKey(bot_id=1, chat_id=1, user_id=1))

    async def fake_render_screen(state, event, text, reply_markup=None) -> None:
        return None

    monkeypatch.setattr(telegram_bot, "_render_screen", fake_render_screen)

    await _show_add_ip_prompt(
        object(),
        state,
        list_name="test",
        selected_source="new",
    )

    data = await state.get_data()
    assert await state.get_state() == BotFlow.add_waiting_ip_input.state
    assert data[DATA_SELECTED_LIST] == "test"
    assert data[DATA_SELECTED_SOURCE] == "new"
    assert data[DATA_VALID_IPS] == []
    assert data[DATA_INVALID_TOKENS] == []


def test_contains_cyrillic_detects_cyrillic_chars() -> None:
    assert _contains_cyrillic("тест")
    assert _contains_cyrillic("vpn-тест")
    assert not _contains_cyrillic("vpn-test_01")
