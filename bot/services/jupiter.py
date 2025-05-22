import aiohttp
import base64

from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.signature import Signature
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts

from bot.constants import (
    LAMPORTS_PER_SOL,
    MIN_LAMPORTS_RESERVE,
    WSOL_MINT,
    USDC_MINT,
    RPC_URL
)


async def swap_all_sol_to_usdc(keypair: Keypair, full_balance_lamports: int) -> str:
    if full_balance_lamports <= MIN_LAMPORTS_RESERVE:
        raise Exception("Not enough SOL to swap after reserving fee buffer.")

    amount_to_swap = full_balance_lamports - MIN_LAMPORTS_RESERVE
    print(f"[Jupiter] Preparing to swap {amount_to_swap} lamports (~{amount_to_swap / LAMPORTS_PER_SOL:.5f} SOL)")

    quote = None
    async with aiohttp.ClientSession() as session:
        for slippage in [100, 300, 500]:
            quote_url = (
                f"https://quote-api.jup.ag/v6/quote?inputMint={WSOL_MINT}"
                f"&outputMint={USDC_MINT}&amount={amount_to_swap}&slippageBps={slippage}"
            )
            print(f"[Jupiter] Requesting quote with slippage {slippage / 100}%")
            async with session.get(quote_url) as r:
                data = await r.json()
                if "data" in data and data["data"]:
                    print("[Jupiter] Route found ✅")
                    quote = data["data"][0]
                    break
                else:
                    print("[Jupiter] No routes found at this slippage")

        if not quote:
            raise Exception("No routes available for this amount.")

        swap_payload = {
            "route": quote,
            "userPublicKey": str(keypair.pubkey()),
            "wrapUnwrapSOL": True,
            "createATA": True,  # ✅ автоматическое создание ATA
            "feeAccount": None,
            "asLegacyTransaction": False
        }

        print("[Jupiter] Requesting swap transaction...")
        async with session.post("https://quote-api.jup.ag/v6/swap", json=swap_payload) as r:
            result = await r.json()
            if "swapTransaction" not in result:
                print("[Jupiter] Missing swapTransaction ❌")
                print("Response:", result)
                raise Exception("Invalid swap transaction from Jupiter.")

            print("[Jupiter] swapTransaction received ✅")
            tx_bytes = base64.b64decode(result["swapTransaction"])

    async with AsyncClient(RPC_URL) as client:
        tx = VersionedTransaction.deserialize(tx_bytes)
        tx.sign([keypair])
        print("[Jupiter] Broadcasting transaction to Solana...")
        txid = await client.send_raw_transaction(tx.serialize(), opts=TxOpts(skip_confirmation=False))
        print(f"[Jupiter] Transaction sent! ✅ TX: {txid.value}")
        return str(txid.value if isinstance(txid.value, Signature) else txid.value)