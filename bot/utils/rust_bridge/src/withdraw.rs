use serde::Deserialize;
use std::str::FromStr;

use anyhow::{anyhow, Result};
use solana_client::nonblocking::rpc_client::RpcClient;
use solana_sdk::{
    commitment_config::CommitmentConfig,
    message::Message,
    pubkey::Pubkey,
    signature::Signer,
    system_instruction,
    transaction::Transaction,
};
use spl_associated_token_account::{get_associated_token_address, instruction::create_associated_token_account};
use spl_token::{instruction::transfer_checked, id as token_program_id};

use crate::utils::{decode_keypair, respond_empty, respond_with_txid, JsonInput};

const USDC_MINT: &str = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";

#[derive(Deserialize)]
struct WithdrawRequest {
    private_key: String,
    to_address: String,
    amount: u64,
}

pub async fn handle_withdraw_sol(input: JsonInput) -> Result<()> {
    let req = WithdrawRequest {
        private_key: input.private_key,
        to_address: input.ca.ok_or_else(|| anyhow!("Missing `ca` (to_address)"))?,
        amount: input.amount.ok_or_else(|| anyhow!("Missing `amount`"))?,
    };

    let keypair = decode_keypair(&req.private_key)?;
    let from = keypair.pubkey();
    let to_pubkey = Pubkey::from_str(&req.to_address)?;

    let rpc = RpcClient::new_with_commitment(
        "https://api.mainnet-beta.solana.com".to_string(),
        CommitmentConfig::confirmed(),
    );

    let blockhash = rpc.get_latest_blockhash().await?;
    let ix = system_instruction::transfer(&from, &to_pubkey, req.amount);
    let msg = Message::new(&[ix], Some(&from));
    let tx = Transaction::new(&[&keypair], msg, blockhash);

    match rpc.send_and_confirm_transaction(&tx).await {
        Ok(sig) => respond_with_txid(Ok(sig.to_string())),
        Err(err) => respond_empty(Err(anyhow!("SOL tx failed: {}", err))),
    }

    Ok(())
}

pub async fn handle_withdraw_usdc(input: JsonInput) -> Result<()> {
    let req = WithdrawRequest {
        private_key: input.private_key,
        to_address: input.ca.ok_or_else(|| anyhow!("Missing `ca` (to_address)"))?,
        amount: input.amount.ok_or_else(|| anyhow!("Missing `amount`"))?,
    };

    let keypair = decode_keypair(&req.private_key)?;
    let from = keypair.pubkey();
    let to = Pubkey::from_str(&req.to_address)?;
    let mint = Pubkey::from_str(USDC_MINT)?;

    let from_ata = get_associated_token_address(&from, &mint);
    let to_ata = get_associated_token_address(&to, &mint);

    let rpc = RpcClient::new_with_commitment(
        "https://api.mainnet-beta.solana.com".to_string(),
        CommitmentConfig::confirmed(),
    );

    let blockhash = rpc.get_latest_blockhash().await?;

    let mut instructions = vec![];

    if rpc.get_account(&to_ata).await.is_err() {
        let create_ix = create_associated_token_account(&from, &to, &mint, &token_program_id());
        instructions.push(create_ix);
    }

    let transfer_ix = transfer_checked(
        &token_program_id(),
        &from_ata,
        &mint,
        &to_ata,
        &from,
        &[],
        req.amount,
        6,
    )?;
    instructions.push(transfer_ix);

    let msg = Message::new(&instructions, Some(&from));
    let tx = Transaction::new(&[&keypair], msg, blockhash);

    match rpc.send_and_confirm_transaction(&tx).await {
        Ok(sig) => respond_with_txid(Ok(sig.to_string())),
        Err(err) => respond_empty(Err(anyhow!("USDC tx failed: {}", err))),
    }

    Ok(())
}
