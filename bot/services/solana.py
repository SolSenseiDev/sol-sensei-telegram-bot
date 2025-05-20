from solana.keypair import Keypair
from solana.rpc.async_api import AsyncClient
from solana.publickey import PublicKey
from base58 import b58encode, b58decode
import os


RPC_URL = "https://api.mainnet-beta.solana.com"

def generate_wallet():
    keypair = Keypair.generate()
    seed = b58encode(keypair.secret_key).decode()
    pubkey = str(keypair.public_key)
    return pubkey, seed

def decrypt_keypair(seed_b58: str) -> Keypair:
    secret = b58decode(seed_b58)
    return Keypair.from_secret_key(secret)

async def get_wallet_balance(pubkey: str) -> float:
    public_key = PublicKey(pubkey)
    async with AsyncClient(RPC_URL) as client:
        response = await client.get_balance(public_key)
        lamports = response.value
        return lamports / 1_000_000_000