use std::str::FromStr;

use anyhow::{anyhow, Result};
use base64::{engine::general_purpose::STANDARD, Engine};
use reqwest::Client;
use serde::Deserialize;
use serde_json::Value;
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
use spl_token::{state::Account as TokenAccount, id as token_program_id};
use tokio::time::{sleep, Duration};

use crate::utils::{decode_keypair, respond_empty, respond_with_txid, sol_to_lamports};

const SOL_MINT: &str = "So11111111111111111111111111111111111111112";
const FEE_SOL: f64 = 0.001;

#[derive(Debug, Deserialize)]
struct SwapResponse {
    #[serde(rename = "swapTransaction")]
    swap_transaction: String,
}

async fn get_token_balance(rpc: &RpcClient, owner: &Pubkey, mint: &str) -> Result<u64> {
    let mint_pubkey = Pubkey::from_str(mint)?;
    let ata = get_associated_token_address(owner, &mint_pubkey);
    let account_data = rpc.get_account(&ata).await?;
    let token_account = TokenAccount::unpack(&account_data.data)?;
    Ok(token_account.amount)
}

pub async fn buy_token_with_sol(base58_str: &str, token_mint: &str) -> Result<()> {
    let keypair = decode_keypair(base58_str)?;
    let pubkey = keypair.pubkey();
    let rpc = RpcClient::new("https://api.mainnet-beta.solana.com".to_string());

    let balance = rpc.get_balance(&pubkey).await?;
    if balance < 100_000 {
        respond_empty(Err(anyhow!("Недостаточно SOL для покупки")));
        return Ok(());
    }

    let amount = balance.saturating_sub(100_000);
    swap_directional(&keypair, SOL_MINT, token_mint, amount).await
}

pub async fn sell_token_for_sol(base58_str: &str, token_mint: &str) -> Result<()> {
    let keypair = decode_keypair(base58_str)?;
    let pubkey = keypair.pubkey();
    let rpc = RpcClient::new("https://api.mainnet-beta.solana.com".to_string());

    let amount = get_token_balance(&rpc, &pubkey, token_mint).await?;
    if amount == 0 {
        respond_empty(Err(anyhow!("Нет токенов для продажи")));
        return Ok(());
    }

    swap_directional(&keypair, token_mint, SOL_MINT, amount).await
}

pub async fn buy_token_with_sol_fixed(base58_str: &str, token_mint: &str, amount: u64) -> Result<()> {
    let keypair = decode_keypair(base58_str)?;
    let rpc = RpcClient::new("https://api.mainnet-beta.solana.com".to_string());
    let pubkey = keypair.pubkey();

    // Получим баланс кошелька
    let balance = rpc.get_balance(&pubkey).await?;
    let buffer = 4_500_000; // 0.0045 SOL

    if balance <= buffer {
        respond_empty(Err(anyhow!("Insufficient SOL balance (buffer exceeded)")));
        return Ok(());
    }

    let safe_amount = amount.min(balance - buffer);
    if safe_amount == 0 {
        respond_empty(Err(anyhow!("Insufficient SOL after buffer deduction")));
        return Ok(());
    }

    swap_directional(&keypair, SOL_MINT, token_mint, safe_amount).await
}

pub async fn sell_token_for_sol_fixed(base58_str: &str, token_mint: &str, amount: u64) -> Result<()> {
    let keypair = decode_keypair(base58_str)?;
    swap_directional(&keypair, token_mint, SOL_MINT, amount).await
}

async fn swap_directional(
    keypair: &solana_sdk::signature::Keypair,
    input_mint: &str,
    output_mint: &str,
    amount: u64,
) -> Result<()> {
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
        modified_quote["routePlan"] = route_plan.clone();

        let payload = serde_json::json!({
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
            Err(_) => continue,
        };

        if swap_val.get("simulationError").is_some() && !swap_val["simulationError"].is_null() {
            continue;
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
                    respond_with_txid(Ok(sig.to_string()));
                    return Ok(());
                }
                Err(_) => sleep(Duration::from_secs(3)).await,
            }
        }
    }

    respond_empty(Err(anyhow!("Все маршруты свапа завершились неудачей")));
    Ok(())
}
