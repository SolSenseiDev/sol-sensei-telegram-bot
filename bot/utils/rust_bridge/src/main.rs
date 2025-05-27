use anyhow::{Result, anyhow};
use base64::{engine::general_purpose::STANDARD, Engine};
use bincode;
use bs58;
use serde::{Deserialize, Serialize};
use std::env;
use std::io::{self, BufRead};
use solana_sdk::{
    message::VersionedMessage,
    signature::{Keypair, Signature, Signer},
    transaction::VersionedTransaction,
};
use solana_client::nonblocking::rpc_client::RpcClient;
use reqwest::Client;

#[derive(Debug, Serialize)]
struct SwapResult {
    success: bool,
    txid: Option<String>,
    error: Option<String>,
}

#[derive(Debug, Serialize)]
struct SwapRequest<'a> {
    route: serde_json::Value,
    userPublicKey: &'a str,
    wrapUnwrapSOL: bool,
    createATA: bool,
    feeAccount: Option<String>,
    asLegacyTransaction: bool,
}

#[derive(Debug, Deserialize)]
struct SwapResponse {
    #[serde(rename = "swapTransaction")]
    swap_transaction: String,
}

#[tokio::main]
async fn main() -> Result<()> {
    // Читаем аргумент режима
    let args: Vec<String> = env::args().collect();
    let mode = args.get(1).map(|s| s.as_str()).unwrap_or("");

    // Читаем приватный ключ из stdin
    let stdin = io::stdin();
    let mut privkey_str = String::new();
    stdin.lock().read_line(&mut privkey_str)?;
    let privkey_str = privkey_str.trim();

    let result = match mode {
        "sol_to_usdc" => swap_sol_to_usdc(privkey_str).await,
        // добавим позже:
        // "usdc_to_sol" => swap_usdc_to_sol(privkey_str).await,
        // "buy_token" => buy_token(privkey_str, token_addr, amount).await,
        _ => Err(anyhow!("Unknown or missing mode")),
    };

    // Ответ в stdout
    let response = match result {
        Ok(txid) => SwapResult { success: true, txid: Some(txid.to_string()), error: None },
        Err(e) => SwapResult { success: false, txid: None, error: Some(e.to_string()) },
    };

    println!("{}", serde_json::to_string(&response)?);
    Ok(())
}

async fn swap_sol_to_usdc(base58_str: &str) -> Result<Signature> {
    let key_bytes = bs58::decode(base58_str).into_vec()?;
    let keypair = Keypair::from_bytes(&key_bytes)?;
    let pubkey = keypair.pubkey();

    let amount = 3_000_000;
    let client = Client::new();

    let quote_url = format!(
        "https://quote-api.jup.ag/v6/quote?inputMint=So11111111111111111111111111111111111111112\
        &outputMint=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v\
        &amount={}&slippageBps=100",
        amount
    );

    let quote_res = client.get(&quote_url).send().await?;
    let route_json: serde_json::Value = quote_res.json().await?;

    let swap_req = SwapRequest {
        route: route_json.clone(),
        userPublicKey: &pubkey.to_string(),
        wrapUnwrapSOL: true,
        createATA: true,
        feeAccount: None,
        asLegacyTransaction: false,
    };

    let swap_res = client
        .post("https://quote-api.jup.ag/v6/swap")
        .json(&swap_req)
        .send()
        .await?;

    let text = swap_res.text().await?;
    let swap: SwapResponse = serde_json::from_str(&text)
        .map_err(|_| anyhow!("Invalid response from Jupiter: {}", text))?;

    let tx_bytes = STANDARD.decode(&swap.swap_transaction)?;
    let unsigned_tx: VersionedTransaction = bincode::deserialize(&tx_bytes)?;

    let message: VersionedMessage = unsigned_tx.message;
    let signed_tx = VersionedTransaction::try_new(message, &[&keypair])?;

    let rpc = RpcClient::new("https://api.mainnet-beta.solana.com".to_string());
    let txid: Signature = rpc.send_and_confirm_transaction(&signed_tx).await?;
    Ok(txid)
}