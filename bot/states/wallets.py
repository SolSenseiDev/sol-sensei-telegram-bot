from aiogram.fsm.state import StatesGroup, State

class WalletStates(StatesGroup):
    waiting_for_private_key = State()
    waiting_for_withdraw_address = State()
    waiting_for_withdraw_amount = State()
    waiting_for_withdraw_usdc_address = State()
    waiting_for_withdraw_usdc_amount = State()