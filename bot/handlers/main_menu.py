from aiogram import Router
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from bot.states.buy_sell import BuySellStates

main_menu_router = Router()


@main_menu_router.callback_query(lambda c: c.data == "buy_sell")
async def buy_sell_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("🔍 <b>Send the contract address (CA) of the token:</b>")
    await state.set_state(BuySellStates.waiting_for_ca)
    await callback.answer()