from aiogram.fsm.state import StatesGroup, State

class WalletStates(StatesGroup):
    waiting_for_private_key = State()