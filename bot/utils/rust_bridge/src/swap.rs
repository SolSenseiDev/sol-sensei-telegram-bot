use std::str::FromStr;

use anyhow::Result;
use base64::{engine::general_purpose::STANDARD, Engine};
use reqwest::Client;
use serde::Deserialize;
use serde_json::Value;
use solana_client::nonblocking::rpc_client::RpcClient;
use solana_sdk::{
    message::VersionedMessage,
    pubkey::Pubkey,
    signature::Signer,
    transaction::VersionedTransaction,
    program_pack::Pack, // 👈 ВОТ ЭТО ВАЖНО!
};

use spl_associated_token_account::get_associated_token_address;
use spl_token::state::Account as TokenAccount;

use crate::utils::{decode_keypair, respond_empty, respond_with_txid};

const SOL_MINT: &str = "So11111111111111111111111111111111111111112";
const USDC_MINT: &str = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";

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

pub async fn swap_sol_to_usdc(base58_str: &str) -> Result<()> {
    swap_directional(base58_str, SOL_MINT, USDC_MINT).await
}

pub async fn swap_usdc_to_sol(base58_str: &str) -> Result<()> {
    swap_directional(base58_str, USDC_MINT, SOL_MINT).await
}

async fn swap_directional(base58_str: &str, input_mint: &str, output_mint: &str) -> Result<()> {
    let keypair = decode_keypair(base58_str)?;
    let pubkey = keypair.pubkey();
    let client = Client::new();
    let rpc = RpcClient::new("https://api.mainnet-beta.solana.com".to_string());

    // Получаем баланс
    let amount = if input_mint == SOL_MINT {
        let balance = rpc.get_balance(&pubkey).await?;
        if balance < 20_000 {
            respond_empty(Err(anyhow::anyhow!(
                "Недостаточно SOL для свапа (нужно > 20_000)"
            )));
            return Ok(());
        }
        balance.saturating_sub(100_000)
    } else {
        let token_balance = get_token_balance(&rpc, &pubkey, input_mint).await?;
        if token_balance == 0 {
            respond_empty(Err(anyhow::anyhow!("Нет USDC для свапа")));
            return Ok(());
        }
        token_balance
    };

    // Получаем quote
    let quote_url = format!(
        "https://lite-api.jup.ag/swap/v1/quote?inputMint={}&outputMint={}&amount={}&slippageBps=100",
        input_mint, output_mint, amount
    );

    let quote_res = client.get(&quote_url).send().await?;
    let quote_json: Value = quote_res.json().await?;
    eprintln!("[Jupiter] Quote response: {}", quote_json);

    let mut route_plans = vec![quote_json["routePlan"].clone()];
    if let Some(others) = quote_json["otherRoutePlans"].as_array() {
        route_plans.extend(others.clone());
    }

    for (i, route_plan) in route_plans.iter().enumerate() {
        // Фильтрация по Obric
        let label = route_plan
            .get(0)
            .and_then(|x| x.get("swapInfo"))
            .and_then(|s| s.get("label"))
            .and_then(|l| l.as_str())
            .unwrap_or("");
        if label.to_lowercase().contains("obric") {
            eprintln!("🚫 Пропущен маршрут с пулом Obric ({label})");
            continue;
        }

        let mut modified_quote = quote_json.clone();
        modified_quote["routePlan"] = route_plan.clone();

        let payload = serde_json::json!({
            "quoteResponse": modified_quote,
            "userPublicKey": pubkey.to_string(),
            "wrapAndUnwrapSol": true,
            "asLegacyTransaction": false
        });

        let swap_res = client
            .post("https://lite-api.jup.ag/swap/v1/swap")
            .json(&payload)
            .send()
            .await?;

        let text = swap_res.text().await?;
        eprintln!("💬 Swap response [route #{i}]: {}", text);

        let Ok(swap) = serde_json::from_str::<SwapResponse>(&text) else {
            eprintln!("⚠️ Ошибка сериализации swapTransaction. Пробуем следующий маршрут...");
            continue;
        };

        let tx_bytes = STANDARD.decode(&swap.swap_transaction)?;
        let unsigned_tx: VersionedTransaction = bincode::deserialize(&tx_bytes)?;
        let message: VersionedMessage = unsigned_tx.message;
        let signed_tx = VersionedTransaction::try_new(message, &[&keypair])?;

        match rpc.send_and_confirm_transaction(&signed_tx).await {
            Ok(txid) => {
                respond_with_txid(Ok(txid.to_string()));
                return Ok(());
            }
            Err(e) => {
                eprintln!("❌ Ошибка при отправке транзакции [маршрут #{i}]: {e}");
                continue;
            }
        }
    }

    respond_empty(Err(anyhow::anyhow!(
        "Все маршруты свапа завершились неудачей"
    )));
    Ok(())
}
