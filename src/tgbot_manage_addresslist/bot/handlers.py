from __future__ import annotations

from dataclasses import dataclass

from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from tgbot_manage_addresslist.bot.keyboards import (
    build_address_list_keyboard,
    build_confirmation_keyboard,
)
from tgbot_manage_addresslist.bot.states import AddIpFlow, DeleteListFlow
from tgbot_manage_addresslist.config.settings import Settings
from tgbot_manage_addresslist.services.address_list_manager import (
    AddOperationResult,
    AddressListManager,
    DeleteOperationResult,
)
from tgbot_manage_addresslist.validation.ip_lists import parse_ip_input


@dataclass(frozen=True, slots=True)
class BotDependencies:
    settings: Settings
    address_list_manager: AddressListManager


async def _ensure_authorized(event: Message | CallbackQuery, settings: Settings) -> bool:
    user = event.from_user
    if user is None or user.id not in settings.allowed_telegram_user_ids:
        if isinstance(event, CallbackQuery):
            await event.answer("Доступ запрещен", show_alert=True)
        else:
            await event.answer("У вас нет доступа к этому боту.")
        return False
    return True


def _format_add_result(result: AddOperationResult) -> str:
    lines = [
        f"Address-list: {result.list_name}",
        f"Добавлено: {len(result.added)}",
        f"Дубликаты: {len(result.duplicates)}",
        f"Невалидные значения: {len(result.invalid_tokens)}",
        f"Ошибки MikroTik: {len(result.errors)}",
    ]
    if result.added:
        lines.append("")
        lines.append("Добавлены:")
        lines.extend(result.added)
    if result.duplicates:
        lines.append("")
        lines.append("Уже существовали:")
        lines.extend(result.duplicates)
    if result.invalid_tokens:
        lines.append("")
        lines.append("Невалидные:")
        lines.extend(result.invalid_tokens)
    if result.errors:
        lines.append("")
        lines.append("Ошибки:")
        lines.extend(f"{item.ip_address}: {item.reason}" for item in result.errors)
    return "\n".join(lines)


def _format_delete_result(result: DeleteOperationResult) -> str:
    return (
        f"Address-list {result.list_name} удален.\n"
        f"Удалено записей: {result.removed_count}"
    )


def register_handlers(dispatcher: Dispatcher, deps: BotDependencies) -> None:
    @dispatcher.message(Command("help"))
    async def help_handler(message: Message, state: FSMContext) -> None:
        if not await _ensure_authorized(message, deps.settings):
            return
        await state.clear()
        await message.answer(
            "/start - добавить IP в address-list\n"
            "/delete_list - удалить весь address-list\n"
            "/cancel - отменить текущий сценарий"
        )

    @dispatcher.message(Command("cancel"))
    async def cancel_handler(message: Message, state: FSMContext) -> None:
        if not await _ensure_authorized(message, deps.settings):
            return
        await state.clear()
        await message.answer("Текущий сценарий отменен.")

    @dispatcher.message(Command("start"))
    async def start_handler(message: Message, state: FSMContext) -> None:
        if not await _ensure_authorized(message, deps.settings):
            return
        await state.clear()
        await state.set_state(AddIpFlow.waiting_for_ip_input)
        await message.answer("Отправьте список IP адресов.")

    @dispatcher.message(AddIpFlow.waiting_for_ip_input)
    async def ip_input_handler(message: Message, state: FSMContext) -> None:
        if not await _ensure_authorized(message, deps.settings):
            return
        if not message.text:
            await message.answer("Нужен текст со списком IP адресов.")
            return

        parsed = parse_ip_input(message.text)
        if not parsed.valid_ips and not parsed.invalid_tokens:
            await message.answer("Не удалось распознать ни одного IP адреса. Попробуйте еще раз.")
            return
        if not parsed.valid_ips:
            await message.answer(
                "В сообщении нет валидных IP адресов. Исправьте список и отправьте его еще раз."
            )
            return

        address_lists = await deps.address_list_manager.fetch_address_lists()

        await state.update_data(
            valid_ips=parsed.valid_ips,
            invalid_tokens=parsed.invalid_tokens,
            address_lists=address_lists,
        )
        await message.answer(
            "Выберите существующий address-list или создайте новый.",
            reply_markup=build_address_list_keyboard(address_lists, "pick"),
        )

    @dispatcher.callback_query(F.data == "pick:new")
    async def create_new_pick_handler(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _ensure_authorized(callback, deps.settings):
            return
        await state.set_state(AddIpFlow.waiting_for_new_list_name)
        await callback.message.answer("Отправьте имя нового address-list.")
        await callback.answer()

    @dispatcher.callback_query(F.data.startswith("pick:"))
    async def choose_existing_list_handler(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _ensure_authorized(callback, deps.settings):
            return
        _, raw_index = callback.data.split(":", 1)
        if raw_index == "new":
            return
        data = await state.get_data()
        address_lists = data.get("address_lists", [])
        index = int(raw_index)
        list_name = address_lists[index]
        result = await deps.address_list_manager.add_ips(
            list_name=list_name,
            valid_ips=data.get("valid_ips", []),
            invalid_tokens=data.get("invalid_tokens", []),
        )
        await state.clear()
        await callback.message.answer(_format_add_result(result))
        await callback.answer()

    @dispatcher.message(AddIpFlow.waiting_for_new_list_name)
    async def new_list_name_handler(message: Message, state: FSMContext) -> None:
        if not await _ensure_authorized(message, deps.settings):
            return
        list_name = (message.text or "").strip()
        if not list_name:
            await message.answer("Имя address-list не может быть пустым.")
            return
        data = await state.get_data()
        result = await deps.address_list_manager.add_ips(
            list_name=list_name,
            valid_ips=data.get("valid_ips", []),
            invalid_tokens=data.get("invalid_tokens", []),
        )
        await state.clear()
        await message.answer(_format_add_result(result))

    @dispatcher.message(Command("delete_list"))
    async def delete_list_handler(message: Message, state: FSMContext) -> None:
        if not await _ensure_authorized(message, deps.settings):
            return
        await state.clear()
        address_lists = await deps.address_list_manager.fetch_address_lists()
        if not address_lists:
            await message.answer("На MikroTik не найдено ни одного address-list.")
            return
        await state.update_data(address_lists=address_lists)
        await message.answer(
            "Выберите address-list для полного удаления.",
            reply_markup=build_address_list_keyboard(address_lists, "delete"),
        )

    @dispatcher.callback_query(F.data.startswith("delete:"))
    async def delete_pick_handler(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _ensure_authorized(callback, deps.settings):
            return
        _, raw_index = callback.data.split(":", 1)
        data = await state.get_data()
        address_lists = data.get("address_lists", [])
        list_name = address_lists[int(raw_index)]
        await state.update_data(delete_list_name=list_name)
        await state.set_state(DeleteListFlow.waiting_for_confirmation)
        await callback.message.answer(
            f"Подтвердите удаление address-list {list_name}. Это удалит все IP адреса внутри него.",
            reply_markup=build_confirmation_keyboard("delete:confirm", "delete:cancel"),
        )
        await callback.answer()

    @dispatcher.callback_query(F.data == "delete:cancel")
    async def delete_cancel_handler(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _ensure_authorized(callback, deps.settings):
            return
        await state.clear()
        await callback.message.answer("Удаление отменено.")
        await callback.answer()

    @dispatcher.callback_query(F.data == "delete:confirm")
    async def delete_confirm_handler(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _ensure_authorized(callback, deps.settings):
            return
        data = await state.get_data()
        list_name = data["delete_list_name"]
        result = await deps.address_list_manager.delete_list(list_name)
        await state.clear()
        await callback.message.answer(_format_delete_result(result))
        await callback.answer()
