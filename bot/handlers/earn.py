from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import secrets
import string
from bot.database.models import User
from sqlalchemy import select
from bot.utils.pnl import update_active_referrals

from bot.database.db import async_session
from bot.utils.earn_data import get_user_by_telegram_id, get_top_users, get_user_rank

earn_router = Router()


def get_earn_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📣 My Referral Code", callback_data="my_referral"),
                InlineKeyboardButton(text="🔑 Enter Referral Code", callback_data="enter_ref_code")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_main")
            ]
        ]
    )


def shorten(address: str) -> str:
    return f"{address[:4]}...{address[-4:]}" if address != "N/A" else "N/A"


def render_leaderboard(users: list[tuple[str, int, int]]) -> str:
    if not users:
        return "🏅 <b>Leaderboards: Top 10 Users</b>\n<code>No users yet.</code>\n"

    max_pnl_len = max(len(str(pnl)) for _, pnl, _ in users)
    max_pts_len = max(len(str(points)) for _, _, points in users)

    lines = [
        f"<code>{i:>2}  {shorten(addr):<14}${pnl:<{max_pnl_len}}    ({pts:>{max_pts_len}} pts)</code>"
        for i, (addr, pnl, pts) in enumerate(users, start=1)
    ]

    return "🏅 <b>Leaderboards: Top 10 Users</b>\n" + "\n".join(lines) + "\n"


async def send_earn_menu(target):
    telegram_id = (
        target.from_user.id
        if isinstance(target, CallbackQuery)
        else target.from_user.id
    )

    async with async_session() as session:
        user = await get_user_by_telegram_id(session, telegram_id)
        top_users = await get_top_users(session)
        rank = await get_user_rank(session, user.id) if user else "N/A"
        leaderboard = render_leaderboard(top_users)

        wallet_display = (
            shorten(user.wallets[0].address) if user and user.wallets else "N/A"
        )

        text = (
            "🏆 <b>Welcome to Earn with Sensei!</b>\n\n"
            f"{leaderboard}\n"
            f"👤 <b>You:</b> {wallet_display}\n"
            f"🏅 <b>Rank:</b> #{rank}\n"
            f"💸 <b>PNL:</b> ${user.pnl if user else 0}\n"
            f"🏆 <b>Points:</b> {user.points if user else 0}\n"
            f"👥 <b>Referrals:</b> {user.referrals_total if user else 0} "
            f"({user.referrals_active if user else 0} active)\n\n"
            "📚 <b>How to earn points:</b>\n"
            "• 📈 +1 point for every $10 profit (PNL)\n"
            "• 👥 +10 points for each active referral\n"
            "   (referral must earn 10 PNL points)"
        )

        keyboard = get_earn_menu_keyboard()

        if isinstance(target, CallbackQuery):
            await target.message.bot.send_message(
                chat_id=telegram_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await target.answer(text, reply_markup=keyboard, parse_mode="HTML")


@earn_router.message(F.text.lower() == "/earn")
async def earn_command_handler(message: Message):
    await send_earn_menu(message)


@earn_router.callback_query(F.data == "earn_menu")
async def earn_menu_handler(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass

    await send_earn_menu(callback)
    await callback.answer()


class ReferralFSM(StatesGroup):
    entering_code = State()


@earn_router.callback_query(F.data == "my_referral")
async def my_referral_handler(callback: CallbackQuery):
    async with async_session() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)

        if not user:
            await callback.answer("User not found", show_alert=True)
            return

        if not user.referral_code:
            while True:
                code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
                exists = await session.execute(select(User).where(User.referral_code == code))
                if not exists.scalar_one_or_none():
                    user.referral_code = code
                    await session.commit()
                    break
        else:
            code = user.referral_code

        await callback.message.answer(f"📣 Your referral code:\n<code>{code}</code>", parse_mode="HTML")
        await callback.answer()


@earn_router.callback_query(F.data == "enter_ref_code")
async def enter_ref_code_handler(callback: CallbackQuery, state: FSMContext):
    async with async_session() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        if not user:
            await callback.answer("User not found", show_alert=True)
            return

        if user.referred_by:
            await callback.message.answer(f"🧾 You've already entered a referral code:\n<code>{user.referred_by}</code>", parse_mode="HTML")
            await callback.answer()
            return

        await state.set_state(ReferralFSM.entering_code)
        await callback.message.answer("🔑 Please enter your referral code:")
        await callback.answer()


@earn_router.message(ReferralFSM.entering_code)
async def process_ref_code_entry(message: Message, state: FSMContext):
    entered_code = message.text.strip().upper()

    async with async_session() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)

        if not user or user.referred_by:
            await message.answer("⚠️ You can't enter a referral code again.")
            await state.clear()
            return

        result = await session.execute(select(User).where(User.referral_code == entered_code))
        referrer = result.scalar_one_or_none()

        if not referrer or referrer.id == user.id:
            await message.answer("❌ Invalid referral code.")
            await state.clear()
            return

        user.referred_by = entered_code
        await update_active_referrals(session, referrer)
        await session.commit()

        await message.answer("✅ Referral code accepted!")
        await state.clear()