from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.database.db import async_session
from bot.database.models import User
from bot.services.solana import get_wallet_balance


async def get_first_wallet_and_balance(telegram_id: int):
    async with async_session() as session:
        result = await session.execute(
            select(User).options(selectinload(User.wallets)).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user and user.wallets:
            wallet = user.wallets[0]
            balance = await get_wallet_balance(wallet.address)
            return wallet.address, balance

        return "you haven't created a wallet yet", 0.0
