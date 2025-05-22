from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select, delete
from solders.keypair import Keypair
import base58

from bot.keyboards.wallets import get_wallets_keyboard
from bot.services.solana import generate_wallet
from bot.services.encryption import encrypt_seed
from bot.database.models import Wallet, User
from bot.database.db import async_session
from bot.states.wallets import WalletStates
from bot.handlers.start import render_main_menu
from bot.utils.value_data import (
    get_usdc_balance,
    fetch_sol_price,
    calculate_total_usdc_equivalent,
    get_balances_for_wallets,
    get_wallets_text,
    get_user_with_wallets,
)

wallets_router = Router()
user_selected_wallets = {}


@wallets_router.callback_query(F.data == "wallets")
async def show_wallets(callback: CallbackQuery):
    telegram_id = callback.from_user.id

    async with async_session() as session:
        user = await get_user_with_wallets(telegram_id, session)

        if not user or not user.wallets:
            try:
                await callback.message.edit_text(
                    "💼 <b>Your Wallets</b>\n\n"
                    "You don't have any wallets yet. Click ➕ to create one.",
                    reply_markup=get_wallets_keyboard([], {}, {}, set())
                )
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e):
                    raise e
            await callback.answer()
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

        try:
            await callback.message.edit_text(
                text,
                reply_markup=get_wallets_keyboard(user.wallets, balances_sol, balances_usdc, selected)
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise e

    await callback.answer()


@wallets_router.callback_query(F.data.startswith("copy_wallet_balance:"))
async def refresh_wallets_on_balance_click(callback: CallbackQuery):
    try:
        await show_wallets(callback)
    except Exception:
        pass
    await callback.answer()


@wallets_router.callback_query(F.data == "new_wallet")
async def create_new_wallet(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    pubkey, seed = generate_wallet()
    encrypted = encrypt_seed(seed)

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()

        if not user:
            user = User(telegram_id=telegram_id)
            session.add(user)
            await session.flush()

        wallet = Wallet(address=pubkey, encrypted_seed=encrypted, user_id=user.id)
        session.add(wallet)
        await session.commit()

    text_private = (
        "🆕 <b>New Wallet Info:</b>\n\n"
        f"<b>Address:</b>\n<code>{pubkey}</code>\n\n"
        f"<b>Private Key (base58):</b>\n<code>{seed}</code>\n\n"
        "⚠️ <b>Save this message. The private key = access to your wallet.</b>"
    )

    refresh_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh Wallets", callback_data="wallets")]
        ]
    )

    await callback.message.answer(text_private)
    await callback.message.answer("👇 Click below to refresh your wallet view:", reply_markup=refresh_markup)
    await callback.answer()


@wallets_router.callback_query(F.data.startswith("select_wallet:"))
async def select_wallet(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    address = callback.data.split("select_wallet:")[1]
    selected = user_selected_wallets.setdefault(telegram_id, set())
    if address in selected:
        selected.remove(address)
    else:
        selected.add(address)
    await show_wallets(callback)


@wallets_router.callback_query(F.data == "delete_wallet")
async def delete_selected_wallet(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    selected = user_selected_wallets.get(telegram_id, set())

    if not selected:
        await callback.answer("❗ Please select at least one wallet", show_alert=True)
        return

    async with async_session() as session:
        for address in selected:
            await session.execute(delete(Wallet).where(Wallet.address == address))
        await session.commit()

    user_selected_wallets[telegram_id] = set()
    await callback.answer("🗑️ Selected wallets deleted")
    await show_wallets(callback)


@wallets_router.callback_query(F.data == "add_wallet")
async def ask_private_key(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("🔑 Send the private key (in base58) of your wallet:")
    await state.set_state(WalletStates.waiting_for_private_key)
    await callback.answer()


@wallets_router.message(WalletStates.waiting_for_private_key)
async def add_wallet_by_private_key(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    private_key = message.text.strip()

    try:
        decoded = base58.b58decode(private_key)
        if len(decoded) != 64:
            raise ValueError("Keypair must be 64 bytes")
        keypair = Keypair.from_bytes(decoded)
        pubkey = str(keypair.pubkey())
    except Exception:
        await message.answer("❌ <b>Invalid private key</b>. Please make sure it’s a valid base58-encoded 64-byte key.")
        return

    encrypted = encrypt_seed(private_key)

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(telegram_id=telegram_id)
            session.add(user)
            await session.flush()

        exists = await session.execute(select(Wallet).where(Wallet.address == pubkey))
        if exists.scalar_one_or_none():
            await message.answer("⚠️ Wallet already exists.")
            await state.clear()
            return

        wallet = Wallet(address=pubkey, encrypted_seed=encrypted, user_id=user.id)
        session.add(wallet)
        await session.commit()

    await state.clear()
    await message.answer(f"✅ Wallet <code>{pubkey}</code> has been added.")

    refresh_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh Wallets", callback_data="wallets")]
        ]
    )
    await message.answer("👇 Click below to refresh your wallet view:", reply_markup=refresh_markup)


@wallets_router.callback_query(F.data == "back_to_menu")
async def back_to_main_menu(callback: CallbackQuery):
    await render_main_menu(callback, callback.from_user.id)
