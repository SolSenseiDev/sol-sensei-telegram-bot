// src/buy_sell.rs

use anyhow::{anyhow, Result};
use base64::{engine::general_purpose::STANDARD, Engine};
use serde::Deserialize;
use serde_json::{json, Value};
use solana_client::{
    nonblocking::rpc_client::RpcClient,
    rpc_config::RpcSendTransactionConfig,
};
use solana_sdk::{
    commitment_config::CommitmentLevel,
    message::{Message, VersionedMessage},
    signature::Signer,
    transaction::{Transaction, VersionedTransaction},
};
use reqwest::Client;
use spl_token::id as token_program_id;
use spl_associated_token_account::{
    get_associated_token_address, instruction::create_associated_token_account,
};

use crate::utils::{decode_keypair, JsonInput, sol_to_lamports};

const SOL_MINT: &str = "So11111111111111111111111111111111111111112";
const FEE_SOL: f64 = 0.001;

#[derive(Debug, Deserialize)]
struct SwapResponse {
    #[serde(rename = "swapTransaction")]
    swap_transaction: String,
}

pub async fn buy_token_with_sol_fixed_json(input: JsonInput) -> Result<Value> {
    let keypair = decode_keypair(&input.private_key)?;
    let ca = input.ca.ok_or_else(|| anyhow!("Missing token address"))?;
    let amount = input.amount.ok_or_else(|| anyhow!("Missing amount"))?;

    let slippage = input.slippage_bps.unwrap_or(100);
    let total_fee = input
        .total_fee_lamports
        .unwrap_or(sol_to_lamports(FEE_SOL));

    swap_directional(&keypair, SOL_MINT, &ca, amount, slippage, total_fee).await
}

pub async fn sell_token_for_sol_fixed_json(input: JsonInput) -> Result<Value> {
    let keypair = decode_keypair(&input.private_key)?;
    let ca = input.ca.ok_or_else(|| anyhow!("Missing token address"))?;
    let amount = input.amount.ok_or_else(|| anyhow!("Missing amount"))?;

    let slippage = input.slippage_bps.unwrap_or(100);
    let total_fee = input
        .total_fee_lamports
        .unwrap_or(sol_to_lamports(FEE_SOL));

    swap_directional(&keypair, &ca, SOL_MINT, amount, slippage, total_fee).await
}

async fn swap_directional(
    keypair: &solana_sdk::signature::Keypair,
    input_mint: &str,
    output_mint: &str,
    amount: u64,
    slippage_bps: u16,
    total_fee_lamports: u64,
) -> Result<Value> {
    let pubkey = keypair.pubkey();
    let client = Client::new();
    let rpc = RpcClient::new("https://api.mainnet-beta.solana.com".to_string());

    if input_mint == SOL_MINT {
        let wsol_ata = get_associated_token_address(&pubkey, &spl_token::native_mint::id());
        if rpc.get_account(&wsol_ata).await.is_err() {
            let ix = create_associated_token_account(
                &pubkey,
                &pubkey,
                &spl_token::native_mint::id(),
                &token_program_id(),
            );
            let blockhash = rpc.get_latest_blockhash().await?;
            let msg = Message::new(&[ix], Some(&pubkey));
            let tx = Transaction::new(&[keypair], msg, blockhash);
            let _ = rpc.send_transaction(&tx).await?;
        }
    }

    let quote_url = format!(
        "https://lite-api.jup.ag/swap/v1/quote?inputMint={}&outputMint={}&amount={}&slippageBps={}",
        input_mint, output_mint, amount, slippage_bps
    );
    let quote_res = client.get(&quote_url).send().await?;
    let mut quote_json: Value = quote_res.json().await?;

    let compute_unit_limit = quote_json["computeUnitLimit"].as_u64().unwrap_or(200_000);
    let route_plan = quote_json["routePlan"].clone();
    quote_json["routePlan"] = route_plan;

    let cup_price_micro = total_fee_lamports.saturating_mul(1_000_000) / compute_unit_limit;

    let payload = json!({
        "quoteResponse": quote_json,
        "userPublicKey": pubkey.to_string(),
        "wrapAndUnwrapSol": true,
        "asLegacyTransaction": false,
        "computeUnitPriceMicroLamports": cup_price_micro
    });

    let swap_res = client
        .post("https://lite-api.jup.ag/swap/v1/swap")
        .json(&payload)
        .send()
        .await?;
    let text = swap_res.text().await?;
    let swap_val: Value = serde_json::from_str(&text)
        .map_err(|_| anyhow!("Invalid swap response"))?;

    if let Some(err) = swap_val.get("simulationError") {
        if !err.is_null() {
            return Ok(json!({"success": false, "error": "Simulation failed"}));
        }
    }
    if swap_val.get("swapTransaction").is_none() {
        return Ok(json!({"success": false, "error": "No swap transaction returned"}));
    }

    let swap: SwapResponse = serde_json::from_value(swap_val.clone())?;
    let tx_bytes = STANDARD.decode(&swap.swap_transaction)?;
    let unsigned_tx: VersionedTransaction = bincode::deserialize(&tx_bytes)?;
    let message: VersionedMessage = unsigned_tx.message;
    let signed_tx = VersionedTransaction::try_new(message, &[keypair])?;

    let config = RpcSendTransactionConfig {
        skip_preflight: true,
        preflight_commitment: Some(CommitmentLevel::Processed),
        ..Default::default()
    };

    let in_amount = quote_json["inAmount"]
        .as_str()
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(amount);
    let out_amount = quote_json["outAmount"]
        .as_str()
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(0);

    let sig = rpc
        .send_transaction_with_config(&signed_tx, config)
        .await?;

    Ok(json!({
        "success":    true,
        "txid":       sig.to_string(),
        "in_amount":  in_amount,
        "out_amount": out_amount
    }))
}
