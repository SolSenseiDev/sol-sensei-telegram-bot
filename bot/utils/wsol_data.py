from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.hash import Hash
from solders.transaction import Transaction
from spl.token.instructions import (
    get_associated_token_address,
    create_associated_token_account,
    sync_native
)
from solders.system_program import TransferParams, transfer
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Confirmed

from bot.constants import RPC_URL, WSOL_MINT_PUBKEY, LAMPORTS_PER_SOL


async def check_wsol_ata_exists(pubkey: Pubkey) -> bool:
    ata = get_associated_token_address(pubkey, WSOL_MINT_PUBKEY)
    async with AsyncClient(RPC_URL) as client:
        resp = await client.get_account_info(ata, commitment=Confirmed)
        return resp.value is not None


async def ensure_wsol_ata_exists(user_pubkey: Pubkey, payer: Keypair) -> str:
    ata = get_associated_token_address(user_pubkey, WSOL_MINT_PUBKEY)

    async with AsyncClient(RPC_URL) as client:
        resp = await client.get_account_info(ata, commitment=Confirmed)
        if resp.value is not None:
            return str(ata)

        print(f"[WSOL] Creating ATA for {user_pubkey}")
        ix = create_associated_token_account(
            payer=payer.pubkey(),
            owner=user_pubkey,
            mint=WSOL_MINT_PUBKEY
        )

        blockhash = (await client.get_latest_blockhash()).value.blockhash
        tx = Transaction([ix], payer.pubkey(), Hash.from_string(str(blockhash)))
        tx.sign([payer])
        await client.send_raw_transaction(tx.serialize(), opts=TxOpts(skip_confirmation=False))
        return str(ata)
