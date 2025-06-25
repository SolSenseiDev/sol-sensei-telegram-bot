from aiogram import Router
from aiogram.types import Message
from datetime import datetime, timezone

from bot.keyboards.wallets import get_wallets_keyboard
from bot.utils.value_data import (
    fetch_sol_price,
    get_balances_for_wallets,
    calculate_total_usdc_equivalent,
    get_wallets_text,
    get_user_with_wallets,
)
from bot.database.db import async_session

start_wallets_router = Router()
user_selected_wallets = {}


@start_wallets_router.message(lambda msg: msg.text == "/wallets")
async def wallets_command_handler(message: Message):
    telegram_id = message.from_user.id

    async with async_session() as session:
        user = await get_user_with_wallets(telegram_id, session)

        if not user or not user.wallets:
            await message.answer(
                "💼 <b>Your Wallets</b>\n\n"
                "You don't have any wallets yet. Click ➕ to create one.",
                reply_markup=get_wallets_keyboard([], {}, {}, set())
            )
            return

        sol_price = await fetch_sol_price()
        balances_sol, balances_usdc = await get_balances_for_wallets(user.wallets)
        selected = user_selected_wallets.get(telegram_id, set())

        total_usdc_equivalent = calculate_total_usdc_equivalent(
            user.wallets, balances_sol, balances_usdc, sol_price
        )
        wallets_text = get_wallets_text(user.wallets)

        text = (
            "💼 <b>Your Wallets:</b>\n\n"
            f"{wallets_text}\n\n"
            f"<b>Total Balance:</b> <code>${total_usdc_equivalent:.3f}</code>\n\n"
            f"⏱ <i>Last updated at {datetime.now(timezone.utc):%H:%M:%S} UTC</i>"
        )

        await message.answer(
            text,
            reply_markup=get_wallets_keyboard(user.wallets, balances_sol, balances_usdc, selected)
        )
