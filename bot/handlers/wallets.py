from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from solana.publickey import PublicKey
from solana.rpc.async_api import AsyncClient

from bot.keyboards.wallets import get_wallets_keyboard
from bot.keyboards.main_menu import get_main_menu
from bot.services.solana import (
    generate_wallet,
    get_wallet_balance,
    decrypt_keypair
)
from bot.services.encryption import encrypt_seed
from bot.database.models import Wallet, User
from bot.database.db import async_session
from bot.states.wallets import WalletStates
from bot.handlers.start import render_main_menu
from bot.utils.user_data import get_usdc_balance, fetch_sol_price

from solders.keypair import Keypair

wallets_router = Router()
user_selected_wallets = {}

RPC_URL = "https://api.mainnet-beta.solana.com"


@wallets_router.callback_query(F.data == "wallets")
async def show_wallets(callback: CallbackQuery):
    telegram_id = callback.from_user.id

    async with async_session() as session:
        result = await session.execute(
            select(User).options(selectinload(User.wallets)).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.wallets:
            await callback.message.edit_text(
                "💼 <b>Your Wallets</b>"
                "You don't have any wallets yet. Click ➕ to create one.",
                reply_markup=get_wallets_keyboard([], {}, {}, set())
            )
            await callback.answer()
            return

        balances_sol = {}
        balances_usdc = {}
        sol_price = await fetch_sol_price()

        for wallet in user.wallets:
            sol = await get_wallet_balance(wallet.address)
            usdc = await get_usdc_balance(wallet.address)
            balances_sol[wallet.address] = sol
            balances_usdc[wallet.address] = usdc

        selected = user_selected_wallets.get(telegram_id, set())
        total_usdc_equivalent = sum(
            balances_usdc.get(wallet.address, 0.0) + balances_sol.get(wallet.address, 0.0) * sol_price
            for wallet in user.wallets
        )
        wallets_text = "\n".join(
            [f"↳ ({i}) <code>{wallet.address}</code>" for i, wallet in enumerate(user.wallets, start=1)]
        )

        text = (
            "💼 <b>Your Wallets:</b>\n\n"
            f"{wallets_text}\n\n"
            f"<b>Total Balance:</b> <code>${total_usdc_equivalent:.3f}</code>"
        )

        try:
            await callback.message.edit_text(
                text,
                reply_markup=get_wallets_keyboard(user.wallets, balances_sol, balances_usdc, selected)
            )
        except Exception:
            pass

    await callback.answer()


@wallets_router.callback_query(F.data.startswith("copy_wallet_balance:"))
async def refresh_wallets_on_balance_click(callback: CallbackQuery):
    try:
        await show_wallets(callback)
    except Exception:
        pass
    await callback.answer()


@wallets_router.callback_query(F.data == "new_wallet")
async def create_new_wallet(callback: CallbackQuery):
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
    await callback.message.answer(text_private)
    await show_wallets(callback)


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
        keypair = Keypair.from_base58_string(private_key)
        pubkey = str(keypair.pubkey())
    except Exception:
        await message.answer("❌ Invalid private key. Please try again.")
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

    await message.answer(f"✅ Wallet <code>{pubkey}</code> has been added.")
    await state.clear()
    await show_wallets(message)


@wallets_router.callback_query(F.data == "back_to_menu")
async def back_to_main_menu(callback: CallbackQuery):
    await render_main_menu(callback, callback.from_user.id)