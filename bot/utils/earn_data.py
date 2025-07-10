from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from bot.database.models import User


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    """
    Fetch a user by telegram_id from the database.
    Wallets are included via selectinload for safe access.
    """
    result = await session.execute(
        select(User)
        .options(selectinload(User.wallets))
        .where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_top_users(session: AsyncSession, limit: int = 10) -> list[tuple[str, int, int]]:
    """
    Fetch top users sorted by points (desc), then by registration time (asc).
    """
    result = await session.execute(
        select(User)
        .options(selectinload(User.wallets))
        .order_by(User.points.desc(), User.id.asc())
        .limit(limit)
    )
    users = result.scalars().all()

    data = []
    for user in users:
        address = user.wallets[0].address if user.wallets else "N/A"
        data.append((address, user.pnl or 0, user.points or 0))

    return data


async def get_user_rank(session: AsyncSession, user_id: int) -> int:
    """
    Get the rank of the user by points and registration order.
    """
    result = await session.execute(
        select(User).order_by(User.points.desc(), User.id.asc())
    )
    users = result.scalars().all()

    for i, user in enumerate(users, start=1):
        if user.id == user_id:
            return i

    return -1
