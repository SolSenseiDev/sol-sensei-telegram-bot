use anyhow::Result;
use bs58;
use solana_sdk::signature::Keypair;
use serde::Serialize;

/// 🔐 Декодируем base58 приватник в Keypair
pub fn decode_keypair(base58_str: &str) -> Result<Keypair> {
    let bytes = bs58::decode(base58_str).into_vec()?;
    let keypair = Keypair::from_bytes(&bytes)?;
    Ok(keypair)
}

/// ✅ Структура JSON-ответа
#[derive(Debug, Serialize)]
struct SwapResult {
    success: bool,
    txid: Option<String>,
    error: Option<String>,
}

/// 📤 Ответ с txid
pub fn respond_with_txid(result: Result<String>) {
    let response = match result {
        Ok(txid) => SwapResult {
            success: true,
            txid: Some(txid),
            error: None,
        },
        Err(e) => SwapResult {
            success: false,
            txid: None,
            error: Some(e.to_string()),
        },
    };

    println!("{}", serde_json::to_string(&response).unwrap());
}

/// 📤 Ответ без txid
pub fn respond_empty(result: Result<()>) {
    let response = match result {
        Ok(_) => SwapResult {
            success: true,
            txid: None,
            error: None,
        },
        Err(e) => SwapResult {
            success: false,
            txid: None,
            error: Some(e.to_string()),
        },
    };

    println!("{}", serde_json::to_string(&response).unwrap());
}