from aiogram.fsm.state import StatesGroup, State


class SettingsStates(StatesGroup):

    entering_slippage = State()
    entering_fee      = State()