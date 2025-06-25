use std::str::FromStr;

use anyhow::{anyhow, Result};
use base64::engine::general_purpose::STANDARD;
use base64::Engine;
use reqwest::Client;
use serde::{Deserialize};
use serde_json::{json, Value};
use solana_client::nonblocking::rpc_client::RpcClient;
use solana_sdk::{
    message::{Message, VersionedMessage},
    program_pack::Pack,
    pubkey::Pubkey,
    signature::Signer,
    transaction::{Transaction, VersionedTransaction},
};
use spl_associated_token_account::{
    get_associated_token_address, instruction::create_associated_token_account,
};
use spl_token::{native_mint, state::Account as TokenAccount, id as token_program_id};
use tokio::time::{sleep, Duration};

use crate::utils::{decode_keypair, sol_to_lamports, JsonInput};

const SOL_MINT: &str = "So11111111111111111111111111111111111111112";
const USDC_MINT: &str = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";
const FEE_SOL: f64 = 0.001;
const BUFFER_SOL: f64 = 0.0045;

#[derive(Debug, Deserialize)]
struct SwapResponse {
    #[serde(rename = "swapTransaction")]
    swap_transaction: String,
}

fn json_ok(txid: &str) -> Value {
    json!({
        "success": true,
        "txid": txid
    })
}

async fn get_token_balance(rpc: &RpcClient, owner: &Pubkey, mint: &str) -> Result<u64> {
    let mint_pubkey = Pubkey::from_str(mint)?;
    let ata = get_associated_token_address(owner, &mint_pubkey);
    let account_data = rpc.get_account(&ata).await?;
    let token_account = TokenAccount::unpack(&account_data.data)?;
    Ok(token_account.amount)
}

pub async fn swap_sol_to_usdc_json(req: JsonInput) -> Result<Value> {
    let keypair = decode_keypair(&req.private_key)?;
    let pubkey = keypair.pubkey();
    let rpc = RpcClient::new("https://api.mainnet-beta.solana.com".to_string());

    let balance = rpc.get_balance(&pubkey).await?;
    let keep = sol_to_lamports(BUFFER_SOL);
    if balance <= keep {
        return Err(anyhow!("Not enough SOL for swap"));
    }

    let swap_amount = balance.saturating_sub(keep);
    let txid = swap_directional(&keypair, SOL_MINT, USDC_MINT, swap_amount).await?;
    Ok(json_ok(&txid))
}

pub async fn swap_usdc_to_sol_json(req: JsonInput) -> Result<Value> {
    let keypair = decode_keypair(&req.private_key)?;
    let pubkey = keypair.pubkey();
    let rpc = RpcClient::new("https://api.mainnet-beta.solana.com".to_string());

    let amount = get_token_balance(&rpc, &pubkey, USDC_MINT).await?;
    if amount == 0 {
        return Err(anyhow!("No USDC to swap"));
    }

    let txid = swap_directional(&keypair, USDC_MINT, SOL_MINT, amount).await?;
    Ok(json_ok(&txid))
}

pub async fn swap_sol_to_usdc_fixed_json(req: JsonInput) -> Result<Value> {
    let requested = req.amount.unwrap_or(0);
    let keypair = decode_keypair(&req.private_key)?;
    let pubkey = keypair.pubkey();
    let rpc = RpcClient::new("https://api.mainnet-beta.solana.com".to_string());

    let balance = rpc.get_balance(&pubkey).await?;
    let buffer = sol_to_lamports(BUFFER_SOL);

    if requested > balance {
        return Err(anyhow!("Insufficient SOL: you only have {:.4} SOL", balance as f64 / 1e9));
    }

    let actual_swap_amount = requested.saturating_sub(buffer);
    if actual_swap_amount == 0 {
        return Err(anyhow!("Amount too small after buffer deduction ({:.4} SOL)", BUFFER_SOL));
    }

    let txid = swap_directional(&keypair, SOL_MINT, USDC_MINT, actual_swap_amount).await?;
    Ok(json_ok(&txid))
}

pub async fn swap_usdc_to_sol_fixed_json(req: JsonInput) -> Result<Value> {
    let amount = req.amount.unwrap_or(0);
    if amount == 0 {
        return Err(anyhow!("USDC amount must be greater than zero"));
    }

    let keypair = decode_keypair(&req.private_key)?;
    let pubkey = keypair.pubkey();
    let rpc = RpcClient::new("https://api.mainnet-beta.solana.com".to_string());

    let fee = sol_to_lamports(FEE_SOL);
    let balance = rpc.get_balance(&pubkey).await?;
    if balance < fee {
        return Err(anyhow!("Insufficient SOL for fee (minimum required is {} SOL)", FEE_SOL));
    }

    let actual_balance = get_token_balance(&rpc, &pubkey, USDC_MINT).await?;
    if amount > actual_balance {
        return Err(anyhow!("Insufficient USDC: you only have {} USDC", actual_balance));
    }

    let txid = swap_directional(&keypair, USDC_MINT, SOL_MINT, amount).await?;
    Ok(json_ok(&txid))
}

async fn swap_directional(
    keypair: &solana_sdk::signature::Keypair,
    input_mint: &str,
    output_mint: &str,
    amount: u64,
) -> Result<String> {
    let pubkey = keypair.pubkey();
    let client = Client::new();
    let rpc = RpcClient::new("https://api.mainnet-beta.solana.com".to_string());

    if input_mint == SOL_MINT {
        let wsol_ata = get_associated_token_address(&pubkey, &native_mint::id());
        if rpc.get_account(&wsol_ata).await.is_err() {
            let ix = create_associated_token_account(
                &pubkey,
                &pubkey,
                &native_mint::id(),
                &token_program_id(),
            );
            let blockhash = rpc.get_latest_blockhash().await?;
            let msg = Message::new(&[ix], Some(&pubkey));
            let tx = Transaction::new(&[keypair], msg, blockhash);
            let _ = rpc.send_and_confirm_transaction(&tx).await?;
        }
    }

    let quote_url = format!(
        "https://lite-api.jup.ag/swap/v1/quote?inputMint={}&outputMint={}&amount={}&slippageBps=100",
        input_mint, output_mint, amount
    );

    let quote_res = client.get(&quote_url).send().await?;
    let quote_json: Value = quote_res.json().await?;

    let mut route_plans = vec![quote_json["routePlan"].clone()];
    if let Some(others) = quote_json["otherRoutePlans"].as_array() {
        for route in others {
            route_plans.push(route.clone());
        }
    }

    for route_plan in route_plans {
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
        let swap_val: Value = serde_json::from_str(&text)?;

        if let Some(err) = swap_val.get("simulationError") {
            if !err.is_null() {
                continue;
            }
        }

        if swap_val.get("swapTransaction").is_none() {
            continue;
        }

        let swap: SwapResponse = serde_json::from_value(swap_val)?;
        let tx_bytes = STANDARD.decode(&swap.swap_transaction)?;
        let unsigned_tx: VersionedTransaction = bincode::deserialize(&tx_bytes)?;
        let message: VersionedMessage = unsigned_tx.message;
        let signed_tx = VersionedTransaction::try_new(message, &[keypair])?;

        for _ in 0..3 {
            match rpc.send_transaction(&signed_tx).await {
                Ok(sig) => {
                    let _ = rpc.confirm_transaction(&sig).await;
                    return Ok(sig.to_string());
                }
                Err(_) => {
                    sleep(Duration::from_secs(3)).await;
                }
            }
        }
    }

    Err(anyhow!("All swap routes failed"))
}