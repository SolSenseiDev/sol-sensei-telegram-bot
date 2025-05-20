from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

from bot.keyboards.main_menu import get_main_menu
from bot.utils.user_data import fetch_sol_price, get_first_wallet_and_balance

start_router = Router()

async def render_main_menu(target, telegram_id: int):
    sol_price = await fetch_sol_price()
    wallet_address, balance = await get_first_wallet_and_balance(telegram_id)

    text = (
        "👋 <b>SolSensei</b> is your trading master in the Solana ecosystem.\n\n"
        f"💰 <b>SOL Price:</b> <code>{sol_price:.2f}$</code>\n\n"
        f"<b>Primary Wallet:</b>\n"
        f"↳ <code>{wallet_address}</code>\n"
        f"↳ Balance: <code>{balance:.9f} SOL</code>"
    )

    if isinstance(target, Message):
        await target.answer(text, reply_markup=get_main_menu())
    elif isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=get_main_menu())
        await target.answer()

@start_router.message(CommandStart())
async def start_handler(message: Message):
    await render_main_menu(message, message.from_user.id)