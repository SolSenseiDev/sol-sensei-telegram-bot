from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from spl.token.instructions import get_associated_token_address
from spl.token.constants import WRAPPED_SOL_MINT

async def has_wsol_ata(wallet_address: str) -> bool:
    owner = Pubkey.from_string(wallet_address)
    ata = get_associated_token_address(owner, WRAPPED_SOL_MINT)

    async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
        resp = await client.get_account_info(ata)
        return resp.value is not None