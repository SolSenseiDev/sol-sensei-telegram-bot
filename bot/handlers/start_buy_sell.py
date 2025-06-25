from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from bot.states.buy_sell import BuySellStates

router = Router(name="start_buy_sell")


@router.message(Command("buy_sell"))
async def command_buy_sell(message: Message, state: FSMContext):
    await message.answer("📥 Enter the token address (CA):")
    await state.set_state(BuySellStates.waiting_for_ca)
