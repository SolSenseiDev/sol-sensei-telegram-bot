from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from base58 import b58encode, b58decode

RPC_URL = "https://api.mainnet-beta.solana.com"
LAMPORTS_PER_SOL = 1_000_000_000


def generate_wallet() -> tuple[str, str]:
    keypair = Keypair.generate()
    seed = b58encode(bytes(keypair)).decode()
    pubkey = str(keypair.pubkey())
    return pubkey, seed


def decrypt_keypair(seed_b58: str) -> Keypair:
    secret = b58decode(seed_b58)
    return Keypair.from_bytes(secret)


async def get_wallet_balance(pubkey: str) -> float:
    public_key = Pubkey.from_string(pubkey)
    async with AsyncClient(RPC_URL) as client:
        response = await client.get_balance(public_key)
        lamports = response.value
        return lamports / LAMPORTS_PER_SOL
