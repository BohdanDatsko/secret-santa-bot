from aiogram.fsm.state import State, StatesGroup


class ExclusionStates(StatesGroup):
    waiting_for_first = State()
    waiting_for_second = State()
