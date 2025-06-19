from aiogram.fsm.state import StatesGroup, State


class BuySellStates(StatesGroup):
    waiting_for_ca = State()
    choosing_mode = State()  # Buy or Sell
    selecting_wallets = State()  # Selecting wallets to use
    entering_buy_amount = State()  # For custom buy input
    entering_sell_percent = State()  # For custom sell input
