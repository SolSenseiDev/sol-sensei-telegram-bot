from decimal import Decimal, ROUND_DOWN
from sqlalchemy import select, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import Position, Trade, TradeType, User
from bot.utils.token_info import fetch_token_info
from bot.database.models import ReferralReward

MINIMUM_REMAINING_THRESHOLD = Decimal("0.0001")


async def award_points_for_active_referral(session: AsyncSession, user: User) -> None:
    """
    Awards 10 points to the referrer when a user becomes active (PnL >= 10)
    and no reward has been granted yet.
    """
    if not user.referred_by:
        return

    if (user.pnl or Decimal(0)) < Decimal("100"):
        return

    # Check if reward already granted
    existing = await session.execute(
        select(ReferralReward).where(ReferralReward.referee_id == user.id)
    )
    if existing.scalar_one_or_none():
        return

    # Find referrer by their referral code
    referrer_result = await session.execute(
        select(User).where(User.referral_code == user.referred_by)
    )
    referrer = referrer_result.scalar_one_or_none()
    if not referrer:
        return

    # Grant 10 points
    referrer.points = (referrer.points or 0) + 10
    reward = ReferralReward(referrer_id=referrer.id, referee_id=user.id)
    session.add(reward)


async def calculate_realized_pnl(
    session: AsyncSession,
    user_id: int,
    wallet_address: str,
    token: str,
    sell_amount_tokens: Decimal,
    sell_amount_usdc: Decimal
) -> Decimal:
    """
    Calculate realized PnL for a partial or full token sale based on position.
    If there's no position — return 0.
    If sale results in profit — return positive Decimal. Losses and zero are ignored later.
    """

    result = await session.execute(
        select(Position).where(
            Position.user_id == user_id,
            Position.wallet_address == wallet_address,
            Position.token == token
        )
    )
    position = result.scalar_one_or_none()

    if not position or position.token_amount <= 0:
        return Decimal("0")

    entry_total = position.entry_amount_usdc
    held_tokens = position.token_amount

    if sell_amount_tokens > held_tokens:
        sell_amount_tokens = held_tokens

    entry_proportional = entry_total * (sell_amount_tokens / held_tokens)

    realized = sell_amount_usdc - entry_proportional


    return realized


async def update_realized_pnl(session: AsyncSession, user_id: int, delta: Decimal) -> None:
    """
    Increment user's realized PnL by `delta` only if it's positive.
    Also awards points: +1 for every $10 of total PnL.
    Triggers referral bonus if user becomes active (>= $10 realized PnL).
    """
    if delta <= 0:
        return

    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if user:
        # Update total PnL
        user.pnl = (user.pnl or Decimal(0)) + delta

        # Recalculate total points
        total_points = int(user.pnl // Decimal("10"))
        current_points = user.points or 0

        if total_points > current_points:
            earned = total_points - current_points
            user.points = total_points

        # Award referral bonus if applicable
        await award_points_for_active_referral(session, user)

    await session.commit()


async def record_swap_and_update(
    session,
    user_id: int,
    wallet_address: str,
    token: str,
    delta_usdc: float,
    delta_tokens: float,
    price_per_token: float,
    txid: str,
) -> None:

    if abs(delta_tokens) < 0.000001:
        return

    if delta_tokens < 0:
        realized = await calculate_realized_pnl(
            session=session,
            user_id=user_id,
            wallet_address=wallet_address,
            token=token,
            sell_amount_tokens=Decimal(str(abs(delta_tokens))),
            sell_amount_usdc=Decimal(str(abs(delta_usdc))),
        )
    else:
        realized = Decimal("0")

    trade = Trade(
        user_id=user_id,
        token=token,
        wallet_address=wallet_address,
        token_amount=Decimal(str(abs(delta_tokens))),
        amount_usdc=Decimal(str(abs(delta_usdc))),
        type=TradeType.BUY if delta_tokens > 0 else TradeType.SELL,
        price_per_token=Decimal(str(price_per_token)),
        txid=txid,
        realized_pnl=realized,
    )
    session.add(trade)

    await update_or_create_position(
        session=session,
        user_id=user_id,
        wallet_address=wallet_address,
        token=token,
        delta_tokens=Decimal(str(delta_tokens)),
        delta_usdc=Decimal(str(delta_usdc)),
    )

    await update_realized_pnl(session, user_id, realized)
    await session.commit()


async def update_or_create_position(
    session: AsyncSession,
    user_id: int,
    wallet_address: str,
    token: str,
    delta_tokens: Decimal,
    delta_usdc: Decimal,
):
    result = await session.execute(
        select(Position).where(
            Position.user_id == user_id,
            Position.wallet_address == wallet_address,
            Position.token == token
        )
    )
    position = result.scalar_one_or_none()

    if delta_tokens > 0:
        if position:
            new_token_amount = position.token_amount + delta_tokens
            new_entry_amount_usdc = position.entry_amount_usdc + delta_usdc
            await session.execute(update(Position)
                .where(Position.id == position.id)
                .values(token_amount=new_token_amount, entry_amount_usdc=new_entry_amount_usdc)
            )
        else:
            session.add(Position(
                user_id=user_id,
                wallet_address=wallet_address,
                token=token,
                token_amount=delta_tokens,
                entry_amount_usdc=delta_usdc
            ))

    elif delta_tokens < 0 and position:
        if position.token_amount < abs(delta_tokens):
            delta_tokens = position.token_amount

        remaining_tokens = position.token_amount + delta_tokens
        remaining_usdc = position.entry_amount_usdc * (remaining_tokens / position.token_amount) if position.token_amount else Decimal("0")

        await session.execute(update(Position)
            .where(Position.id == position.id)
            .values(token_amount=remaining_tokens, entry_amount_usdc=remaining_usdc)
        )

    await session.commit()


async def get_real_time_pnl(
    session: AsyncSession,
    user_id: int,
    wallet_address: str,
    token: str
) -> tuple[float, float]:
    result = await session.execute(
        select(Position).where(
            Position.user_id == user_id,
            Position.wallet_address == wallet_address,
            Position.token == token
        )
    )
    position = result.scalar_one_or_none()
    if not position:
        return 0.0, 0.0

    entry_total = position.entry_amount_usdc
    token_amount = position.token_amount.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)

    if token_amount <= 0 and entry_total > 0:
        return 0.0, 0.0

    info = await fetch_token_info(token)
    if not info or float(info.get("price", 0)) <= 0:
        return 0.0, float(token_amount)

    current_price = Decimal(str(info["price"]))
    current_total = token_amount * current_price
    pnl = current_total - entry_total

    return float(pnl), float(token_amount)


async def reset_position_if_empty(
    session: AsyncSession,
    user_id: int,
    wallet_address: str,
    token: str
) -> None:
    result = await session.execute(
        select(Position).where(
            Position.user_id == user_id,
            Position.wallet_address == wallet_address,
            Position.token == token
        )
    )
    position = result.scalar_one_or_none()

    if position:
        remaining = position.token_amount.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        if remaining < MINIMUM_REMAINING_THRESHOLD:
            await session.execute(
                delete(Position).where(
                    Position.user_id == user_id,
                    Position.wallet_address == wallet_address,
                    Position.token == token
                )
            )
            await session.commit()


async def get_position(
    session: AsyncSession,
    user_id: int,
    wallet_address: str,
    token: str
) -> tuple[Decimal, Decimal]:
    result = await session.execute(
        select(Position).where(
            Position.user_id == user_id,
            Position.wallet_address == wallet_address,
            Position.token == token
        )
    )
    position = result.scalar_one_or_none()

    if position:
        entry = position.entry_amount_usdc
        remaining = position.token_amount.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        return entry, remaining

    return Decimal(0), Decimal(0)


async def update_active_referrals(session: AsyncSession, user: User) -> None:
    if not user.referral_code:
        user.referrals_total = 0
        user.referrals_active = 0
        return

    res = await session.execute(
        select(User).where(User.referred_by == user.referral_code)
    )
    referred = res.scalars().all()
    user.referrals_total = len(referred)
    user.referrals_active = sum(1 for u in referred if (u.pnl or 0) >= 100)
    await session.commit()
