use anyhow::Result;
use bs58;
use serde::{Deserialize, Serialize};
use solana_sdk::signature::Keypair;

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

/// 💸 Перевод SOL → лампорты (1 SOL = 1_000_000_000 lamports)
pub fn sol_to_lamports(sol: f64) -> u64 {
    (sol * 1_000_000_000.0) as u64
}

/// 💰 Вычитаем комиссию 0.0032 SOL из общего баланса (в лампортах)
pub fn deduct_swap_fee(sol_balance: u64) -> u64 {
    const FEE_LAMPORTS: u64 = 4_500_000;
    sol_balance.saturating_sub(FEE_LAMPORTS)
}

/// 📥 Универсальный JSON-вход от Python
#[derive(Debug, Serialize, Deserialize)]
pub struct JsonInput {
    pub action: String,
    pub private_key: String,
    pub amount: Option<u64>,
    pub to_address: Option<String>,
    pub ca: Option<String>,
}
