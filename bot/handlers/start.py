from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart

from bot.keyboards.main_menu import get_main_menu  # 🔹 переименовали импорт

start_router = Router()

@start_router.message(CommandStart())
async def start_handler(message: Message):
    # 🔸 Заглушки: потом заменим реальным запросом к API и БД
    sol_price = 185.25
    wallet_address = "5A7g9f...XoR3"
    balance = 0.000995002

    text = (
        "👋 <b>SolSensei</b> мастер торговли в экосистеме Solana.\n\n"
        f"💰 <b>Цена SOL:</b> <code>{sol_price:.2f}$</code>\n\n"
        f"<b>Основной кошелек:</b>\n"
        f"↳ <code>{wallet_address}</code>\n"
        f"↳ Баланс: <code>{balance:.9f} SOL</code>"
    )

    await message.answer(text, reply_markup=get_main_menu())  # 🔹 тоже заменили
