from aiogram.fsm.state import State, StatesGroup

class SwapState(StatesGroup):
    fixed_sol_to_usdc_amount = State()
    fixed_usdc_to_sol_amount = State()