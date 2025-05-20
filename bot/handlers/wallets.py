from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from solana.publickey import PublicKey
from solana.transaction import Transaction
from solana.system_program import TransferParams, transfer
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
from bot.handlers.start import render_main_menu  # ✅ Updated import

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
            text = (
                "💼 <b>Your Wallets</b>\n\n"
                "You don't have any wallets yet. Click ➕ to create one."
            )
            await callback.message.edit_text(text, reply_markup=get_wallets_keyboard([], {}, None))
            await callback.answer()
            return

        balances = {}
        total = 0.0

        for wallet in user.wallets:
            balance = await get_wallet_balance(wallet.address)
            balances[wallet.address] = balance
            total += balance

        text = "💼 <b>Your Wallets:</b>\n\n"
        for i, wallet in enumerate(user.wallets, start=1):
            text += f"↳ ({i}) <code>{wallet.address}</code>\n"
        text += f"\n<b>Total Balance:</b> {total:.6f} SOL"

        selected = user_selected_wallets.get(telegram_id)
        await callback.message.edit_text(
            text,
            reply_markup=get_wallets_keyboard(user.wallets, balances, selected)
        )
    await callback.answer()


@wallets_router.callback_query(F.data == "new_wallet")
async def create_new_wallet(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    pubkey, seed = generate_wallet()
    encrypted = encrypt_seed(seed)

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
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
    user_selected_wallets[telegram_id] = address
    await show_wallets(callback)


@wallets_router.callback_query(F.data == "delete_wallet")
async def delete_selected_wallet(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    selected = user_selected_wallets.get(telegram_id)

    if not selected:
        await callback.answer("❗ Please select a wallet first", show_alert=True)
        return

    async with async_session() as session:
        await session.execute(delete(Wallet).where(Wallet.address == selected))
        await session.commit()

    user_selected_wallets.pop(telegram_id, None)
    await callback.answer("🗑️ Wallet deleted")
    await show_wallets(callback)


@wallets_router.callback_query(F.data == "withdraw_all")
async def ask_withdraw_address(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📤 Enter the Solana wallet address to withdraw the full balance to:")
    await state.set_state(WalletStates.waiting_for_withdraw_address)
    await callback.answer()


@wallets_router.message(WalletStates.waiting_for_withdraw_address)
async def withdraw_all_sol(message: Message, state: FSMContext):
    target_address = message.text.strip()

    try:
        recipient = PublicKey(target_address)
    except Exception:
        await message.answer("❌ Invalid address. Please try again.")
        return

    telegram_id = message.from_user.id
    total_sent = 0.0

    async with async_session() as session:
        result = await session.execute(
            select(User).options(selectinload(User.wallets)).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.wallets:
            await message.answer("❗ You have no wallets.")
            await state.clear()
            return

        async with AsyncClient(RPC_URL) as client:
            for wallet in user.wallets:
                balance = await get_wallet_balance(wallet.address)
                if balance > 0.001:
                    try:
                        keypair = decrypt_keypair(wallet.encrypted_seed)
                        tx = Transaction()
                        tx.add(
                            transfer(
                                TransferParams(
                                    from_pubkey=keypair.public_key,
                                    to_pubkey=recipient,
                                    lamports=int((balance - 0.000005) * 1e9)
                                )
                            )
                        )
                        await client.send_transaction(tx, keypair)
                        total_sent += balance
                    except Exception as e:
                        await message.answer(f"⚠️ Error sending from {wallet.address}:\n{e}")

    await message.answer(f"✅ Successfully sent {total_sent:.6f} SOL to:\n<code>{target_address}</code>")
    await state.clear()


@wallets_router.callback_query(F.data == "back_to_menu")
async def back_to_main_menu(callback: CallbackQuery):
    await render_main_menu(callback, callback.from_user.id)