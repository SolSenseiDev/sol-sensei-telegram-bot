from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from solders.keypair import Keypair
import base58

from bot.database.db import async_session
from bot.utils.value_data import get_user_with_wallets, get_balances_for_wallets
from bot.handlers.wallets import user_selected_wallets
from bot.utils.common import go_back_to_wallets
from bot.keyboards.swap import get_swap_keyboard, get_create_ata_keyboard
from bot.services.encryption import decrypt_seed
from bot.constants import LAMPORTS_PER_SOL, MIN_LAMPORTS_RESERVE
from bot.services.rust_swap import swap_all_sol_to_usdc, swap_all_usdc_to_sol, create_wsol_ata
from bot.utils.check_ata import has_wsol_ata

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
    telegram_id = callback.from_user.id
    selected_addresses = user_selected_wallets.get(telegram_id, set())

    async with async_session() as session:
        user = await get_user_with_wallets(telegram_id, session)
        if not user:
            await callback.answer("❌ User not found.")
            return

        selected_wallets = [w for w in user.wallets if w.address in selected_addresses]
        if not selected_wallets:
            await callback.answer("❗ No wallets selected.")
            return

        balances_sol, _ = await get_balances_for_wallets(selected_wallets)

        success, failed = [], []

        for wallet in selected_wallets:
            sol = balances_sol.get(wallet.address, 0.0)
            lamports = int(sol * LAMPORTS_PER_SOL)

            print(f"\n🔍 Обработка: {wallet.address} | Баланс: {sol:.4f} SOL")

            if lamports <= MIN_LAMPORTS_RESERVE:
                failed.append((wallet.address, "Too little SOL (≤ 0.0025 reserved for fees)"))
                continue
            if sol < 0.01:
                failed.append((wallet.address, "Минимум для свапа — 0.01 SOL"))
                continue

            ata_exists = await has_wsol_ata(wallet.address)
            if not ata_exists:
                await callback.message.answer(
                    f"❗ У кошелька <code>{wallet.address}</code> отсутствует wSOL ATA. Создайте его перед свапом.",
                    reply_markup=get_create_ata_keyboard()
                )
                continue

            try:
                keypair = Keypair.from_bytes(base58.b58decode(decrypt_seed(wallet.encrypted_seed)))
                txid = await swap_all_sol_to_usdc(keypair, lamports)
                if txid and txid != "null":
                    success.append((wallet.address, txid))
                else:
                    failed.append((wallet.address, "Swap failed — пустой txid."))
            except Exception as e:
                print(f"❌ Ошибка: {e}")
                failed.append((wallet.address, "Swap failed. Please try again."))

        await send_swap_result(callback, success, failed)


@swap_router.callback_query(F.data == "swap_all_usdc_sol")
async def handle_swap_all_usdc_sol(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    selected_addresses = user_selected_wallets.get(telegram_id, set())

    async with async_session() as session:
        user = await get_user_with_wallets(telegram_id, session)
        if not user:
            await callback.answer("❌ User not found.")
            return

        selected_wallets = [w for w in user.wallets if w.address in selected_addresses]
        if not selected_wallets:
            await callback.answer("❗ No wallets selected.")
            return

        _, balances_usdc = await get_balances_for_wallets(selected_wallets)

        success, failed = [], []

        for wallet in selected_wallets:
            usdc = balances_usdc.get(wallet.address, 0.0)
            if usdc < 0.01:
                failed.append((wallet.address, "Минимум для свапа — 0.01 USDC"))
                continue

            try:
                keypair = Keypair.from_bytes(base58.b58decode(decrypt_seed(wallet.encrypted_seed)))
                txid = await swap_all_usdc_to_sol(keypair)
                if txid and txid != "null":
                    success.append((wallet.address, txid))
                else:
                    failed.append((wallet.address, "Swap failed — пустой txid."))
            except Exception as e:
                print(f"❌ Ошибка: {e}")
                failed.append((wallet.address, "Swap failed. Please try again."))

        await send_swap_result(callback, success, failed)


async def send_swap_result(callback: CallbackQuery, success: list, failed: list):
    if success and failed:
        text = "⚠️ <b>Partial Success</b>\n\n"
    elif success:
        text = "✅ <b>Swap Complete</b>\n\n"
    else:
        text = "❌ <b>Swap Failed</b>\n\n"

    if success:
        text += "<b>Success:</b>\n"
        for addr, tx in success:
            text += f"• <code>{addr[:6]}...{addr[-4:]}</code> → <a href='https://solscan.io/tx/{tx}'>tx</a>\n"

    if failed:
        text += "\n<b>Failed:</b>\n"
        for addr, err in failed:
            text += f"• <code>{addr[:6]}...{addr[-4:]}</code> → {err}\n"

    await callback.message.answer(text, disable_web_page_preview=True)
    await callback.answer()


@swap_router.callback_query(F.data == "create_wsol_ata")
async def create_ata_handler(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    selected_addresses = user_selected_wallets.get(telegram_id, set())

    if not selected_addresses:
        await callback.answer("❗ No wallet selected.", show_alert=True)
        return

    async with async_session() as session:
        user = await get_user_with_wallets(telegram_id, session)
        if not user:
            await callback.answer("❌ User not found.")
            return

        wallet = next((w for w in user.wallets if w.address in selected_addresses), None)
        if not wallet:
            await callback.answer("❗ Wallet not found.", show_alert=True)
            return

        try:
            keypair = Keypair.from_bytes(base58.b58decode(decrypt_seed(wallet.encrypted_seed)))
            await create_wsol_ata(keypair)
            await callback.message.answer("✅ wSOL ATA создан!")
        except Exception as e:
            await callback.message.answer(f"❌ Ошибка при создании ATA: {e}")

        await callback.answer()


@swap_router.callback_query(F.data == "swap_fixed_sol_usdc")
async def handle_swap_fixed_sol_usdc(callback: CallbackQuery):
    await callback.answer("🛠️ Fixed SOL → USDC not implemented yet.", show_alert=True)


@swap_router.callback_query(F.data == "swap_fixed_usdc_sol")
async def handle_swap_fixed_usdc_sol(callback: CallbackQuery):
    await callback.answer("🛠️ Fixed USDC → SOL not implemented yet.", show_alert=True)


@swap_router.callback_query(F.data == "back_to_wallets")
async def back_to_wallets_from_swap(callback: CallbackQuery, state: FSMContext):
    await go_back_to_wallets(callback, state)
