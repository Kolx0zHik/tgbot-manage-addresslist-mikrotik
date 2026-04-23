from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import re
import secrets

from aiogram import Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from tgbot_manage_addresslist.logic import (
    AddOperationResult,
    AddressListService,
    DeleteOperationResult,
    UserAccessResolver,
    parse_ip_input,
)
from tgbot_manage_addresslist.settings import MikroTikSettings, Settings


logger = logging.getLogger(__name__)
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")

FLOW_MENU = "menu"
FLOW_ADD = "add"
FLOW_DELETE = "delete"

ACTION_SELECT_MIKROTIK = "mselect"
ACTION_ROUTER_ADD = "radd"
ACTION_ROUTER_DELETE = "rdel"
ACTION_ROUTER_BACK = "rback"
ACTION_CANCEL = "cancel"
ACTION_BACK = "back"
ACTION_ADD_EXISTING = "alist"
ACTION_ADD_NEW = "anew"
ACTION_ADD_CONFIRM = "aconf"
ACTION_DELETE_PICK = "dlist"
ACTION_DELETE_CONFIRM = "dconf"

DATA_FLOW_TYPE = "flow_type"
DATA_FLOW_SESSION_ID = "flow_session_id"
DATA_ADDRESS_LISTS = "address_lists"
DATA_VALID_IPS = "valid_ips"
DATA_INVALID_TOKENS = "invalid_tokens"
DATA_SELECTED_LIST = "selected_list_name"
DATA_SELECTED_SOURCE = "selected_list_source"
DATA_SELECTED_MIKROTIK_ID = "selected_mikrotik_id"
DATA_SELECTED_MIKROTIK_NAME = "selected_mikrotik_name"
DATA_ACTIVE_CHAT_ID = "active_chat_id"
DATA_ACTIVE_MESSAGE_ID = "active_message_id"


class BotFlow(StatesGroup):
    mikrotik_selection = State()
    mikrotik_actions = State()
    add_waiting_list_choice = State()
    add_waiting_new_list_name = State()
    add_waiting_ip_input = State()
    add_waiting_confirmation = State()
    delete_waiting_list_choice = State()
    delete_waiting_confirmation = State()


@dataclass(frozen=True, slots=True)
class BotDependencies:
    settings: Settings
    address_list_service: AddressListService
    user_access_resolver: UserAccessResolver


@dataclass(frozen=True, slots=True)
class ParsedCallbackData:
    action: str
    session_id: str
    payload: str | None = None


def _new_session_id() -> str:
    return secrets.token_hex(4)


def _encode_callback_data(action: str, session_id: str, payload: str | int | None = None) -> str:
    parts = [action, session_id]
    if payload is not None:
        parts.append(str(payload))
    return ":".join(parts)


def _parse_callback_data(raw_data: str | None) -> ParsedCallbackData | None:
    if not raw_data:
        return None
    parts = raw_data.split(":", 2)
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return None
    payload = parts[2] if len(parts) == 3 else None
    return ParsedCallbackData(action=parts[0], session_id=parts[1], payload=payload)


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
    builder.adjust(1)
    return builder.as_markup()


def _build_mikrotik_actions_keyboard(session_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Добавить IP", callback_data=_encode_callback_data(ACTION_ROUTER_ADD, session_id))
    builder.button(
        text="Удалить address-list",
        callback_data=_encode_callback_data(ACTION_ROUTER_DELETE, session_id),
    )
    builder.button(text="Назад", callback_data=_encode_callback_data(ACTION_ROUTER_BACK, session_id))
    builder.adjust(1)
    return builder.as_markup()


def _build_cancel_keyboard(session_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Отмена", callback_data=_encode_callback_data(ACTION_CANCEL, session_id))
    builder.adjust(1)
    return builder.as_markup()


def _build_add_list_keyboard(address_lists: list[str], session_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, list_name in enumerate(address_lists):
        builder.button(
            text=list_name,
            callback_data=_encode_callback_data(ACTION_ADD_EXISTING, session_id, index),
        )
    builder.button(text="Создать новый address-list", callback_data=_encode_callback_data(ACTION_ADD_NEW, session_id))
    builder.button(text="Отмена", callback_data=_encode_callback_data(ACTION_CANCEL, session_id))
    builder.adjust(1)
    return builder.as_markup()


def _build_delete_list_keyboard(address_lists: list[str], session_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, list_name in enumerate(address_lists):
        builder.button(
            text=list_name,
            callback_data=_encode_callback_data(ACTION_DELETE_PICK, session_id, index),
        )
    builder.button(text="Отмена", callback_data=_encode_callback_data(ACTION_CANCEL, session_id))
    builder.adjust(1)
    return builder.as_markup()


def _build_confirmation_keyboard(session_id: str, confirm_action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Подтвердить", callback_data=_encode_callback_data(confirm_action, session_id))
    builder.button(text="Назад", callback_data=_encode_callback_data(ACTION_BACK, session_id))
    builder.button(text="Отмена", callback_data=_encode_callback_data(ACTION_CANCEL, session_id))
    builder.adjust(2, 1)
    return builder.as_markup()


def _help_text() -> str:
    return (
        "Бот работает через inline-кнопки.\n"
        "/start - выбрать MikroTik\n"
        "/delete_list - удалить address-list на выбранном MikroTik\n"
        "/cancel - отменить текущий сценарий\n"
        "Текстом отправляются только IP-адреса и имя нового address-list."
    )


def _contains_cyrillic(value: str) -> bool:
    return CYRILLIC_RE.search(value) is not None


def _format_add_result(result: AddOperationResult, mikrotik_name: str) -> str:
    lines = [
        f"MikroTik: {mikrotik_name}",
        f"Address-list: {result.list_name}",
        f"Добавлено: {len(result.added)}",
        f"Дубликаты: {len(result.duplicates)}",
        f"Невалидные значения: {len(result.invalid_tokens)}",
        f"Ошибки MikroTik: {len(result.errors)}",
    ]
    if result.added:
        lines.extend(["", "Добавлены:", *result.added])
    if result.duplicates:
        lines.extend(["", "Уже существовали:", *result.duplicates])
    if result.invalid_tokens:
        lines.extend(["", "Невалидные:", *result.invalid_tokens])
    if result.errors:
        lines.extend(["", "Ошибки:", *[f"{item.ip_address}: {item.reason}" for item in result.errors]])
    return "\n".join(lines)


def _format_delete_result(result: DeleteOperationResult, mikrotik_name: str) -> str:
    return (
        f"MikroTik: {mikrotik_name}\n"
        f"Address-list {result.list_name} удален.\n"
        f"Удалено записей: {result.removed_count}"
    )


async def _ensure_authorized(event: Message | CallbackQuery, settings: Settings) -> bool:
    user = event.from_user
    if user is None or user.id not in settings.allowed_telegram_user_ids:
        if isinstance(event, CallbackQuery):
            await event.answer("Доступ запрещен", show_alert=True)
        else:
            await event.answer("У вас нет доступа к этому боту.")
        return False
    return True


def _message_target(event: Message | CallbackQuery) -> Message:
    if isinstance(event, Message):
        return event
    assert event.message is not None
    return event.message


async def _render_screen(
    state: FSMContext,
    event: Message | CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    data = await state.get_data()
    active_chat_id = data.get(DATA_ACTIVE_CHAT_ID)
    active_message_id = data.get(DATA_ACTIVE_MESSAGE_ID)

    target = _message_target(event)
    bot = target.bot

    if isinstance(event, CallbackQuery) and event.message is not None:
        active_chat_id = event.message.chat.id
        active_message_id = event.message.message_id
        try:
            await bot.edit_message_text(
                chat_id=active_chat_id,
                message_id=active_message_id,
                text=text,
                reply_markup=reply_markup,
            )
            await state.update_data(
                **{
                    DATA_ACTIVE_CHAT_ID: active_chat_id,
                    DATA_ACTIVE_MESSAGE_ID: active_message_id,
                }
            )
            return
        except TelegramBadRequest:
            logger.info(
                "Falling back to sending a fresh message for chat=%s message=%s",
                active_chat_id,
                active_message_id,
            )

    if active_chat_id is not None and active_message_id is not None:
        try:
            await bot.edit_message_reply_markup(
                chat_id=active_chat_id,
                message_id=active_message_id,
                reply_markup=None,
            )
        except TelegramBadRequest:
            logger.info(
                "Failed to clear keyboard for chat=%s message=%s",
                active_chat_id,
                active_message_id,
            )

    sent_message = await target.answer(text, reply_markup=reply_markup)
    await state.update_data(
        **{
            DATA_ACTIVE_CHAT_ID: sent_message.chat.id,
            DATA_ACTIVE_MESSAGE_ID: sent_message.message_id,
        }
    )


def _visible_mikrotik_choices(user_id: int, deps: BotDependencies) -> list[tuple[str, str]]:
    return [
        (mikrotik.id, mikrotik.name)
        for mikrotik in deps.user_access_resolver.visible_mikrotiks_for(user_id)
    ]


def _selected_mikrotik_from_data(data: dict[str, object]) -> tuple[str, str] | None:
    mikrotik_id = data.get(DATA_SELECTED_MIKROTIK_ID)
    mikrotik_name = data.get(DATA_SELECTED_MIKROTIK_NAME)
    if not isinstance(mikrotik_id, str) or not mikrotik_id:
        return None
    if not isinstance(mikrotik_name, str) or not mikrotik_name:
        return None
    return mikrotik_id, mikrotik_name


async def _show_connecting_to_mikrotik(
    event: Message | CallbackQuery,
    state: FSMContext,
    *,
    mikrotik_name: str,
) -> None:
    await _render_screen(state, event, f"Подключение к MikroTik {mikrotik_name}...")


async def _mikrotik_is_available(deps: BotDependencies, mikrotik_id: str) -> bool:
    try:
        await asyncio.wait_for(
            deps.address_list_service.fetch_address_lists(mikrotik_id),
            timeout=5,
        )
    except (asyncio.TimeoutError, ConnectionError, OSError, TimeoutError, RuntimeError):
        logger.exception("Selected MikroTik %s is unavailable", mikrotik_id)
        return False
    return True


async def _show_mikrotik_selection_menu(
    event: Message | CallbackQuery,
    state: FSMContext,
    deps: BotDependencies,
    *,
    notice: str | None = None,
) -> None:
    user = event.from_user
    if user is None:
        return

    visible_mikrotiks = _visible_mikrotik_choices(user.id, deps)
    if not visible_mikrotiks:
        logger.warning("Allowed Telegram user %s has no assigned MikroTik routers", user.id)
        await state.clear()
        await _render_screen(
            state,
            event,
            "Для вашего пользователя не назначен ни один MikroTik.",
        )
        return

    session_id = _new_session_id()
    active_data = await state.get_data()
    await state.clear()
    await state.set_state(BotFlow.mikrotik_selection)
    await state.update_data(
        **{
            DATA_FLOW_TYPE: FLOW_MENU,
            DATA_FLOW_SESSION_ID: session_id,
            DATA_ACTIVE_CHAT_ID: active_data.get(DATA_ACTIVE_CHAT_ID),
            DATA_ACTIVE_MESSAGE_ID: active_data.get(DATA_ACTIVE_MESSAGE_ID),
        }
    )
    text = "Выберите MikroTik."
    if notice:
        text = f"{notice}\n\n{text}"
    await _render_screen(
        state,
        event,
        text,
        _build_mikrotik_selection_keyboard(visible_mikrotiks, session_id),
    )


async def _show_mikrotik_actions_menu(
    event: Message | CallbackQuery,
    state: FSMContext,
    *,
    mikrotik_id: str,
    mikrotik_name: str,
    notice: str | None = None,
) -> None:
    session_id = _new_session_id()
    await state.set_state(BotFlow.mikrotik_actions)
    await state.update_data(
        **{
            DATA_FLOW_TYPE: FLOW_MENU,
            DATA_FLOW_SESSION_ID: session_id,
            DATA_SELECTED_MIKROTIK_ID: mikrotik_id,
            DATA_SELECTED_MIKROTIK_NAME: mikrotik_name,
        }
    )
    text = f"Выбран MikroTik: {mikrotik_name}\nВыберите действие."
    if notice:
        text = f"{notice}\n\n{text}"
    await _render_screen(state, event, text, _build_mikrotik_actions_keyboard(session_id))


async def _reset_to_menu(
    state: FSMContext,
    event: Message | CallbackQuery,
    deps: BotDependencies,
    notice: str | None = None,
) -> None:
    await _show_mikrotik_selection_menu(event, state, deps, notice=notice)


async def _reply_mikrotik_error(
    event: Message | CallbackQuery,
    state: FSMContext,
    deps: BotDependencies,
) -> None:
    data = await state.get_data()
    selected = _selected_mikrotik_from_data(data)
    if selected is None:
        await _reset_to_menu(
            state,
            event,
            deps,
            "Не удалось подключиться к MikroTik. Проверьте доступность роутера.",
        )
        return

    mikrotik_id, mikrotik_name = selected
    await _show_mikrotik_actions_menu(
        event,
        state,
        mikrotik_id=mikrotik_id,
        mikrotik_name=mikrotik_name,
        notice=f"Не удалось подключиться к MikroTik {mikrotik_name}.",
    )


async def _start_add_flow(event: Message | CallbackQuery, state: FSMContext, deps: BotDependencies) -> None:
    data = await state.get_data()
    selected = _selected_mikrotik_from_data(data)
    if selected is None:
        await _reset_to_menu(state, event, deps, "Сначала выберите MikroTik.")
        return

    mikrotik_id, mikrotik_name = selected
    try:
        address_lists = await deps.address_list_service.fetch_address_lists(mikrotik_id)
    except (ConnectionError, OSError, TimeoutError, RuntimeError):
        logger.exception("Failed to fetch address-lists for add flow on MikroTik %s", mikrotik_id)
        await _reply_mikrotik_error(event, state, deps)
        return
    await _show_add_list_choice(
        event,
        state,
        mikrotik_id=mikrotik_id,
        mikrotik_name=mikrotik_name,
        address_lists=address_lists,
    )


async def _show_add_list_choice(
    event: Message | CallbackQuery,
    state: FSMContext,
    *,
    mikrotik_id: str,
    mikrotik_name: str,
    address_lists: list[str],
    notice: str | None = None,
) -> None:
    session_id = _new_session_id()
    await state.set_state(BotFlow.add_waiting_list_choice)
    await state.update_data(
        **{
            DATA_FLOW_TYPE: FLOW_ADD,
            DATA_FLOW_SESSION_ID: session_id,
            DATA_SELECTED_MIKROTIK_ID: mikrotik_id,
            DATA_SELECTED_MIKROTIK_NAME: mikrotik_name,
            DATA_ADDRESS_LISTS: address_lists,
        }
    )
    text = f"MikroTik: {mikrotik_name}\nВыберите существующий address-list или создайте новый."
    if notice:
        text = f"{notice}\n\n{text}"
    await _render_screen(state, event, text, _build_add_list_keyboard(address_lists, session_id))


async def _show_new_list_name_prompt(
    event: Message | CallbackQuery,
    state: FSMContext,
    *,
    notice: str | None = None,
) -> None:
    session_id = _new_session_id()
    data = await state.get_data()
    selected = _selected_mikrotik_from_data(data)
    if selected is None:
        raise RuntimeError("Selected MikroTik is required before creating a new address-list")
    _, mikrotik_name = selected
    await state.set_state(BotFlow.add_waiting_new_list_name)
    await state.update_data(
        **{
            DATA_FLOW_TYPE: FLOW_ADD,
            DATA_FLOW_SESSION_ID: session_id,
        }
    )
    text = f"MikroTik: {mikrotik_name}\nОтправьте имя нового address-list."
    if notice:
        text = f"{notice}\n\n{text}"
    await _render_screen(state, event, text, _build_cancel_keyboard(session_id))


async def _show_add_ip_prompt(
    event: Message | CallbackQuery,
    state: FSMContext,
    *,
    list_name: str,
    selected_source: str,
    notice: str | None = None,
) -> None:
    session_id = _new_session_id()
    data = await state.get_data()
    selected = _selected_mikrotik_from_data(data)
    if selected is None:
        raise RuntimeError("Selected MikroTik is required before adding IPs")
    _, mikrotik_name = selected
    await state.set_state(BotFlow.add_waiting_ip_input)
    await state.update_data(
        **{
            DATA_FLOW_TYPE: FLOW_ADD,
            DATA_FLOW_SESSION_ID: session_id,
            DATA_SELECTED_LIST: list_name,
            DATA_SELECTED_SOURCE: selected_source,
            DATA_VALID_IPS: [],
            DATA_INVALID_TOKENS: [],
        }
    )
    text = f"MikroTik: {mikrotik_name}\nОтправьте IP-адреса или подсети для address-list {list_name}."
    if notice:
        text = f"{notice}\n\n{text}"
    await _render_screen(state, event, text, _build_cancel_keyboard(session_id))


async def _show_add_confirmation(
    event: Message | CallbackQuery,
    state: FSMContext,
    *,
    list_name: str,
    selected_source: str,
    valid_ips: list[str],
    invalid_tokens: list[str],
) -> None:
    session_id = _new_session_id()
    data = await state.get_data()
    selected = _selected_mikrotik_from_data(data)
    if selected is None:
        raise RuntimeError("Selected MikroTik is required before add confirmation")
    _, mikrotik_name = selected
    await state.set_state(BotFlow.add_waiting_confirmation)
    await state.update_data(
        **{
            DATA_FLOW_TYPE: FLOW_ADD,
            DATA_FLOW_SESSION_ID: session_id,
            DATA_SELECTED_LIST: list_name,
            DATA_SELECTED_SOURCE: selected_source,
            DATA_VALID_IPS: valid_ips,
            DATA_INVALID_TOKENS: invalid_tokens,
        }
    )
    invalid_note = ""
    if invalid_tokens:
        invalid_note = f"\nНевалидных значений будет пропущено: {len(invalid_tokens)}"
    await _render_screen(
        state,
        event,
        (
            f"MikroTik: {mikrotik_name}\n"
            f"Подтвердите добавление {len(valid_ips)} IP в address-list {list_name}.{invalid_note}"
        ),
        _build_confirmation_keyboard(session_id, ACTION_ADD_CONFIRM),
    )


async def _start_delete_flow(event: Message | CallbackQuery, state: FSMContext, deps: BotDependencies) -> None:
    data = await state.get_data()
    selected = _selected_mikrotik_from_data(data)
    if selected is None:
        await _reset_to_menu(state, event, deps, "Сначала выберите MikroTik.")
        return

    mikrotik_id, mikrotik_name = selected
    try:
        address_lists = await deps.address_list_service.fetch_address_lists(mikrotik_id)
    except (ConnectionError, OSError, TimeoutError, RuntimeError):
        logger.exception("Failed to fetch address-lists for delete flow on MikroTik %s", mikrotik_id)
        await _reply_mikrotik_error(event, state, deps)
        return

    if not address_lists:
        await _show_mikrotik_actions_menu(
            event,
            state,
            mikrotik_id=mikrotik_id,
            mikrotik_name=mikrotik_name,
            notice=f"На MikroTik {mikrotik_name} не найдено ни одного address-list.",
        )
        return

    session_id = _new_session_id()
    await state.set_state(BotFlow.delete_waiting_list_choice)
    await state.update_data(
        **{
            DATA_FLOW_TYPE: FLOW_DELETE,
            DATA_FLOW_SESSION_ID: session_id,
            DATA_SELECTED_MIKROTIK_ID: mikrotik_id,
            DATA_SELECTED_MIKROTIK_NAME: mikrotik_name,
            DATA_ADDRESS_LISTS: address_lists,
        }
    )
    await _render_screen(
        state,
        event,
        f"MikroTik: {mikrotik_name}\nВыберите address-list для полного удаления.",
        _build_delete_list_keyboard(address_lists, session_id),
    )


async def _show_delete_confirmation(event: Message | CallbackQuery, state: FSMContext, *, list_name: str) -> None:
    session_id = _new_session_id()
    data = await state.get_data()
    selected = _selected_mikrotik_from_data(data)
    if selected is None:
        raise RuntimeError("Selected MikroTik is required before delete confirmation")
    _, mikrotik_name = selected
    await state.set_state(BotFlow.delete_waiting_confirmation)
    await state.update_data(
        **{
            DATA_FLOW_TYPE: FLOW_DELETE,
            DATA_FLOW_SESSION_ID: session_id,
            DATA_SELECTED_LIST: list_name,
        }
    )
    await _render_screen(
        state,
        event,
        (
            f"MikroTik: {mikrotik_name}\n"
            f"Подтвердите удаление address-list {list_name}. Это удалит все IP-адреса внутри него."
        ),
        _build_confirmation_keyboard(session_id, ACTION_DELETE_CONFIRM),
    )


def _message_for_wrong_text(current_state: str | None) -> str:
    if current_state == BotFlow.mikrotik_selection.state:
        return "Сейчас выберите MikroTik кнопкой."
    if current_state == BotFlow.mikrotik_actions.state:
        return "Сейчас используйте кнопки меню MikroTik."
    if current_state == BotFlow.add_waiting_list_choice.state:
        return "Сейчас выберите address-list кнопкой."
    if current_state == BotFlow.add_waiting_confirmation.state:
        return "Сейчас нужно подтвердить добавление кнопкой."
    if current_state == BotFlow.delete_waiting_list_choice.state:
        return "Сейчас выберите address-list для удаления кнопкой."
    if current_state == BotFlow.delete_waiting_confirmation.state:
        return "Сейчас нужно подтвердить удаление кнопкой."
    return "Откройте главное меню через /start."


def _message_for_wrong_callback(current_state: str | None) -> str:
    if current_state == BotFlow.mikrotik_selection.state:
        return "Сейчас можно выбрать MikroTik только из текущего меню."
    if current_state == BotFlow.mikrotik_actions.state:
        return "Сейчас используйте актуальные кнопки выбранного MikroTik."
    if current_state == BotFlow.add_waiting_ip_input.state:
        return "Сейчас бот ждет список IP-адресов."
    if current_state == BotFlow.add_waiting_new_list_name.state:
        return "Сейчас бот ждет имя нового address-list."
    if current_state == BotFlow.add_waiting_list_choice.state:
        return "Сейчас можно выбрать address-list только из текущего меню."
    if current_state == BotFlow.add_waiting_confirmation.state:
        return "Сейчас можно только подтвердить или отменить добавление."
    if current_state == BotFlow.delete_waiting_list_choice.state:
        return "Сейчас можно выбрать address-list для удаления только из текущего меню."
    if current_state == BotFlow.delete_waiting_confirmation.state:
        return "Сейчас можно только подтвердить или отменить удаление."
    return "Эта кнопка больше неактуальна. Откройте меню заново."


async def _validate_callback(
    callback: CallbackQuery,
    state: FSMContext,
    *,
    expected_state: State,
    expected_actions: set[str],
) -> tuple[ParsedCallbackData, dict[str, object]] | None:
    parsed = _parse_callback_data(callback.data)
    if parsed is None or parsed.action not in expected_actions:
        await callback.answer("Эта кнопка не поддерживается.", show_alert=True)
        return None

    current_state = await state.get_state()
    if current_state != expected_state.state:
        await callback.answer(_message_for_wrong_callback(current_state), show_alert=True)
        return None

    data = await state.get_data()
    if data.get(DATA_FLOW_SESSION_ID) != parsed.session_id:
        await callback.answer("Это меню уже неактуально. Откройте его заново.", show_alert=True)
        return None

    return parsed, data


async def _handle_add_ip_input(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Нужен текст со списком IP-адресов.")
        return

    parsed = parse_ip_input(message.text)
    if not parsed.valid_ips and not parsed.invalid_tokens:
        await message.answer("Не удалось распознать ни одного IP-адреса. Попробуйте еще раз.")
        return
    if not parsed.valid_ips:
        await message.answer("В сообщении нет валидных IP-адресов. Исправьте список и отправьте его еще раз.")
        return

    logger.info(
        "Received %s valid IPs from Telegram user %s",
        len(parsed.valid_ips),
        message.from_user.id if message.from_user else "unknown",
    )

    data = await state.get_data()
    list_name = data.get(DATA_SELECTED_LIST)
    selected_source = data.get(DATA_SELECTED_SOURCE)
    if not isinstance(list_name, str) or not list_name or not isinstance(selected_source, str):
        raise RuntimeError("Add flow state is missing selected list data")

    await _show_add_confirmation(
        message,
        state,
        list_name=list_name,
        selected_source=selected_source,
        valid_ips=parsed.valid_ips,
        invalid_tokens=parsed.invalid_tokens,
    )


def register_handlers(dispatcher: Dispatcher, deps: BotDependencies) -> None:
    @dispatcher.message(Command("start"))
    async def start_handler(message: Message, state: FSMContext) -> None:
        if not await _ensure_authorized(message, deps.settings):
            return
        await _reset_to_menu(state, message, deps)

    @dispatcher.message(Command("help"))
    async def help_handler(message: Message, state: FSMContext) -> None:
        if not await _ensure_authorized(message, deps.settings):
            return
        await _reset_to_menu(state, message, deps, _help_text())

    @dispatcher.message(Command("cancel"))
    async def cancel_handler(message: Message, state: FSMContext) -> None:
        if not await _ensure_authorized(message, deps.settings):
            return
        await _reset_to_menu(state, message, deps, "Текущий сценарий отменен.")

    @dispatcher.message(Command("delete_list"))
    async def delete_list_handler(message: Message, state: FSMContext) -> None:
        if not await _ensure_authorized(message, deps.settings):
            return
        await _start_delete_flow(message, state, deps)

    @dispatcher.callback_query(F.data.startswith(f"{ACTION_SELECT_MIKROTIK}:"))
    async def select_mikrotik_handler(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _ensure_authorized(callback, deps.settings):
            return
        validated = await _validate_callback(
            callback,
            state,
            expected_state=BotFlow.mikrotik_selection,
            expected_actions={ACTION_SELECT_MIKROTIK},
        )
        if validated is None:
            return
        parsed, _ = validated
        user = callback.from_user
        if user is None or parsed.payload is None:
            await callback.answer("Эта кнопка больше неактуальна. Откройте меню заново.", show_alert=True)
            return
        if not deps.user_access_resolver.can_access(user.id, parsed.payload):
            await _reset_to_menu(state, callback, deps, "Выбранный MikroTik больше недоступен.")
            await callback.answer()
            return
        mikrotik = deps.settings.mikrotiks_by_id.get(parsed.payload)
        if mikrotik is None:
            await _reset_to_menu(state, callback, deps, "Выбранный MikroTik больше недоступен.")
            await callback.answer()
            return
        await _show_connecting_to_mikrotik(
            callback,
            state,
            mikrotik_name=mikrotik.name,
        )
        if not await _mikrotik_is_available(deps, mikrotik.id):
            await _show_mikrotik_selection_menu(
                callback,
                state,
                deps,
                notice=f"MikroTik {mikrotik.name} недоступен.",
            )
            await callback.answer()
            return
        await _show_mikrotik_actions_menu(
            callback,
            state,
            mikrotik_id=mikrotik.id,
            mikrotik_name=mikrotik.name,
        )
        await callback.answer()

    @dispatcher.callback_query(F.data.startswith(f"{ACTION_ROUTER_ADD}:"))
    async def router_add_handler(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _ensure_authorized(callback, deps.settings):
            return
        if await _validate_callback(
            callback,
            state,
            expected_state=BotFlow.mikrotik_actions,
            expected_actions={ACTION_ROUTER_ADD},
        ) is None:
            return
        await _start_add_flow(callback, state, deps)
        await callback.answer()

    @dispatcher.callback_query(F.data.startswith(f"{ACTION_ROUTER_DELETE}:"))
    async def router_delete_handler(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _ensure_authorized(callback, deps.settings):
            return
        if await _validate_callback(
            callback,
            state,
            expected_state=BotFlow.mikrotik_actions,
            expected_actions={ACTION_ROUTER_DELETE},
        ) is None:
            return
        await _start_delete_flow(callback, state, deps)
        await callback.answer()

    @dispatcher.callback_query(F.data.startswith(f"{ACTION_ROUTER_BACK}:"))
    async def router_back_handler(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _ensure_authorized(callback, deps.settings):
            return
        if await _validate_callback(
            callback,
            state,
            expected_state=BotFlow.mikrotik_actions,
            expected_actions={ACTION_ROUTER_BACK},
        ) is None:
            return
        await _reset_to_menu(state, callback, deps)
        await callback.answer()

    @dispatcher.message(BotFlow.add_waiting_ip_input)
    async def add_ip_input_handler(message: Message, state: FSMContext) -> None:
        if not await _ensure_authorized(message, deps.settings):
            return
        try:
            await _handle_add_ip_input(message, state)
        except RuntimeError:
            await _reset_to_menu(state, message, deps, "Сценарий добавления потерян. Начните заново.")

    @dispatcher.callback_query(F.data.startswith(f"{ACTION_ADD_EXISTING}:"))
    async def add_existing_list_handler(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _ensure_authorized(callback, deps.settings):
            return
        validated = await _validate_callback(
            callback,
            state,
            expected_state=BotFlow.add_waiting_list_choice,
            expected_actions={ACTION_ADD_EXISTING},
        )
        if validated is None:
            return
        parsed, data = validated
        address_lists = data.get(DATA_ADDRESS_LISTS, [])
        if not isinstance(address_lists, list) or parsed.payload is None:
            await callback.answer("Состояние сценария потеряно. Начните заново.", show_alert=True)
            return
        try:
            list_name = address_lists[int(parsed.payload)]
        except (ValueError, IndexError):
            await callback.answer("Выбранный address-list больше неактуален. Откройте список заново.", show_alert=True)
            return
        await _show_add_ip_prompt(
            callback,
            state,
            list_name=list_name,
            selected_source="existing",
        )
        await callback.answer()

    @dispatcher.callback_query(F.data.startswith(f"{ACTION_ADD_NEW}:"))
    async def add_new_list_handler(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _ensure_authorized(callback, deps.settings):
            return
        if await _validate_callback(
            callback,
            state,
            expected_state=BotFlow.add_waiting_list_choice,
            expected_actions={ACTION_ADD_NEW},
        ) is None:
            return
        await _show_new_list_name_prompt(callback, state)
        await callback.answer()

    @dispatcher.message(BotFlow.add_waiting_new_list_name)
    async def add_new_list_name_handler(message: Message, state: FSMContext) -> None:
        if not await _ensure_authorized(message, deps.settings):
            return
        list_name = (message.text or "").strip()
        if not list_name:
            await message.answer("Имя address-list не может быть пустым.")
            return
        if _contains_cyrillic(list_name):
            await message.answer("Имя address-list не должно содержать кириллицу.")
            return
        parsed_name = parse_ip_input(list_name)
        if parsed_name.valid_ips and not parsed_name.invalid_tokens:
            await message.answer("Сейчас ожидается имя address-list, а не IP-адреса.")
            return
        await _show_add_ip_prompt(
            message,
            state,
            list_name=list_name,
            selected_source="new",
        )

    @dispatcher.callback_query(F.data.startswith(f"{ACTION_ADD_CONFIRM}:"))
    async def add_confirm_handler(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _ensure_authorized(callback, deps.settings):
            return
        validated = await _validate_callback(
            callback,
            state,
            expected_state=BotFlow.add_waiting_confirmation,
            expected_actions={ACTION_ADD_CONFIRM},
        )
        if validated is None:
            return
        _, data = validated
        selected = _selected_mikrotik_from_data(data)
        list_name = data.get(DATA_SELECTED_LIST)
        valid_ips = data.get(DATA_VALID_IPS, [])
        invalid_tokens = data.get(DATA_INVALID_TOKENS, [])
        if (
            selected is None
            or not isinstance(list_name, str)
            or not isinstance(valid_ips, list)
            or not isinstance(invalid_tokens, list)
        ):
            await callback.answer("Сценарий добавления потерян. Начните заново.", show_alert=True)
            return
        mikrotik_id, mikrotik_name = selected
        try:
            result = await deps.address_list_service.add_ips(
                mikrotik_id=mikrotik_id,
                list_name=list_name,
                valid_ips=valid_ips,
                invalid_tokens=invalid_tokens,
            )
        except (ConnectionError, OSError, TimeoutError, RuntimeError):
            logger.exception("Failed to add IPs to MikroTik %s list %s", mikrotik_id, list_name)
            await _reply_mikrotik_error(callback, state, deps)
            await callback.answer()
            return
        await _show_mikrotik_actions_menu(
            callback,
            state,
            mikrotik_id=mikrotik_id,
            mikrotik_name=mikrotik_name,
            notice=_format_add_result(result, mikrotik_name),
        )
        await callback.answer()

    @dispatcher.callback_query(F.data.startswith(f"{ACTION_DELETE_PICK}:"))
    async def delete_pick_handler(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _ensure_authorized(callback, deps.settings):
            return
        validated = await _validate_callback(
            callback,
            state,
            expected_state=BotFlow.delete_waiting_list_choice,
            expected_actions={ACTION_DELETE_PICK},
        )
        if validated is None:
            return
        parsed, data = validated
        address_lists = data.get(DATA_ADDRESS_LISTS, [])
        if not isinstance(address_lists, list) or parsed.payload is None:
            await callback.answer("Состояние сценария потеряно. Начните заново.", show_alert=True)
            return
        try:
            list_name = address_lists[int(parsed.payload)]
        except (ValueError, IndexError):
            await callback.answer("Выбранный address-list больше неактуален. Откройте список заново.", show_alert=True)
            return
        await _show_delete_confirmation(callback, state, list_name=list_name)
        await callback.answer()

    @dispatcher.callback_query(F.data.startswith(f"{ACTION_DELETE_CONFIRM}:"))
    async def delete_confirm_handler(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _ensure_authorized(callback, deps.settings):
            return
        validated = await _validate_callback(
            callback,
            state,
            expected_state=BotFlow.delete_waiting_confirmation,
            expected_actions={ACTION_DELETE_CONFIRM},
        )
        if validated is None:
            return
        _, data = validated
        selected = _selected_mikrotik_from_data(data)
        list_name = data.get(DATA_SELECTED_LIST)
        if selected is None or not isinstance(list_name, str) or not list_name:
            await callback.answer("Сценарий удаления потерян. Начните заново.", show_alert=True)
            return
        mikrotik_id, mikrotik_name = selected
        try:
            result = await deps.address_list_service.delete_list(mikrotik_id, list_name)
        except (ConnectionError, OSError, TimeoutError, RuntimeError):
            logger.exception("Failed to delete MikroTik %s list %s", mikrotik_id, list_name)
            await _reply_mikrotik_error(callback, state, deps)
            await callback.answer()
            return
        await _show_mikrotik_actions_menu(
            callback,
            state,
            mikrotik_id=mikrotik_id,
            mikrotik_name=mikrotik_name,
            notice=_format_delete_result(result, mikrotik_name),
        )
        await callback.answer()

    @dispatcher.callback_query(F.data.startswith(f"{ACTION_BACK}:"))
    async def back_handler(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _ensure_authorized(callback, deps.settings):
            return
        parsed = _parse_callback_data(callback.data)
        current_state = await state.get_state()
        data = await state.get_data()
        if parsed is None:
            await callback.answer("Эта кнопка не поддерживается.", show_alert=True)
            return
        if data.get(DATA_FLOW_SESSION_ID) != parsed.session_id:
            await callback.answer("Это меню уже неактуально. Откройте его заново.", show_alert=True)
            return

        selected = _selected_mikrotik_from_data(data)
        if selected is None:
            await _reset_to_menu(state, callback, deps, "Сценарий потерян. Начните заново.")
            await callback.answer()
            return
        mikrotik_id, mikrotik_name = selected

        if current_state == BotFlow.add_waiting_new_list_name.state:
            address_lists = data.get(DATA_ADDRESS_LISTS, [])
            if not isinstance(address_lists, list):
                await _show_mikrotik_actions_menu(
                    callback,
                    state,
                    mikrotik_id=mikrotik_id,
                    mikrotik_name=mikrotik_name,
                    notice="Сценарий добавления потерян. Начните заново.",
                )
                await callback.answer()
                return
            await _show_add_list_choice(
                callback,
                state,
                mikrotik_id=mikrotik_id,
                mikrotik_name=mikrotik_name,
                address_lists=address_lists,
            )
            await callback.answer()
            return

        if current_state == BotFlow.add_waiting_confirmation.state:
            list_name = data.get(DATA_SELECTED_LIST)
            selected_source = data.get(DATA_SELECTED_SOURCE)
            if not isinstance(list_name, str) or not isinstance(selected_source, str):
                await _show_mikrotik_actions_menu(
                    callback,
                    state,
                    mikrotik_id=mikrotik_id,
                    mikrotik_name=mikrotik_name,
                    notice="Сценарий добавления потерян. Начните заново.",
                )
                await callback.answer()
                return
            await _show_add_ip_prompt(
                callback,
                state,
                list_name=list_name,
                selected_source=selected_source,
            )
            await callback.answer()
            return

        if current_state == BotFlow.delete_waiting_confirmation.state:
            address_lists = data.get(DATA_ADDRESS_LISTS, [])
            if not isinstance(address_lists, list) or not address_lists:
                await _show_mikrotik_actions_menu(
                    callback,
                    state,
                    mikrotik_id=mikrotik_id,
                    mikrotik_name=mikrotik_name,
                    notice="Сценарий удаления потерян. Начните заново.",
                )
                await callback.answer()
                return
            session_id = _new_session_id()
            await state.set_state(BotFlow.delete_waiting_list_choice)
            await state.update_data(
                **{
                    DATA_FLOW_TYPE: FLOW_DELETE,
                    DATA_FLOW_SESSION_ID: session_id,
                    DATA_ADDRESS_LISTS: address_lists,
                }
            )
            await _render_screen(
                state,
                callback,
                f"MikroTik: {mikrotik_name}\nВыберите address-list для полного удаления.",
                _build_delete_list_keyboard(address_lists, session_id),
            )
            await callback.answer()
            return

        await callback.answer(_message_for_wrong_callback(current_state), show_alert=True)

    @dispatcher.callback_query(F.data.startswith(f"{ACTION_CANCEL}:"))
    async def callback_cancel_handler(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _ensure_authorized(callback, deps.settings):
            return
        parsed = _parse_callback_data(callback.data)
        data = await state.get_data()
        if parsed is None:
            await callback.answer("Эта кнопка не поддерживается.", show_alert=True)
            return
        if data.get(DATA_FLOW_SESSION_ID) != parsed.session_id:
            await callback.answer("Это меню уже неактуально. Откройте его заново.", show_alert=True)
            return
        selected = _selected_mikrotik_from_data(data)
        if selected is None:
            await _reset_to_menu(state, callback, deps, "Текущий сценарий отменен.")
        else:
            await _show_mikrotik_actions_menu(
                callback,
                state,
                mikrotik_id=selected[0],
                mikrotik_name=selected[1],
                notice="Текущий сценарий отменен.",
            )
        await callback.answer()

    @dispatcher.message(
        BotFlow.mikrotik_selection,
        BotFlow.mikrotik_actions,
        BotFlow.add_waiting_list_choice,
        BotFlow.add_waiting_confirmation,
        BotFlow.delete_waiting_list_choice,
        BotFlow.delete_waiting_confirmation,
    )
    async def wrong_text_in_button_step_handler(message: Message, state: FSMContext) -> None:
        if not await _ensure_authorized(message, deps.settings):
            return
        await message.answer(_message_for_wrong_text(await state.get_state()))

    @dispatcher.message()
    async def fallback_message_handler(message: Message, state: FSMContext) -> None:
        if not await _ensure_authorized(message, deps.settings):
            return
        await message.answer(_message_for_wrong_text(await state.get_state()))

    @dispatcher.callback_query()
    async def fallback_callback_handler(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _ensure_authorized(callback, deps.settings):
            return
        parsed = _parse_callback_data(callback.data)
        if parsed is None:
            await callback.answer("Эта кнопка не поддерживается.", show_alert=True)
            return
        data = await state.get_data()
        if data.get(DATA_FLOW_SESSION_ID) != parsed.session_id:
            await callback.answer("Это меню уже неактуально. Откройте его заново.", show_alert=True)
            return
        await callback.answer(_message_for_wrong_callback(await state.get_state()), show_alert=True)
