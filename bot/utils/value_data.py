import aiohttp
from typing import List, Dict, Tuple, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from spl.token.instructions import get_associated_token_address
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from bot.utils.token_info import fetch_token_info

from bot.database.models import Wallet, User
from bot.services.solana import get_wallet_balance

SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
MIN_SOL_RESERVE = 0.0032
MIN_USDC_AMOUNT = 1.0


async def get_token_balance(address: str, mint: str) -> int:
    owner = Pubkey.from_string(address)
    mint_pubkey = Pubkey.from_string(mint)
    ata = get_associated_token_address(owner, mint_pubkey)

    async with AsyncClient(SOLANA_RPC_URL) as client:
        ata_info = await client.get_account_info(ata)
        if ata_info.value is None:
            return 0
        resp = await client.get_token_account_balance(ata)
        return int(resp.value.amount)


async def get_token_balances_in_usdc(wallets, mint_address: str) -> dict[str, float]:
    result = {}
    info = await fetch_token_info(mint_address)
    price = info["price"] if info else 0.0
    mint = Pubkey.from_string(mint_address)

    async with AsyncClient(SOLANA_RPC_URL) as client:
        for w in wallets:
            owner = Pubkey.from_string(w.address)
            ata = get_associated_token_address(owner, mint)

            # Сначала проверим, существует ли ATA
            ata_info = await client.get_account_info(ata)
            if ata_info.value is None:
                result[str(owner)] = 0.0  # Если нет аккаунта, значит токенов нет
                continue

            # ATA существует — получаем баланс
            resp = await client.get_token_account_balance(ata)
            if resp.value:
                amount = float(resp.value.ui_amount_string or "0")
                result[str(owner)] = round(amount * price, 3)
            else:
                result[str(owner)] = 0.0

    return result


async def fetch_sol_price() -> float:
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
    return sum(
        balances_usdc.get(wallet.address, 0.0) + balances_sol.get(wallet.address, 0.0) * sol_price
        for wallet in wallets
    )


def get_wallets_text(wallets: List[Wallet]) -> str:
    return "\n".join(
        [f"↳ ({i}) <code>{wallet.address}</code>" for i, wallet in enumerate(wallets, start=1)]
    )


async def get_user_with_wallets(telegram_id: int, session: AsyncSession) -> Optional[User]:
    result = await session.execute(
        select(User).options(selectinload(User.wallets)).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


def get_first_wallet(wallets: List[Wallet]) -> Optional[str]:
    return wallets[0].address if wallets else None


async def check_sol_swap_possibility(address: str) -> Tuple[bool, Optional[str], float]:
    sol_balance = await get_wallet_balance(address)
    if sol_balance <= MIN_SOL_RESERVE:
        return False, "Недостаточно SOL для оплаты комиссии (минимум 0.0032)", sol_balance
    return True, None, sol_balance


async def check_usdc_swap_possibility(address: str) -> Tuple[bool, Optional[str], float, float]:
    sol_balance = await get_wallet_balance(address)
    usdc_balance = await get_usdc_balance(address)

    if usdc_balance < MIN_USDC_AMOUNT:
        return False, "Минимум для свапа — 1.0 USDC", sol_balance, usdc_balance

    if sol_balance <= MIN_SOL_RESERVE:
        return False, f"Недостаточно SOL для комиссии (нужно > {MIN_SOL_RESERVE})", sol_balance, usdc_balance

    return True, None, sol_balance, usdc_balance



async def check_sol_withdraw_possibility(address: str, amount: float) -> Tuple[bool, Optional[str], float]:
    sol_balance = await get_wallet_balance(address)
    fee_buffer = MIN_SOL_RESERVE

    if sol_balance < amount + fee_buffer:
        return False, (
            f"Недостаточно SOL: требуется ≥ {amount + fee_buffer:.4f}, доступно {sol_balance:.4f} "
            f"(включая резерв для комиссии ≈ {fee_buffer:.4f})"
        ), sol_balance

    return True, None, sol_balance


async def check_usdc_withdraw_possibility(address: str, amount: float) -> Tuple[bool, Optional[str], float, float]:
    sol_balance = await get_wallet_balance(address)
    usdc_balance = await get_usdc_balance(address)

    if usdc_balance < amount:
        return False, f"Недостаточно USDC: нужно {amount:.2f}, доступно {usdc_balance:.2f}", sol_balance, usdc_balance

    if sol_balance <= MIN_SOL_RESERVE:
        return False, f"Недостаточно SOL для комиссии (нужно > {MIN_SOL_RESERVE:.4f})", sol_balance, usdc_balance

    return True, None, sol_balance, usdc_balance