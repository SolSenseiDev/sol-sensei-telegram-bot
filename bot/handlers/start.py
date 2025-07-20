from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from bot.keyboards.main_menu import get_main_menu
from bot.utils.value_data import fetch_sol_price
from bot.utils.main_menu_data import get_first_wallet_and_balance

start_router = Router()


async def render_main_menu(
    target,
    telegram_id: int,
    state: FSMContext | None = None,
    return_markup: bool = False,
    return_text: bool = False
):
    sol_price = await fetch_sol_price()
    wallet_address, sol_balance = await get_first_wallet_and_balance(telegram_id)
    usd_balance = sol_balance * sol_price

    text = (
        "👋 <b>SolSensei</b> is your trading master in the Solana ecosystem.\n\n"
        f"💰 <b>SOL Price:</b> <code>{sol_price:.2f}$</code>\n\n"
        f"<b>Primary Wallet:</b>\n"
        f"↳ <code>{wallet_address}</code>\n"
        f"↳ Balance: <code>{sol_balance:.3f} SOL (${usd_balance:.3f})</code>"
    )

    markup = get_main_menu()

    if return_markup and return_text:
        return markup, text
    elif return_markup:
        return markup
    elif return_text:
        return text

    if isinstance(target, Message):
        await target.answer(text, reply_markup=markup, parse_mode="HTML")
        if state:
            await state.update_data(
                current_chat_id=target.chat.id,
                current_message_id=target.message_id
            )
    elif isinstance(target, CallbackQuery):
        try:
            await target.message.delete()
        except:
            pass
        await target.message.answer(text, reply_markup=markup, parse_mode="HTML")
        if state:
            await state.update_data(
                current_chat_id=target.message.chat.id,
                current_message_id=target.message.message_id
            )


@start_router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await render_main_menu(message, message.from_user.id, state)

