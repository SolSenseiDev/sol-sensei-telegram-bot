import asyncio
from decimal import Decimal, ROUND_DOWN
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Position, Trade, TradeType, User
from bot.utils.token_info import fetch_token_info


async def record_swap_and_update(
    session: AsyncSession,
    user_id: int,
    wallet_address: str,
    token: str,
    delta_usdc: float,
    delta_tokens: float,
    price_per_token: float,
    txid: str,
) -> None:

    trade = Trade(
        user_id=user_id,
        token=token,
        wallet_address=wallet_address,
        token_amount=Decimal(abs(delta_tokens)),
        amount_usdc=Decimal(abs(delta_usdc)),
        type=TradeType.BUY if delta_tokens > 0 else TradeType.SELL,
        price_per_token=Decimal(price_per_token),
        txid=txid,
    )
    session.add(trade)
    await session.commit()

    if delta_tokens < 0:
        res = await session.execute(
            select(Position).where(
                Position.user_id == user_id,
                Position.wallet_address == wallet_address,
                Position.token == token,
            )
        )
        pos = res.scalar_one_or_none()
        if pos and pos.token_amount > 0:
            sold_amount = Decimal(abs(delta_tokens))
            cost_basis = (
                (Decimal(pos.entry_amount_usdc) / Decimal(pos.token_amount) * sold_amount)
                .quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            )
            received = Decimal(abs(delta_usdc))
            realized = (received - cost_basis).quantize(Decimal("0.01"), rounding=ROUND_DOWN)

            if realized > 0:
                pts_gain = int(realized // 10)
                await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(
                        pnl=User.pnl + int(realized),
                        points=User.points + pts_gain
                    )
                )
                await session.commit()

    # 3) Обновляем Position
    await update_or_create_position(
        session=session,
        user_id=user_id,
        wallet_address=wallet_address,
        token=token,
        new_amount_usdc=delta_usdc,
        new_token_amount=delta_tokens
    )


async def update_or_create_position(
    session: AsyncSession,
    user_id: int,
    wallet_address: str,
    token: str,
    new_amount_usdc: float,
    new_token_amount: float
) -> None:
    res = await session.execute(
        select(Position).where(
            Position.user_id == user_id,
            Position.wallet_address == wallet_address,
            Position.token == token,
        )
    )
    pos = res.scalar_one_or_none()

    if pos:
        old_usdc = Decimal(pos.entry_amount_usdc)
        old_tok = Decimal(pos.token_amount)
        total_tok = old_tok + Decimal(new_token_amount)

        if total_tok <= 0:
            pos.entry_amount_usdc = 0
            pos.token_amount = 0
        else:
            avg_price = (old_usdc + Decimal(new_amount_usdc)) / total_tok
            pos.entry_amount_usdc = avg_price * total_tok
            pos.token_amount = total_tok
    else:
        pos = Position(
            user_id=user_id,
            wallet_address=wallet_address,
            token=token,
            entry_amount_usdc=new_amount_usdc,
            token_amount=new_token_amount
        )
        session.add(pos)

    await session.commit()


async def get_real_time_pnl(
    session: AsyncSession,
    user_id: int,
    token: str,
) -> tuple[float, float]:
    res = await session.execute(
        select(Position).where(
            Position.user_id == user_id,
            Position.token == token,
        )
    )
    positions = res.scalars().all()
    if not positions:
        return 0.0, 0.0

    entry_total = sum(Decimal(p.entry_amount_usdc) for p in positions)
    market_price = Decimal((await fetch_token_info(token)).get("price", 0))
    current_total = sum(Decimal(p.token_amount) * market_price for p in positions)

    pnl = current_total - entry_total
    pct = (pnl / entry_total * 100) if entry_total > 0 else Decimal(0)
    return float(pnl), float(pct)


async def reset_position_if_empty(
    session: AsyncSession,
    user_id: int,
    wallet_address: str,
    token: str,
) -> None:
    res = await session.execute(
        select(Position).where(
            Position.user_id == user_id,
            Position.wallet_address == wallet_address,
            Position.token == token,
        )
    )
    pos = res.scalar_one_or_none()
    if pos and float(pos.token_amount) == 0:
        pos.entry_amount_usdc = 0
        await session.commit()


async def get_position(
    session: AsyncSession,
    user_id: int,
    wallet_address: str,
    token: str,
) -> tuple[float, float]:
    res = await session.execute(
        select(Position).where(
            Position.user_id == user_id,
            Position.wallet_address == wallet_address,
            Position.token == token,
        )
    )
    pos = res.scalar_one_or_none()
    if not pos:
        return 0.0, 0.0
    return float(pos.entry_amount_usdc), float(pos.token_amount)


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
    user.referrals_active = sum(1 for u in referred if (u.pnl or 0) >= 10)
    await session.commit()