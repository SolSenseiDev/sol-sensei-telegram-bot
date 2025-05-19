from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from solana.publickey import PublicKey
from solana.transaction import Transaction
from solana.system_program import TransferParams, transfer

from bot.keyboards.wallets import get_wallets_keyboard
from bot.keyboards.main_menu import get_main_menu
from bot.services.solana import (
    generate_wallet,
    get_wallet_balance,
    decrypt_keypair,
    get_client
)
from bot.services.encryption import encrypt_seed
from bot.database.models import Wallet, User
from bot.database.db import async_session
from bot.states.wallets import WalletStates

wallets_router = Router()
user_selected_wallets = {}

# 💼 Показ всех кошельков
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
                "💼 <b>Ваши кошельки</b>\n\n"
                "У вас пока нет кошельков. Нажмите ➕, чтобы создать."
            )
            await callback.message.edit_text(text, reply_markup=get_wallets_keyboard([], {}, None))
            return

        balances = {}
        total = 0.0

        for wallet in user.wallets:
            balance = await get_wallet_balance(wallet.address)
            balances[wallet.address] = balance
            total += balance

        text = "💼 <b>Ваши кошельки:</b>\n\n"
        for i, wallet in enumerate(user.wallets, start=1):
            text += f"↳ ({i}) <code>{wallet.address}</code>\n"
        text += f"\n<b>Общий баланс:</b> {total:.6f} SOL"

        selected = user_selected_wallets.get(telegram_id)
        await callback.message.edit_text(
            text,
            reply_markup=get_wallets_keyboard(user.wallets, balances, selected)
        )
    await callback.answer()


# ➕ Создание нового кошелька
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
        "🆕 <b>Информация о новом кошельке:</b>\n\n"
        f"<b>Адрес:</b>\n<code>{pubkey}</code>\n\n"
        f"<b>Приватный ключ (base58):</b>\n<code>{seed}</code>\n\n"
        "⚠️ <b>Сохрани это сообщение. Приватный ключ = доступ к кошельку.</b>"
    )
    await callback.message.answer(text_private)
    await show_wallets(callback)


# ✅ Выбор кошелька
@wallets_router.callback_query(F.data.startswith("select_wallet:"))
async def select_wallet(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    address = callback.data.split("select_wallet:")[1]
    user_selected_wallets[telegram_id] = address
    await show_wallets(callback)


# ❌ Удаление выбранного
@wallets_router.callback_query(F.data == "delete_wallet")
async def delete_selected_wallet(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    selected = user_selected_wallets.get(telegram_id)

    if not selected:
        await callback.answer("❗ Сначала выбери кошелек", show_alert=True)
        return

    async with async_session() as session:
        await session.execute(delete(Wallet).where(Wallet.address == selected))
        await session.commit()

    user_selected_wallets.pop(telegram_id, None)
    await callback.answer("🗑️ Кошелек удалён")
    await show_wallets(callback)


# 📤 Запрос адреса вывода
@wallets_router.callback_query(F.data == "withdraw_all")
async def ask_withdraw_address(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📤 Введите адрес Solana-кошелька, на который перевести весь баланс:")
    await state.set_state(WalletStates.waiting_for_withdraw_address)
    await callback.answer()


# 📤 Обработка ввода адреса и вывод всех средств
@wallets_router.message(WalletStates.waiting_for_withdraw_address)
async def withdraw_all_sol(message: Message, state: FSMContext):
    target_address = message.text.strip()

    try:
        recipient = PublicKey(target_address)
    except Exception:
        await message.answer("❌ Неверный адрес. Попробуйте снова.")
        return

    telegram_id = message.from_user.id
    total_sent = 0.0

    async with async_session() as session:
        result = await session.execute(
            select(User).options(selectinload(User.wallets)).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.wallets:
            await message.answer("❗ У вас нет кошельков.")
            await state.clear()
            return

        client = get_client()

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
                    await message.answer(f"⚠️ Ошибка при отправке с {wallet.address}:\n{e}")

    await message.answer(f"✅ Успешно отправлено {total_sent:.6f} SOL на адрес:\n<code>{target_address}</code>")
    await state.clear()


# ⬅️ Назад
@wallets_router.callback_query(F.data == "back_to_menu")
async def back_to_main_menu(callback: CallbackQuery):
    text = (
        "👋 <b>SolSensei мастер торговли в экосистеме Solana.</b>\n\n"
        "💰 <b>Цена SOL:</b> <code>185.25$</code>\n\n"
        "<b>Основной кошелек:</b>\n"
        "↳ <code>5A79gF...XoR3</code>\n"
        "↳ Баланс: <code>0.000995002 SOL</code>"
    )
    await callback.message.edit_text(text, reply_markup=get_main_menu())
    await callback.answer()
