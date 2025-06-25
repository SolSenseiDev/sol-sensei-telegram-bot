from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from bot.handlers.start import render_main_menu
from bot.handlers.wallets import show_wallets


async def go_back_to_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        await render_main_menu(callback, callback.from_user.id, state)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        elif "there is no text in the message to edit" in str(e):
            await callback.message.delete()
            markup, text = await render_main_menu(
                callback, callback.from_user.id, state,
                return_markup=True,
                return_text=True
            )
            await callback.message.answer(
                text,
                reply_markup=markup,
                parse_mode="HTML"
            )
        else:
            raise e
    await state.clear()
    await callback.answer()


async def go_back_to_wallets(callback: CallbackQuery, state: FSMContext) -> None:

    try:
        await show_wallets(callback)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise e
    await state.clear()
    await callback.answer()