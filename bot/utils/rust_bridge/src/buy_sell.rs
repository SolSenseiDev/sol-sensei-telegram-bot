use anyhow::{anyhow, Result};
use base64::{engine::general_purpose::STANDARD, Engine};
use serde::Deserialize;
use serde_json::{json, Value};
use solana_client::nonblocking::rpc_client::RpcClient;
use solana_sdk::{
    message::{Message, VersionedMessage},
    signature::Signer,
    transaction::{Transaction, VersionedTransaction},
};
use tokio::time::{sleep, Duration};
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
    swap_directional(&keypair, SOL_MINT, &ca, amount).await
}

pub async fn sell_token_for_sol_fixed_json(input: JsonInput) -> Result<Value> {
    let keypair = decode_keypair(&input.private_key)?;
    let ca = input.ca.ok_or_else(|| anyhow!("Missing token address"))?;
    let amount = input.amount.ok_or_else(|| anyhow!("Missing amount"))?;
    swap_directional(&keypair, &ca, SOL_MINT, amount).await
}

async fn swap_directional(
    keypair: &solana_sdk::signature::Keypair,
    input_mint: &str,
    output_mint: &str,
    amount: u64,
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
        "https://lite-api.jup.ag/swap/v1/quote?inputMint={}&outputMint={}&amount={}&slippageBps=100",
        input_mint, output_mint, amount
    );
    let quote_res = client.get(&quote_url).send().await?;
    let quote_json: Value = quote_res.json().await?;

    let route_plan = quote_json["routePlan"].clone();
    let mut modified_quote = quote_json.clone();
    modified_quote["routePlan"] = route_plan;

    let payload = json!({
        "quoteResponse": modified_quote,
        "userPublicKey": pubkey.to_string(),
        "wrapAndUnwrapSol": true,
        "asLegacyTransaction": false,
        "computeUnitPriceMicroLamports": sol_to_lamports(FEE_SOL) / 1_000
    });

    let swap_res = client
        .post("https://lite-api.jup.ag/swap/v1/swap")
        .json(&payload)
        .send()
        .await?;

    let text = swap_res.text().await?;
    let swap_val: Value = match serde_json::from_str(&text) {
        Ok(val) => val,
        Err(_) => {
            return Ok(json!({
                "success": false,
                "error": "Invalid swap response"
            }))
        }
    };

    if swap_val.get("simulationError").is_some() && !swap_val["simulationError"].is_null() {
        return Ok(json!({
            "success": false,
            "error": "Simulation failed"
        }));
    }

    if swap_val.get("swapTransaction").is_none() {
        return Ok(json!({
            "success": false,
            "error": "No swap transaction returned"
        }));
    }

    let swap: SwapResponse = serde_json::from_value(swap_val)?;
    let tx_bytes = STANDARD.decode(&swap.swap_transaction)?;
    let unsigned_tx: VersionedTransaction = bincode::deserialize(&tx_bytes)?;
    let message: VersionedMessage = unsigned_tx.message;
    let signed_tx = VersionedTransaction::try_new(message, &[keypair])?;

    for _ in 0..3 {
        match rpc.send_transaction(&signed_tx).await {
            Ok(sig) => {
                return Ok(json!({
                    "success": true,
                    "txid": sig.to_string()
                }));
            }
            Err(_) => sleep(Duration::from_millis(500)).await,
        }
    }

    Ok(json!({
        "success": false,
        "error": "Swap transaction failed"
    }))
}
