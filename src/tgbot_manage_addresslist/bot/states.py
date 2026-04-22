from aiogram.fsm.state import State, StatesGroup


class AddIpFlow(StatesGroup):
    waiting_for_ip_input = State()
    waiting_for_new_list_name = State()


class DeleteListFlow(StatesGroup):
    waiting_for_confirmation = State()
