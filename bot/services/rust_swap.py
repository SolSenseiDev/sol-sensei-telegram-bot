import subprocess
import json
import base58
import os
from solders.keypair import Keypair
from bot.services.encryption import decrypt_seed


def call_rust_withdraw_usdc(keypair: Keypair, to_address: str, amount: int) -> dict:
    try:
        privkey_b58 = base58.b58encode(bytes(keypair)).decode()
        binary_path = os.path.join("bin", "rust_swapper.exe" if os.name == "nt" else "rust_swapper")

        if not os.path.isfile(binary_path):
            raise FileNotFoundError("Rust binary not found.")

        payload = json.dumps({
            "private_key": privkey_b58,
            "to_address": to_address,
            "amount": amount
        })

        proc = subprocess.run(
            [binary_path, "withdraw_usdc"],
            input=payload.encode(),
            capture_output=True,
            timeout=30,
        )

        stdout = proc.stdout.decode().strip()
        stderr = proc.stderr.decode().strip()

        if stderr:
            raise Exception(stderr)
        if not stdout:
            raise Exception("Rust returned empty output")

        result = json.loads(stdout)
        if not result.get("success"):
            raise Exception(result.get("error", "Unknown Rust error"))

        return result

    except Exception as e:
        return {
            "success": False,
            "txid": None,
            "error": str(e),
        }


def call_rust_withdraw(keypair: Keypair, to_address: str, lamports: int) -> dict:
    try:
        privkey_b58 = base58.b58encode(bytes(keypair)).decode()
        binary_path = os.path.join("bin", "rust_swapper.exe" if os.name == "nt" else "rust_swapper")

        if not os.path.isfile(binary_path):
            raise FileNotFoundError("Rust binary not found.")

        payload = json.dumps({
            "private_key": privkey_b58,
            "to_address": to_address,
            "amount": lamports
        })

        proc = subprocess.run(
            [binary_path, "withdraw_sol"],
            input=payload.encode(),
            capture_output=True,
            timeout=30,
        )

        stdout = proc.stdout.decode().strip()
        stderr = proc.stderr.decode().strip()

        if stderr:
            raise Exception(stderr)
        if not stdout:
            raise Exception("Rust returned empty output")

        result = json.loads(stdout)
        if not result.get("success"):
            raise Exception(result.get("error", "Unknown Rust error"))

        return result

    except Exception as e:
        return {
            "success": False,
            "txid": None,
            "error": str(e),
        }


def call_rust_swapper(mode: str, keypair: Keypair, amount: int = None) -> dict:
    try:
        privkey_b58 = base58.b58encode(bytes(keypair)).decode()
        binary_path = os.path.join("bin", "rust_swapper.exe" if os.name == "nt" else "rust_swapper")

        if not os.path.isfile(binary_path):
            raise FileNotFoundError("Rust binary not found.")

        input_lines = privkey_b58
        if amount is not None:
            input_lines += f"\n{amount}"

        proc = subprocess.run(
            [binary_path, mode],
            input=input_lines.encode(),
            capture_output=True,
            timeout=30,
        )

        stdout = proc.stdout.decode().strip()
        stderr = proc.stderr.decode().strip()

        if stderr:
            raise Exception(stderr)
        if not stdout:
            raise Exception("Rust returned empty output")

        result = json.loads(stdout)
        if not result.get("success"):
            raise Exception(result.get("error", "Unknown Rust error"))

        return result

    except Exception as e:
        return {
            "success": False,
            "txid": None,
            "error": str(e),
        }


# === Публичные async-функции ===

async def swap_all_sol_to_usdc(keypair: Keypair, lamports: int) -> str:
    result = call_rust_swapper("sol_to_usdc", keypair)
    if result["success"]:
        return result["txid"]
    raise Exception(result["error"])


async def swap_all_usdc_to_sol(keypair: Keypair) -> str:
    result = call_rust_swapper("usdc_to_sol", keypair)
    if result["success"]:
        return result["txid"]
    raise Exception(result["error"])


async def swap_fixed_sol_to_usdc(keypair: Keypair, lamports: int) -> str:
    result = call_rust_swapper("sol_to_usdc_fixed", keypair, lamports)
    if result["success"]:
        return result["txid"]
    raise Exception(result["error"])


async def swap_fixed_usdc_to_sol(keypair: Keypair, usdc_amount: int) -> str:
    result = call_rust_swapper("usdc_to_sol_fixed", keypair, usdc_amount)
    if result["success"]:
        return result["txid"]
    raise Exception(result["error"])


async def withdraw_sol_from_wallets(wallets, to_address: str, amount_sol: float):
    success = []
    failed = {}
    lamports = int(amount_sol * 1_000_000_000)

    for w in wallets:
        try:
            decrypted = decrypt_seed(w.encrypted_seed)
            keypair = Keypair.from_bytes(base58.b58decode(decrypted))
            # 👇 Передаём to_address и сумму
            result = call_rust_withdraw(keypair, to_address, lamports)
            if result["success"]:
                success.append(w.address)
            else:
                failed[w.address] = result["error"]
        except Exception as e:
            failed[w.address] = str(e)

    return success, failed


async def withdraw_usdc_from_wallets(wallets, to_address: str, amount_usdc: float):
    success = []
    failed = {}
    usdc_amount = int(amount_usdc * 1_000_000)  # 6 знаков после запятой

    for w in wallets:
        try:
            decrypted = decrypt_seed(w.encrypted_seed)
            keypair = Keypair.from_bytes(base58.b58decode(decrypted))
            result = call_rust_withdraw_usdc(keypair, to_address, usdc_amount)
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
    result = call_rust_withdraw(keypair, to_address, lamports)
    if result["success"]:
        return result["txid"]
    raise Exception(result["error"])


async def withdraw_usdc_txid(wallet, to_address: str, amount_usdc: float) -> str:
    decrypted = decrypt_seed(wallet.encrypted_seed)
    keypair = Keypair.from_bytes(base58.b58decode(decrypted))
    usdc_amount = int(amount_usdc * 1_000_000)
    result = call_rust_withdraw_usdc(keypair, to_address, usdc_amount)
    if result["success"]:
        return result["txid"]
    raise Exception(result["error"])