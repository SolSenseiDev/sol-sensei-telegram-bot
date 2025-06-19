from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from solders.keypair import Keypair
import base58

from bot.database.db import async_session
from bot.utils.value_data import (
    get_user_with_wallets,
    get_balances_for_wallets,
    check_sol_swap_possibility,
    check_usdc_swap_possibility,
)
from bot.handlers.wallets import user_selected_wallets
from bot.utils.common import go_back_to_wallets
from bot.keyboards.swap import get_swap_keyboard
from bot.services.encryption import decrypt_seed
from bot.services.rust_swap import (
    swap_all_sol_to_usdc,
    swap_all_usdc_to_sol,
    swap_fixed_sol_to_usdc,
    swap_fixed_usdc_to_sol,
)
from bot.states.swap_states import SwapState
import logging

logger = logging.getLogger(__name__)
swap_router = Router()


async def render_swap_menu(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    selected_addresses = user_selected_wallets.get(telegram_id)

    if not selected_addresses:
        await callback.answer("❗ Please select at least one wallet in Wallets section.", show_alert=True)
        return

    async with async_session() as session:
        user = await get_user_with_wallets(telegram_id, session)
        if not user:
            await callback.answer("❌ User not found.")
            return

        selected_wallets = [w for w in user.wallets if w.address in selected_addresses]
        if not selected_wallets:
            await callback.answer("❗ Selected wallets not found.")
            return

        balances_sol, balances_usdc = await get_balances_for_wallets(selected_wallets)

        lines = ["💱 <b>Selected Wallets:</b>\n"]
        for i, wallet in enumerate(selected_wallets, start=1):
            sol = balances_sol.get(wallet.address, 0.0)
            usdc = balances_usdc.get(wallet.address, 0.0)
            lines.append(f"↳ ({i}) <code>{wallet.address}</code>")
            lines.append(f"    ↳ balance: {sol:.4f} SOL")
            lines.append(f"    ↳ balance: {usdc:.2f} USDC\n")

        current_time = datetime.now(timezone.utc).strftime("%H:%M:%S")
        lines.append(f"⏱ <i>Last updated: {current_time} UTC</i>")

        try:
            await callback.message.edit_text("\n".join(lines), reply_markup=get_swap_keyboard())
        except Exception as e:
            if "message is not modified" not in str(e):
                raise e

    await callback.answer()


@swap_router.callback_query(F.data == "swap")
async def show_swap_menu(callback: CallbackQuery, state: FSMContext):
    await render_swap_menu(callback)


@swap_router.callback_query(F.data == "refresh_swap_menu")
async def refresh_swap_menu(callback: CallbackQuery, state: FSMContext):
    await render_swap_menu(callback)


@swap_router.callback_query(F.data == "swap_all_sol_usdc")
async def handle_swap_all_sol_usdc(callback: CallbackQuery):
    await callback.answer("⏳ Выполняем свап SOL → USDC...", show_alert=False)

    telegram_id = callback.from_user.id
    selected_addresses = user_selected_wallets.get(telegram_id, set())

    logger.info(f"[SOL→USDC] User {telegram_id} initiated swap for wallets: {selected_addresses}")

    async with async_session() as session:
        user = await get_user_with_wallets(telegram_id, session)
        if not user:
            logger.warning(f"[SOL→USDC] User {telegram_id} not found in DB.")
            await callback.message.answer("❌ User not found.")
            return

        selected_wallets = [w for w in user.wallets if w.address in selected_addresses]
        if not selected_wallets:
            logger.warning(f"[SOL→USDC] No matching wallets for user {telegram_id}.")
            await callback.message.answer("❗ No wallets selected.")
            return

        success = []
        failed = []

        for wallet in selected_wallets:
            logger.info(f"[SOL→USDC] Checking swap possibility for {wallet.address}")
            ok, reason, sol = await check_sol_swap_possibility(wallet.address)
            if not ok:
                logger.warning(f"[SOL→USDC] Swap not possible for {wallet.address}: {reason}")
                failed.append((wallet.address, reason))
                continue

            try:
                lamports = int(sol * 1_000_000_000)
                keypair = Keypair.from_bytes(base58.b58decode(decrypt_seed(wallet.encrypted_seed)))
                logger.info(f"[SOL→USDC] Attempting swap for {wallet.address} with {lamports} lamports")
                txid = await swap_all_sol_to_usdc(keypair, lamports)
                if txid and txid != "null":
                    logger.info(f"[SOL→USDC] Swap success for {wallet.address} → {txid}")
                    success.append((wallet.address, txid))
                else:
                    logger.error(f"[SOL→USDC] Swap failed: No route for {wallet.address}")
                    failed.append((wallet.address, "Маршрут не найден, попробуйте позже."))
            except Exception as e:
                logger.exception(f"[SOL→USDC] Exception during swap for {wallet.address}: {e}")
                failed.append((wallet.address, "Swap failed. Please try again."))

        await send_swap_result(callback, success, failed)


@swap_router.callback_query(F.data == "swap_all_usdc_sol")
async def handle_swap_all_usdc_sol(callback: CallbackQuery):
    await callback.answer("⏳ Выполняем свап USDC → SOL...", show_alert=False)

    telegram_id = callback.from_user.id
    selected_addresses = user_selected_wallets.get(telegram_id, set())

    logger.info(f"[USDC→SOL] User {telegram_id} initiated swap for wallets: {selected_addresses}")

    async with async_session() as session:
        user = await get_user_with_wallets(telegram_id, session)
        if not user:
            logger.warning(f"[USDC→SOL] User {telegram_id} not found in DB.")
            await callback.message.answer("❌ User not found.")
            return

        selected_wallets = [w for w in user.wallets if w.address in selected_addresses]
        if not selected_wallets:
            logger.warning(f"[USDC→SOL] No matching wallets for user {telegram_id}.")
            await callback.message.answer("❗ No wallets selected.")
            return

        success = []
        failed = []

        for wallet in selected_wallets:
            logger.info(f"[USDC→SOL] Checking swap possibility for {wallet.address}")
            ok, reason, _, _ = await check_usdc_swap_possibility(wallet.address)
            if not ok:
                logger.warning(f"[USDC→SOL] Swap not possible for {wallet.address}: {reason}")
                failed.append((wallet.address, reason))
                continue

            try:
                keypair = Keypair.from_bytes(base58.b58decode(decrypt_seed(wallet.encrypted_seed)))
                logger.info(f"[USDC→SOL] Attempting swap for {wallet.address}")
                txid = await swap_all_usdc_to_sol(keypair)
                if txid and txid != "null":
                    logger.info(f"[USDC→SOL] Swap success for {wallet.address} → {txid}")
                    success.append((wallet.address, txid))
                else:
                    logger.error(f"[USDC→SOL] Swap failed: No route for {wallet.address}")
                    failed.append((wallet.address, "Маршрут не найден, попробуйте позже."))
            except Exception as e:
                logger.exception(f"[USDC→SOL] Exception during swap for {wallet.address}: {e}")
                failed.append((wallet.address, "Swap failed. Please try again."))

        await send_swap_result(callback, success, failed)


@swap_router.callback_query(F.data == "swap_fixed_sol_usdc")
async def handle_swap_fixed_sol_usdc(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("🔢 Введите количество SOL для свапа в USDC:")
    await state.set_state(SwapState.fixed_sol_to_usdc_amount)


@swap_router.callback_query(F.data == "swap_fixed_usdc_sol")
async def handle_swap_fixed_usdc_sol(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("🔢 Введите количество USDC для свапа в SOL:")
    await state.set_state(SwapState.fixed_usdc_to_sol_amount)


@swap_router.message(SwapState.fixed_sol_to_usdc_amount)
async def process_fixed_sol_to_usdc(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    selected_addresses = user_selected_wallets.get(telegram_id, set())

    logger.info(f"[FIXED SOL→USDC] (1) User {telegram_id} entered amount: {message.text}")
    logger.info(f"[FIXED SOL→USDC] (2) Selected wallets: {selected_addresses}")

    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        logger.warning(f"[FIXED SOL→USDC] (3) Invalid amount entered: {message.text}")
        await message.answer("❌ Введите корректное число больше нуля.")
        return

    await message.answer("⏳ Выполняем свап SOL → USDC. Пожалуйста, подождите...")

    async with async_session() as session:
        user = await get_user_with_wallets(telegram_id, session)
        if not user:
            logger.warning(f"[FIXED SOL→USDC] (4) User {telegram_id} not found in DB.")
            await message.answer("❌ User not found.")
            return

        selected_wallets = [w for w in user.wallets if w.address in selected_addresses]
        if not selected_wallets:
            logger.warning(f"[FIXED SOL→USDC] (5) No matching wallets for user {telegram_id}.")
            await message.answer("❗ No wallets selected.")
            return

        success = []
        failed = []

        for wallet in selected_wallets:
            logger.info(f"[FIXED SOL→USDC] (6) Checking {wallet.address} for swap possibility.")
            ok, reason, sol_balance = await check_sol_swap_possibility(wallet.address)
            logger.info(f"[FIXED SOL→USDC] (7) Balance: {sol_balance:.6f} SOL | Needed: {amount}")

            if sol_balance < amount:
                logger.warning(f"[FIXED SOL→USDC] (8) Not enough SOL: {sol_balance:.4f} < {amount}")
                failed.append((wallet.address, f"Недостаточно SOL (доступно {sol_balance:.4f})"))
                continue

            try:
                lamports = int(amount * 1_000_000_000)
                logger.info(f"[FIXED SOL→USDC] (9) Swapping {lamports} lamports for {wallet.address}")

                decrypted = decrypt_seed(wallet.encrypted_seed)
                logger.debug(f"[FIXED SOL→USDC] (10) Decrypted seed (base58, shortened): {decrypted[:6]}...")

                keypair = Keypair.from_bytes(base58.b58decode(decrypted))

                logger.info(f"[FIXED SOL→USDC] (11) Calling swap_fixed_sol_to_usdc()...")
                txid = await swap_fixed_sol_to_usdc(keypair, lamports)

                logger.info(f"[FIXED SOL→USDC] (12) TXID returned: {txid}")
                if txid and txid != "null":
                    logger.info(f"[FIXED SOL→USDC] (13) SUCCESS: {wallet.address} → {txid}")
                    success.append((wallet.address, txid))
                else:
                    logger.error(f"[FIXED SOL→USDC] (14) FAIL: No route for {wallet.address}")
                    failed.append((wallet.address, "Маршрут не найден, попробуйте позже."))

            except Exception as e:
                logger.exception(f"[FIXED SOL→USDC] (15) Exception for {wallet.address}: {e}")
                failed.append((wallet.address, "Swap failed. Please try again."))

        logger.info(f"[FIXED SOL→USDC] (16) Finished. Success: {len(success)} | Failed: {len(failed)}")
        await send_swap_result(message, success, failed)
        await state.clear()


@swap_router.message(SwapState.fixed_usdc_to_sol_amount)
async def process_fixed_usdc_to_sol(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    selected_addresses = user_selected_wallets.get(telegram_id, set())

    logger.info(f"[FIXED USDC→SOL] User {telegram_id} entered amount: {message.text}")

    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount < 1.0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Минимальная сумма для свапа — 1.0 USDC")
        return

    await message.answer("⏳ Выполняем свап USDC → SOL. Пожалуйста, подождите...")

    async with async_session() as session:
        user = await get_user_with_wallets(telegram_id, session)
        if not user:
            logger.warning(f"[FIXED USDC→SOL] User {telegram_id} not found in DB.")
            await message.answer("❌ User not found.")
            return

        selected_wallets = [w for w in user.wallets if w.address in selected_addresses]
        if not selected_wallets:
            logger.warning(f"[FIXED USDC→SOL] No matching wallets for user {telegram_id}.")
            await message.answer("❗ No wallets selected.")
            return

        success = []
        failed = []

        for wallet in selected_wallets:
            _, _, _, usdc_balance = await check_usdc_swap_possibility(wallet.address)
            if usdc_balance < amount:
                logger.warning(f"[FIXED USDC→SOL] Not enough USDC on {wallet.address} ({usdc_balance:.2f} < {amount})")
                failed.append((wallet.address, f"Недостаточно USDC (нужно минимум {amount:.2f})"))
                continue

            try:
                usdc_amount = int(amount * 10**6)
                keypair = Keypair.from_bytes(base58.b58decode(decrypt_seed(wallet.encrypted_seed)))
                logger.info(f"[FIXED USDC→SOL] Swapping {amount} USDC for {wallet.address}")
                txid = await swap_fixed_usdc_to_sol(keypair, usdc_amount)
                if txid and txid != "null":
                    logger.info(f"[FIXED USDC→SOL] Success for {wallet.address} → {txid}")
                    success.append((wallet.address, txid))
                else:
                    logger.error(f"[FIXED USDC→SOL] No route for {wallet.address}")
                    failed.append((wallet.address, "Маршрут не найден, попробуйте позже."))
            except Exception as e:
                logger.exception(f"[FIXED USDC→SOL] Exception during swap for {wallet.address}: {e}")
                failed.append((wallet.address, "Swap failed. Please try again."))

        await send_swap_result(message, success, failed)
        await state.clear()



async def send_swap_result(message_or_cb, success: list, failed: list):
    text = ""

    if success:
        text += "<b>✅Success:</b>\n"
        for addr, tx in success:
            text += f"• <code>{addr[:6]}...{addr[-4:]}</code> → <a href='https://solscan.io/tx/{tx}'>tx</a>\n"

    if failed:
        text += "\n<b>❌Failed:</b>\n"
        for addr, err in failed:
            text += f"• <code>{addr[:6]}...{addr[-4:]}</code> → {err}\n"

    if isinstance(message_or_cb, Message):
        await message_or_cb.answer(text or "❌ Swap failed.", disable_web_page_preview=True)
    else:
        await message_or_cb.message.answer(text or "❌ Swap failed.", disable_web_page_preview=True)


@swap_router.callback_query(F.data == "back_to_wallets")
async def back_to_wallets_from_swap(callback: CallbackQuery, state: FSMContext):
    await go_back_to_wallets(callback, state)