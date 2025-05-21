import aiohttp
from typing import List, Dict, Tuple

from bot.database.models import Wallet
from bot.services.solana import get_wallet_balance

SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


async def fetch_sol_price() -> float:
    """Fetches the current SOL price in USDC from Jupiter Aggregator."""
    url = "https://lite-api.jup.ag/price/v2?ids=So11111111111111111111111111111111111111112"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return float(
                    data.get("data", {})
                        .get("So11111111111111111111111111111111111111112", {})
                        .get("price", 0)
                )
    return 0.0


async def get_usdc_balance(address: str) -> float:
    """Fetches the USDC balance for the given wallet address."""
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


async def get_balances_for_wallets(wallets: List[Wallet]) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Returns balances of SOL and USDC for the given list of wallets."""
    balances_sol = {}
    balances_usdc = {}

    for wallet in wallets:
        sol = await get_wallet_balance(wallet.address)
        usdc = await get_usdc_balance(wallet.address)
        balances_sol[wallet.address] = sol
        balances_usdc[wallet.address] = usdc

    return balances_sol, balances_usdc


def calculate_total_usdc_equivalent(
    wallets: List[Wallet],
    balances_sol: Dict[str, float],
    balances_usdc: Dict[str, float],
    sol_price: float
) -> float:
    """Calculates total value of all wallets in USDC equivalent."""
    return sum(
        balances_usdc.get(wallet.address, 0.0) + balances_sol.get(wallet.address, 0.0) * sol_price
        for wallet in wallets
    )


def get_wallets_text(wallets: List[Wallet]) -> str:
    """Returns formatted text of wallet list."""
    return "\n".join(
        [f"↳ ({i}) <code>{wallet.address}</code>" for i, wallet in enumerate(wallets, start=1)]
    )
