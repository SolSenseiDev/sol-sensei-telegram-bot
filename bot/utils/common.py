from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from bot.handlers.wallets import show_wallets


async def go_back_to_wallets(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Returns user to the Wallets screen and clears the state.
    Safe to call from any handler that needs a "Back" button.
    """
    try:
        await show_wallets(callback)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise e
    await state.clear()
    await callback.answer()