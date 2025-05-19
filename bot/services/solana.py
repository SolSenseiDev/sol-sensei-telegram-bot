from solana.keypair import Keypair
from solana.rpc.async_api import AsyncClient
from solana.publickey import PublicKey
from base58 import b58encode, b58decode
import os

from bot.services.encryption import decrypt_seed

# ✅ Генерация кошелька
def generate_wallet():
    keypair = Keypair.generate()
    seed = b58encode(keypair.secret_key).decode()
    pubkey = str(keypair.public_key)
    return pubkey, seed

# ✅ Получение баланса
async def get_wallet_balance(pubkey: str) -> float:
    url = os.getenv("RPC_URL")
    async with AsyncClient(url) as client:
        public_key = PublicKey(pubkey)
        response = await client.get_balance(public_key)
        lamports = response.value
        return lamports / 1_000_000_000

# ✅ Получение клиента
def get_client() -> AsyncClient:
    url = os.getenv("RPC_URL")
    return AsyncClient(url)

# ✅ Дешифровка seed и возврат Keypair
def decrypt_keypair(encrypted: str) -> Keypair:
    seed = decrypt_seed(encrypted)
    secret = b58decode(seed)
    return Keypair.from_secret_key(secret)