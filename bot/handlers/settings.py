from aiogram.filters import Command
from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from bot.states.settings import SettingsStates
from sqlalchemy import select, update

from bot.database.db import async_session
from bot.database.models import User
from bot.keyboards.settings import get_settings_keyboard

router = Router(name="settings")


async def render_settings(callback: CallbackQuery, state: FSMContext):
    """Render the settings menu with current slippage and fee."""
    async with async_session() as session:
        user = (await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )).scalar_one_or_none()

    slippage = user.slippage_tolerance if user else 1
    fee      = float(user.tx_fee)         if user else 0.001
    keyboard = get_settings_keyboard(slippage, fee)

    try:
        await callback.message.edit_text(
            "⚙️ <b>Transaction Settings</b>\n\n"
            "Here you can adjust slippage tolerance and transaction fee.\n"
            "These settings apply to all your wallets, for both buys and sells.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        err = str(e)
        if "message is not modified" in err or "message to edit not found" in err:
            return
        raise

    await state.set_state(None)
    await callback.answer()


@router.callback_query(F.data == "settings")
async def show_settings(callback: CallbackQuery, state: FSMContext):
    await render_settings(callback, state)
    await state.update_data(settings_msg_id=callback.message.message_id)


@router.callback_query(F.data.in_(["settings_slippage", "settings_fee"]))
async def refresh_settings(callback: CallbackQuery, state: FSMContext):
    """Delete old settings message and send a fresh one."""
    data    = await state.get_data()
    menu_id = data.get("settings_msg_id")
    chat_id = callback.message.chat.id

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass

    async with async_session() as session:
        user = (await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )).scalar_one_or_none()
    slippage = user.slippage_tolerance if user else 1
    fee      = float(user.tx_fee)         if user else 0.001
    kb       = get_settings_keyboard(slippage, fee)

    new_msg = await callback.message.answer(
        "⚙️ <b>Transaction Settings</b>\n\n"
        "Here you can adjust slippage tolerance and transaction fee.\n"
        "These settings apply to all your wallets, for both buys and sells.",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.update_data(settings_msg_id=new_msg.message_id)
    await callback.answer()


@router.callback_query(F.data == "settings_enter_slippage")
async def enter_slippage(callback: CallbackQuery, state: FSMContext):
    """Prompt user to input new slippage tolerance."""
    await state.set_state(SettingsStates.entering_slippage)
    await callback.message.answer("Enter new slippage tolerance (1–100)%:")
    await callback.answer()


@router.message(SettingsStates.entering_slippage)
async def process_slippage(message: Message, state: FSMContext):
    """Validate & save new slippage, delete old settings section, send updated one."""
    try:
        val = int(message.text.strip())
        if not (1 <= val <= 100):
            raise ValueError
    except ValueError:
        await message.answer("❌ Please enter an integer between 1 and 100.")
        return

    async with async_session() as session:
        await session.execute(
            update(User)
            .where(User.telegram_id == message.from_user.id)
            .values(slippage_tolerance=val)
        )
        await session.commit()

    data    = await state.get_data()
    menu_id = data.get("settings_msg_id")
    chat_id = message.chat.id
    if isinstance(menu_id, int):
        try:
            await message.bot.delete_message(chat_id=chat_id, message_id=menu_id)
        except TelegramBadRequest:
            pass

    async with async_session() as session:
        user = (await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )).scalar_one_or_none()
    slippage = user.slippage_tolerance if user else 1
    fee      = float(user.tx_fee)         if user else 0.001
    kb       = get_settings_keyboard(slippage, fee)
    text = (
        "⚙️ <b>Transaction Settings</b>\n\n"
        "Here you can adjust slippage tolerance and transaction fee.\n"
        "These settings apply to all your wallets, for both buys and sells."
    )

    new_msg = await message.answer(text, reply_markup=kb, parse_mode="HTML")

    await state.update_data(settings_msg_id=new_msg.message_id)
    await state.set_state(None)


@router.callback_query(F.data == "settings_enter_fee")
async def enter_fee(callback: CallbackQuery, state: FSMContext):
    """Prompt user to input new transaction fee."""
    await state.set_state(SettingsStates.entering_fee)
    await callback.message.answer("Enter new tx fee in SOL (e.g. 0.001):")
    await callback.answer()


@router.message(SettingsStates.entering_fee)
async def process_fee(message: Message, state: FSMContext):
    """Validate & save new tx fee, then delete old settings and send updated one."""
    try:
        val = float(message.text.strip().replace(",", "."))
        if val < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Please enter a non-negative number.")
        return

    async with async_session() as session:
        await session.execute(
            update(User)
            .where(User.telegram_id == message.from_user.id)
            .values(tx_fee=val)
        )
        await session.commit()

    data    = await state.get_data()
    menu_id = data.get("settings_msg_id")
    chat_id = message.chat.id
    if isinstance(menu_id, int):
        try:
            await message.bot.delete_message(chat_id=chat_id, message_id=menu_id)
        except TelegramBadRequest:
            pass

    async with async_session() as session:
        user = (await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )).scalar_one_or_none()
    slippage = user.slippage_tolerance if user else 1
    fee      = float(user.tx_fee)         if user else 0.001
    kb       = get_settings_keyboard(slippage, fee)
    text = (
        "⚙️ <b>Transaction Settings</b>\n\n"
        "Here you can adjust slippage tolerance and transaction fee.\n"
        "These settings apply to all your wallets, for both buys and sells."
    )

    new_msg = await message.answer(text, reply_markup=kb, parse_mode="HTML")

    await state.update_data(settings_msg_id=new_msg.message_id)
    await state.set_state(None)


async def edit_settings_by_id(bot, chat_id: int, msg_id: int):
    """Fetch fresh values and edit the existing menu by chat_id/message_id."""
    async with async_session() as session:
        user = (await session.execute(
            select(User).where(User.telegram_id == chat_id)
        )).scalar_one_or_none()

    slippage = user.slippage_tolerance if user else 1
    fee      = float(user.tx_fee)         if user else 0.001
    keyboard = get_settings_keyboard(slippage, fee)

    text = (
        "⚙️ <b>Transaction Settings</b>\n\n"
        "Here you can adjust slippage tolerance and transaction fee.\n"
        "These settings apply to all your wallets, for both buys and sells."
    )

    try:
        await bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=msg_id,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        err = str(e)
        if "message is not modified" in err or "message to edit not found" in err:
            return
        raise


@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext):

    async with async_session() as session:
        user = (await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )).scalar_one_or_none()

    slippage = user.slippage_tolerance if user else 1
    fee      = float(user.tx_fee)         if user else 0.001
    keyboard = get_settings_keyboard(slippage, fee)

    text = (
        "⚙️ <b>Transaction Settings</b>\n\n"
        "Here you can adjust slippage tolerance and transaction fee.\n"
        "These settings apply to all your wallets, for both buys and sells."
    )

    data = await state.get_data()
    old_msg_id = data.get("settings_msg_id")
    if old_msg_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=old_msg_id)
        except TelegramBadRequest:
            pass

    sent = await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.update_data(settings_msg_id=sent.message_id)
    await state.clear()
