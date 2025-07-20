import asyncio
from datetime import datetime
import inspect

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from sqlalchemy import select
from bot.database.models import User
from bot.database.db import async_session

from bot.states.buy_sell import BuySellStates
from bot.utils.token_info import fetch_token_info, format_token_info_message
from bot.utils.value_data import (
    check_sol_swap_possibility,
    check_token_balance_for_sell,
    get_user_with_wallets,
    get_balances_for_wallets,
    get_token_balances_in_usdc,
    get_token_balance,
)
from bot.utils.pnl import record_swap_and_update, get_real_time_pnl
from bot.services.rust_swap import buy_sell_token_from_wallets
from bot.services.solana import get_wallet_balance
from bot.utils.common import go_back_to_main_menu
from bot.keyboards.buy_sell import get_buy_sell_keyboard_with_wallets

router = Router(name="buy_sell")


async def run_buy_sell(
    source,
    ca: str,
    mode: str,
    wallets: list,
    get_amount_fn
):
    info = await fetch_token_info(ca)
    if not info or float(info.get("price", 0)) <= 0:
        await source.answer("❌ Failed to fetch token info.")
        return

    # load user and compute slippage/CU‐fee
    async with async_session() as session:
        user = (await session.execute(
            select(User).where(User.id == wallets[0].user_id)
        )).scalar_one_or_none()
    slippage_bps = (user.slippage_tolerance * 100) if user else 100
    total_fee_lamports = int((float(user.tx_fee) if user else 0.001) * 1_000_000_000)

    # convert SOL‐fee into USDC to subtract only on sell
    SOL_MINT = "So11111111111111111111111111111111111111112"
    sol_info = await fetch_token_info(SOL_MINT)
    sol_price = float(sol_info.get("price", 0)) if sol_info else 0.0
    fee_sol = float(user.tx_fee) if user else 0.001
    fee_usdc = fee_sol * sol_price

    token_price = float(info["price"])
    success, failed = [], {}

    for w in wallets:
        # determine amount in lamports or tokens
        amt = await (get_amount_fn(w) if inspect.iscoroutinefunction(get_amount_fn)
                     else get_amount_fn(w))
        if not isinstance(amt, int) or amt <= 0:
            failed[w.address] = "❌ Invalid amount"
            continue

        # check balances
        if mode == "buy":
            ok, err, sol_bal = await check_sol_swap_possibility(w.address)
            if not ok or sol_bal * 1e9 < amt:
                failed[w.address] = err or "❌ Not enough SOL"
                continue
        else:
            ok, err, tok_bal = await check_token_balance_for_sell(w.address, ca)
            if not ok or tok_bal < amt:
                failed[w.address] = err or "❌ Not enough tokens"
                continue

        # perform the swap
        res = await buy_sell_token_from_wallets(
            [w],
            ca,
            mode,
            amt,
            slippage_bps=slippage_bps,
            total_fee_lamports=total_fee_lamports,
        )
        if not (res and res[0]):
            failed[w.address] = list(res[1].values())[0] if res and res[1] else "❌ Swap failed"
            continue

        # unpack result
        txid = res[0][0][1]
        token_amount = amt / 1e6
        amount_usdc = token_amount * token_price

        # compute deltas: for buy full cost, for sell net of fee
        if mode == "buy":
            delta_usdc =  amount_usdc
            delta_tokens =  token_amount
        else:
            delta_usdc = -(amount_usdc - fee_usdc)
            delta_tokens = -token_amount

        # record trade and update PnL/positions
        async with async_session() as session:
            await record_swap_and_update(
                session=session,
                user_id=w.user_id,
                wallet_address=w.address,
                token=ca,
                delta_usdc=delta_usdc,
                delta_tokens=delta_tokens,
                price_per_token=token_price,
                txid=txid
            )

        success.append((w.address, txid))

    await asyncio.sleep(0.25)
    await send_buy_sell_result(source, success, failed)


async def get_token_ui_components(
    wallets,
    ca: str,
    mode: str,
    selected: set
):
    info = await fetch_token_info(ca)
    if not info:
        return None, None, None

    pnl = None
    if wallets:
        async with async_session() as session:
            pnl = await get_real_time_pnl(session, wallets[0].user_id, ca)

    if mode == "sell":
        balances = await get_token_balances_in_usdc(wallets, ca)
        tuples = [(w.address, balances.get(w.address, 0.0)) for w in wallets]
        keyboard = get_buy_sell_keyboard_with_wallets(
            ca, tuples, selected, mode,
            token_price=info["price"],
            token_balances=balances
        )
    else:
        sol_balances, _ = await get_balances_for_wallets(wallets)
        tuples = [(w.address, sol_balances.get(w.address, 0.0)) for w in wallets]
        keyboard = get_buy_sell_keyboard_with_wallets(ca, tuples, selected, mode)

    caption = format_token_info_message(info, updated_at=datetime.utcnow(), token_pnl=pnl)
    return caption, keyboard, info.get("icon")


def get_buy_amount_in_lamports(value: str) -> int:
    try:
        sol_amount = float(value.replace(",", "."))
        if sol_amount <= 0:
            return 0
        return int(sol_amount * 1_000_000_000)
    except Exception:
        return 0


async def get_sell_amount(wallet_address: str, token_mint: str, percent: int) -> int:
    try:
        token_balance = await get_token_balance(wallet_address, token_mint)
        return int(token_balance * percent / 100)
    except Exception:
        return 0


async def send_token_ui(msg_or_cb, caption: str, keyboard, icon_url: str):
    is_callback = isinstance(msg_or_cb, CallbackQuery)
    msg = msg_or_cb.message if is_callback else msg_or_cb

    try:
        if is_callback:
            try:
                await msg.delete()
            except TelegramBadRequest:
                pass

        if icon_url:
            await msg_or_cb.bot.send_photo(
                chat_id=msg.chat.id,
                photo=icon_url,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await msg_or_cb.bot.send_message(
                chat_id=msg.chat.id,
                text=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
                disable_web_page_preview=True
            )

    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            await msg.answer(f"❌ Edit error: {e}")


@router.message(BuySellStates.entering_buy_amount)
async def handle_custom_buy_amount(message: Message, state: FSMContext):
    try:
        value = float(message.text.replace(",", "."))
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Enter a valid SOL amount (e.g., 0.1)")
        return

    data = await state.get_data()
    callback_query: CallbackQuery | None = data.get("last_callback")

    if callback_query:
        try:
            await callback_query.message.delete()
        except:
            pass
        try:
            await callback_query.answer("⏳ Processing buy...", show_alert=True)
        except:
            pass

    await message.answer("⏳ Processing buy...")

    ca = data.get("token_ca")
    wallet_addrs = set(data.get("selected_wallets", []))

    async with async_session() as session:
        user = await get_user_with_wallets(message.from_user.id, session)
    selected_wallets = [w for w in user.wallets if w.address in wallet_addrs]

    async def get_amount(_): return int(value * 1_000_000_000)

    await run_buy_sell(message, ca, "buy", selected_wallets, get_amount)

    await state.set_state(BuySellStates.choosing_mode)
    components = await get_token_ui_components(user.wallets, ca, "buy", wallet_addrs)
    await send_token_ui(message, *components)


@router.message(BuySellStates.entering_sell_percent)
async def handle_custom_sell_percent(message: Message, state: FSMContext):
    try:
        percent = int(message.text.strip())
        if not (1 <= percent <= 100):
            raise ValueError
    except ValueError:
        await message.answer("❌ Enter a number between 1 and 100 — the percentage of tokens to sell.")
        return

    await message.answer("⏳ Processing sell...")

    data = await state.get_data()
    ca = data.get("token_ca")
    wallet_addrs = set(data.get("selected_wallets", []))

    last_callback: CallbackQuery | None = data.get("last_callback")
    if last_callback:
        try:
            await last_callback.message.delete()
        except:
            pass

    async with async_session() as session:
        user = await get_user_with_wallets(message.from_user.id, session)
    selected_wallets = [w for w in user.wallets if w.address in wallet_addrs]

    async def get_amount(w):
        return await get_sell_amount(w.address, ca, percent)

    await run_buy_sell(message, ca, "sell", selected_wallets, get_amount)

    await state.set_state(BuySellStates.choosing_mode)
    components = await get_token_ui_components(user.wallets, ca, "sell", wallet_addrs)
    await send_token_ui(message, *components)


@router.callback_query(lambda c: (c.data.startswith("buy:") or c.data.startswith("sell:")) and ":custom" not in c.data)
async def handle_amount_selection(callback: CallbackQuery, state: FSMContext):
    try:
        action, value, ca = callback.data.split(":", 2)
        mode = "buy" if action == "buy" else "sell"

        data = await state.get_data()
        wallet_addrs = set(data.get("selected_wallets", []))
        if not wallet_addrs:
            await callback.answer("❗ Select at least one wallet.")
            return

        try:
            await callback.answer("⏳ Processing transaction...", show_alert=True)
        except TelegramBadRequest:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer("⏳ Processing transaction...")

        async with async_session() as session:
            user = await get_user_with_wallets(callback.from_user.id, session)
        selected_wallets = [w for w in user.wallets if w.address in wallet_addrs]

        if mode == "buy":
            lamports = get_buy_amount_in_lamports(value)

            async def get_amount(_): return lamports
        else:
            percent = int(value)

            async def get_amount(w): return await get_sell_amount(w.address, ca, percent)

        await run_buy_sell(callback, ca, mode, selected_wallets, get_amount)

        await state.update_data(selected_wallets=list(wallet_addrs))
        components = await get_token_ui_components(user.wallets, ca, mode, wallet_addrs)
        await send_token_ui(callback, *components)

    except Exception as e:
        await callback.message.answer(f"❌ An error occurred: {str(e)}")


@router.callback_query(F.data.startswith("buy:custom:") | F.data.startswith("sell:custom:"))
async def handle_custom_amount_request(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("selected_wallets"):
        await callback.answer("❗ Select at least one wallet.")
        return

    await state.update_data(last_callback=callback)

    if "buy:custom" in callback.data:
        await state.set_state(BuySellStates.entering_buy_amount)
        await callback.message.answer("💸 Enter the SOL amount to buy the token:")
    else:
        await state.set_state(BuySellStates.entering_sell_percent)
        await callback.message.answer("📉 Enter the percentage (1-100) of tokens you want to sell:")

    await callback.answer()


async def send_buy_sell_result(message_or_cb, success: list, failed: dict):
    lines = []

    if success:
        lines.append("<b>✅ Successful transactions:</b>")
        for addr, tx in success:
            lines.append(f"• <code>{addr[:6]}...{addr[-4:]}</code> → <a href='https://solscan.io/tx/{tx}'>tx</a>")

    if failed:
        lines.append("\n<b>❌ Errors:</b>")
        for addr, err in failed.items():
            err_text = str(err).strip().replace("<", "").replace(">", "")
            lines.append(f"• <code>{addr[:6]}...{addr[-4:]}</code> → {err_text}")

    text = "\n".join(lines) if lines else "❌ Operation failed."

    if isinstance(message_or_cb, Message):
        await message_or_cb.answer(text, parse_mode="HTML", disable_web_page_preview=True)
    else:
        await message_or_cb.message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


async def handle_confirm_buy_sell(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ca = data.get("token_ca")
    mode = data.get("mode", "buy")
    wallets = data.get("selected_wallets", [])

    if not wallets:
        await callback.answer("❗ Select at least one wallet.")
        return

    await callback.answer("⏳ Processing...", show_alert=True)

    async with async_session() as session:
        user = await get_user_with_wallets(callback.from_user.id, session)
    selected_wallets = [w for w in user.wallets if w.address in wallets]

    async def get_amount(w):
        if mode == "buy":
            sol = await get_wallet_balance(w.address)
            return int(sol * 1_000_000_000)  # no buffer — Rust will handle
        else:
            return await get_token_balance(w.address, ca)

    await run_buy_sell(callback, ca, mode, selected_wallets, get_amount)

    await state.set_state(BuySellStates.choosing_mode)
    components = await get_token_ui_components(user.wallets, ca, mode, set(wallets))
    await send_token_ui(callback, *components)


@router.callback_query(lambda c: c.data == "back_to_main")
async def handle_back(callback: CallbackQuery, state: FSMContext):
    await go_back_to_main_menu(callback, state)


@router.callback_query(F.data.in_({"buy_token", "sell_token"}))
async def handle_trade_mode_selection(callback: CallbackQuery, state: FSMContext):
    mode = "buy" if callback.data == "buy_token" else "sell"
    await state.update_data(mode=mode)
    await callback.message.answer("📥 Enter the token address (CA):")
    await state.set_state(BuySellStates.waiting_for_ca)
    await callback.answer()


@router.message(BuySellStates.waiting_for_ca)
async def handle_token_address(message: Message, state: FSMContext):
    ca = message.text.strip()
    info = await fetch_token_info(ca)
    if not info:
        await message.answer("❌ Failed to find token by this address. Make sure the CA is correct.")
        return

    data = await state.get_data()
    mode = data.get("mode", "buy")

    await state.update_data(token_ca=ca)

    async with async_session() as session:
        user = await get_user_with_wallets(message.from_user.id, session)

    if not user or not user.wallets:
        await message.answer("❗ You don't have any wallets. Please add at least one.")
        return

    selected = set(data.get("selected_wallets", []))
    components = await get_token_ui_components(user.wallets, ca, mode, selected)
    await send_token_ui(message, *components)

    await state.set_state(BuySellStates.choosing_mode)


@router.callback_query(F.data.startswith("tw:"))
async def handle_wallet_toggle(callback: CallbackQuery, state: FSMContext):
    _, address = callback.data.split(":", 1)
    data = await state.get_data()
    ca = data.get("token_ca")
    mode = data.get("mode", "buy")
    selected = set(data.get("selected_wallets", []))
    selected.symmetric_difference_update([address])
    await state.update_data(selected_wallets=list(selected))

    async with async_session() as session:
        user = await get_user_with_wallets(callback.from_user.id, session)

    components = await get_token_ui_components(user.wallets, ca, mode, selected)
    await send_token_ui(callback, *components)

    await callback.answer()


@router.callback_query(F.data.startswith("sm:"))
async def handle_mode_switch(callback: CallbackQuery, state: FSMContext):
    try:
        _, mode, ca = callback.data.split(":")
        if mode not in {"buy", "sell"}:
            await callback.answer("❌ Invalid mode.")
            return
    except ValueError:
        await callback.answer("❌ Data format error.")
        return

    await state.update_data(mode=mode, token_ca=ca)
    data = await state.get_data()
    selected = set(data.get("selected_wallets", []))

    async with async_session() as session:
        user = await get_user_with_wallets(callback.from_user.id, session)

    components = await get_token_ui_components(user.wallets, ca, mode, selected)
    await send_token_ui(callback, *components)

    await callback.answer()


@router.callback_query(F.data.startswith("refresh:"))
async def handle_refresh(callback: CallbackQuery, state: FSMContext):
    try:
        _, ca = callback.data.split(":", 1)
        if not ca:
            raise ValueError
    except ValueError:
        await callback.answer("❌ Data error.")
        return

    data = await state.get_data()
    mode = data.get("mode", "buy")
    selected = set(data.get("selected_wallets", []))

    async with async_session() as session:
        user = await get_user_with_wallets(callback.from_user.id, session)

    components = await get_token_ui_components(user.wallets, ca, mode, selected)
    await send_token_ui(callback, *components)

    await callback.answer("🔄 Refreshed.")