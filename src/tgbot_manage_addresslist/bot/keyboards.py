from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def build_address_list_keyboard(address_lists: list[str], action_prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, list_name in enumerate(address_lists):
        builder.button(text=list_name, callback_data=f"{action_prefix}:{index}")
    if action_prefix == "pick":
        builder.button(text="Создать новый address-list", callback_data="pick:new")
    builder.adjust(1)
    return builder.as_markup()


def build_confirmation_keyboard(confirm_callback: str, cancel_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Подтвердить", callback_data=confirm_callback)
    builder.button(text="Отмена", callback_data=cancel_callback)
    builder.adjust(2)
    return builder.as_markup()
