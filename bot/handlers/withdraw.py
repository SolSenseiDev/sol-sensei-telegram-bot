from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime, timezone
from sqlalchemy import select
from solders.pubkey import Pubkey

from bot.handlers.wallets import user_selected_wallets
from bot.database.db import async_session
from bot.database.models import Wallet
from bot.keyboards.withdraw import get_withdraw_keyboard
from bot.services.rust_swap import withdraw_sol_txid, withdraw_usdc_txid
from bot.states.wallets import WalletStates
from bot.utils.value_data import (
    check_sol_withdraw_possibility,
    check_usdc_withdraw_possibility,
    get_balances_for_wallets,
)

withdraw_router = Router()


async def show_withdraw_options(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    selected = user_selected_wallets.get(telegram_id, set())

    if not selected:
        await callback.answer("❗ Please select at least one wallet", show_alert=True)
        return

    async with async_session() as session:
        result = await session.execute(select(Wallet).where(Wallet.address.in_(selected)))
        wallets = result.scalars().all()

    balances_sol, balances_usdc = await get_balances_for_wallets(wallets)

    lines = ["💱 <b>Selected Wallets:</b>\n"]
    for i, w in enumerate(wallets, start=1):
        sol = balances_sol.get(w.address, 0.0)
        usdc = balances_usdc.get(w.address, 0.0)
        lines.append(f"↳ ({i}) <code>{w.address}</code>\n"
                     f"    ↳ balance: {sol:.4f} SOL\n"
                     f"    ↳ balance: {usdc:.2f} USDC\n")

    lines.append(f"\n⏱️ <i>Last updated: {datetime.now(timezone.utc):%H:%M:%S} UTC</i>")
    text = "\n".join(lines)

    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_withdraw_keyboard()
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise e

    await callback.answer()



@withdraw_router.callback_query(F.data == "withdraw_sol")
async def ask_withdraw_address(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("📬 <b>Please enter the destination wallet address (Solana):</b>")
    await state.set_state(WalletStates.waiting_for_withdraw_address)
    await callback.answer()


@withdraw_router.message(WalletStates.waiting_for_withdraw_address)
async def handle_withdraw_address(message: Message, state: FSMContext):
    address = message.text.strip()
    try:
        Pubkey.from_string(address)
    except Exception:
        await message.answer("❌ Invalid Solana address. Try again:")
        return

    await state.update_data(withdraw_to_address=address)
    await message.answer("💰 <b>Enter amount to withdraw (in SOL):</b>")
    await state.set_state(WalletStates.waiting_for_withdraw_amount)



@withdraw_router.message(WalletStates.waiting_for_withdraw_amount)
async def handle_withdraw_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Invalid amount. Please enter a positive number.")
        return

    data = await state.get_data()
    to_address = data.get("withdraw_to_address")
    telegram_id = message.from_user.id
    selected = user_selected_wallets.get(telegram_id, set())

    if not selected:
        await message.answer("❗ No wallets selected for withdrawal.")
        return

    async with async_session() as session:
        result = await session.execute(select(Wallet).where(Wallet.address.in_(selected)))
        wallets = result.scalars().all()

    await message.answer("⏳ Processing withdrawal...")

    success = []
    failed = {}

    for wallet in wallets:
        ok, reason, _ = await check_sol_withdraw_possibility(wallet.address, amount)
        if not ok:
            failed[wallet.address] = reason
            continue
        try:
            txid = await withdraw_sol_txid(wallet, to_address, amount)
            success.append((wallet.address, txid))
        except Exception as e:
            failed[wallet.address] = str(e)

    text = "📤 <b>Withdraw Result</b>\n"
    for addr, txid in success:
        short = f"{addr[:6]}...{addr[-4:]}"
        text += f"✅ <code>{short}</code> → <a href='https://solscan.io/tx/{txid}'>tx</a>\n"
    for addr, reason in failed.items():
        text += f"❌ <code>{addr}</code> — {reason}\n"

    await message.answer(text, disable_web_page_preview=True)
    await state.clear()


@withdraw_router.callback_query(F.data == "withdraw_usdc")
async def ask_withdraw_usdc_address(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("📬 <b>Please enter the destination wallet address (Solana):</b>")
    await state.set_state(WalletStates.waiting_for_withdraw_usdc_address)
    await callback.answer()



@withdraw_router.message(WalletStates.waiting_for_withdraw_usdc_address)
async def handle_withdraw_usdc_address(message: Message, state: FSMContext):
    address = message.text.strip()
    try:
        Pubkey.from_string(address)
    except Exception:
        await message.answer("❌ Invalid Solana address. Try again:")
        return

    await state.update_data(withdraw_to_address=address)
    await message.answer("💰 <b>Enter amount to withdraw (in USDC):</b>")
    await state.set_state(WalletStates.waiting_for_withdraw_usdc_amount)



@withdraw_router.message(WalletStates.waiting_for_withdraw_usdc_amount)
async def handle_withdraw_usdc_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Invalid amount. Please enter a positive number.")
        return

    data = await state.get_data()
    to_address = data.get("withdraw_to_address")
    telegram_id = message.from_user.id
    selected = user_selected_wallets.get(telegram_id, set())

    if not selected:
        await message.answer("❗ No wallets selected for withdrawal.")
        return

    async with async_session() as session:
        result = await session.execute(select(Wallet).where(Wallet.address.in_(selected)))
        wallets = result.scalars().all()

    await message.answer("⏳ Processing USDC withdrawal...")

    success = []
    failed = {}

    for wallet in wallets:
        try:
            ok, reason, _, _ = await check_usdc_withdraw_possibility(wallet.address, amount)
        except Exception:
            failed[wallet.address] = "Balance check failed"
            continue

        if not ok:
            failed[wallet.address] = reason
            continue

        try:
            txid = await withdraw_usdc_txid(wallet, to_address, amount)
            success.append((wallet.address, txid))
        except Exception as e:
            failed[wallet.address] = str(e)

    text = "📤 <b>Withdraw USDC Result</b>\n"
    for addr, txid in success:
        short = f"{addr[:6]}...{addr[-4:]}"
        text += f"✅ <code>{short}</code> → <a href='https://solscan.io/tx/{txid}'>tx</a>\n"
    for addr, reason in failed.items():
        text += f"❌ <code>{addr}</code> — {reason}\n"

    await message.answer(text, disable_web_page_preview=True)
    await state.clear()


@withdraw_router.callback_query(F.data == "withdraw_all")
async def handle_withdraw_all(callback: CallbackQuery):
    await show_withdraw_options(callback)