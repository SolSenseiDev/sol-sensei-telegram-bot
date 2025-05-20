import aiohttp
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.database.db import async_session
from bot.database.models import User
from bot.services.solana import get_wallet_balance

SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


async def fetch_sol_price():
    url = "https://lite-api.jup.ag/price/v2?ids=So11111111111111111111111111111111111111112"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                price = data.get("data", {}).get("So11111111111111111111111111111111111111112", {}).get("price", 0)
                return float(price)
    return 0.0


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


async def get_usdc_balance(address: str) -> float:
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            address,
            {"mint": USDC_MINT},
            {"encoding": "jsonParsed"}
        ]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(SOLANA_RPC_URL, json=payload, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                accounts = data.get("result", {}).get("value", [])
                if not accounts:
                    return 0.0
                token_info = accounts[0]["account"]["data"]["parsed"]["info"]["tokenAmount"]
                amount = token_info["amount"]
                decimals = token_info["decimals"]
                return float(amount) / (10 ** decimals)
    return 0.0

