import json
import base58
import httpx
from solders.keypair import Keypair
from bot.services.encryption import decrypt_seed

RUST_API_URL = "http://localhost:3030/swap"


async def call_rust_swapper(action: str, keypair: Keypair, ca: str = None, amount: int = None) -> dict:
    try:
        privkey_b58 = base58.b58encode(bytes(keypair)).decode()

        payload = {
            "action": action,
            "private_key": privkey_b58,
        }
        if ca is not None:
            payload["ca"] = str(ca)
        if amount is not None:
            payload["amount"] = amount

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(RUST_API_URL, json=payload)

        if response.status_code != 200:
            raise Exception(f"Rust API returned status {response.status_code}")

        result = response.json()

        if not result.get("success"):
            raise Exception(result.get("error", "Unknown Rust error"))

        if "txid" not in result:
            raise Exception("Rust response missing 'txid' despite success=True")

        return result

    except Exception as e:
        return {
            "success": False,
            "txid": None,
            "error": str(e),
        }


async def swap_all_sol_to_usdc(keypair: Keypair, lamports: int) -> str:
    result = await call_rust_swapper("sol_to_usdc", keypair, amount=lamports)
    if result["success"]:
        return result["txid"]
    raise Exception(result["error"])


async def swap_all_usdc_to_sol(keypair: Keypair) -> str:
    result = await call_rust_swapper("usdc_to_sol", keypair)
    if result["success"]:
        return result["txid"]
    raise Exception(result["error"])


async def swap_fixed_sol_to_usdc(keypair: Keypair, lamports: int) -> str:
    result = await call_rust_swapper("swap_sol_to_usdc_fixed", keypair, amount=lamports)
    if result["success"]:
        return result["txid"]
    raise Exception(result["error"])


async def swap_fixed_usdc_to_sol(keypair: Keypair, usdc_amount: int) -> str:
    result = await call_rust_swapper("swap_usdc_to_sol_fixed", keypair, amount=usdc_amount)
    if result["success"]:
        return result["txid"]
    raise Exception(result["error"])


async def withdraw_sol_from_wallets(wallets, to_address: str, amount_sol: float):
    success, failed = [], {}
    lamports = int(amount_sol * 1_000_000_000)

    for w in wallets:
        try:
            decrypted = decrypt_seed(w.encrypted_seed)
            keypair = Keypair.from_bytes(base58.b58decode(decrypted))
            result = await call_rust_swapper("withdraw_sol", keypair, amount=lamports, ca=to_address)
            if result["success"]:
                success.append(w.address)
            else:
                failed[w.address] = result["error"]
        except Exception as e:
            failed[w.address] = str(e)

    return success, failed


async def withdraw_usdc_from_wallets(wallets, to_address: str, amount_usdc: float):
    success, failed = [], {}
    usdc_amount = int(amount_usdc * 1_000_000)

    for w in wallets:
        try:
            decrypted = decrypt_seed(w.encrypted_seed)
            keypair = Keypair.from_bytes(base58.b58decode(decrypted))
            result = await call_rust_swapper("withdraw_usdc", keypair, amount=usdc_amount, ca=to_address)
            if result["success"]:
                success.append(w.address)
            else:
                failed[w.address] = result["error"]
        except Exception as e:
            failed[w.address] = str(e)

    return success, failed


async def withdraw_sol_txid(wallet, to_address: str, amount_sol: float) -> str:
    decrypted = decrypt_seed(wallet.encrypted_seed)
    keypair = Keypair.from_bytes(base58.b58decode(decrypted))
    lamports = int(amount_sol * 1_000_000_000)
    result = await call_rust_swapper("withdraw_sol", keypair, amount=lamports, ca=to_address)
    if result["success"]:
        return result["txid"]
    raise Exception(result["error"])


async def withdraw_usdc_txid(wallet, to_address: str, amount_usdc: float) -> str:
    decrypted = decrypt_seed(wallet.encrypted_seed)
    keypair = Keypair.from_bytes(base58.b58decode(decrypted))
    usdc_amount = int(amount_usdc * 1_000_000)
    result = await call_rust_swapper("withdraw_usdc", keypair, amount=usdc_amount, ca=to_address)
    if result["success"]:
        return result["txid"]
    raise Exception(result["error"])


async def buy_sell_token_from_wallets(wallets: list, ca: str, mode: str, amount: int | None = None):
    success, failed = [], {}
    rust_mode = "buy_fixed" if mode == "buy" else "sell_fixed"

    for w in wallets:
        try:
            decrypted = decrypt_seed(w.encrypted_seed)
            keypair = Keypair.from_bytes(base58.b58decode(decrypted))
            result = await call_rust_swapper(rust_mode, keypair, ca=ca, amount=amount)
            if result["success"]:
                success.append((w.address, result["txid"]))
            else:
                failed[w.address] = result["error"]
        except Exception as e:
            failed[w.address] = str(e)

    return success, failed
