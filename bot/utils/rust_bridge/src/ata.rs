use anyhow::Result;
use solana_sdk::{
    instruction::Instruction,
    message::{Message, VersionedMessage},
    signature::Signer,
    transaction::VersionedTransaction,
};
use solana_client::nonblocking::rpc_client::RpcClient;
use spl_associated_token_account::{
    get_associated_token_address,
    instruction::create_associated_token_account,
};
use spl_token::{native_mint, id as token_program_id};
use crate::utils::decode_keypair;

pub async fn create_wsol_ata(base58_str: &str) -> Result<()> {
    let payer = decode_keypair(base58_str)?;
    let owner = payer.pubkey();
    let mint = native_mint::id();

    let _ata = get_associated_token_address(&owner, &mint);

    let ix: Instruction = create_associated_token_account(
        &payer.pubkey(),    // funding address
        &owner,             // wallet address
        &mint,              // mint
        &token_program_id() // token program ID
    );

    let rpc = RpcClient::new("https://api.mainnet-beta.solana.com".to_string());
    let blockhash = rpc.get_latest_blockhash().await?;

    let legacy_msg = Message::new_with_blockhash(&[ix], Some(&payer.pubkey()), &blockhash);
    let versioned_msg = VersionedMessage::Legacy(legacy_msg);
    let tx = VersionedTransaction::try_new(versioned_msg, &[&payer])?;

    let sig = rpc.send_and_confirm_transaction(&tx).await?;

    // 🎉 Успешный JSON-ответ
    println!("{}", serde_json::to_string(&serde_json::json!({
        "success": true,
        "txid": sig.to_string(),
        "error": null
    }))?);

    Ok(())
}