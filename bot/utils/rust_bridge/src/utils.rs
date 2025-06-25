use anyhow::Result;
use bs58;
use serde::{Deserialize, Serialize};
use solana_sdk::signature::Keypair;

/// 🔐 Decode base58 private key into Keypair
pub fn decode_keypair(base58_str: &str) -> Result<Keypair> {
    let bytes = bs58::decode(base58_str).into_vec()?;
    let keypair = Keypair::from_bytes(&bytes)?;
    Ok(keypair)
}

/// ✅ JSON response structure
#[derive(Debug, Serialize)]
struct SwapResult {
    success: bool,
    txid: Option<String>,
    error: Option<String>,
}

/// 📤 Response with txid
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

/// 📤 Response without txid
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

/// 💸 Convert SOL to lamports (1 SOL = 1_000_000_000 lamports)
pub fn sol_to_lamports(sol: f64) -> u64 {
    (sol * 1_000_000_000.0) as u64
}

/// 📥 Universal JSON input from Python
#[derive(Debug, Serialize, Deserialize)]
pub struct JsonInput {
    pub action: String,
    pub private_key: String,
    pub amount: Option<u64>,
    pub to_address: Option<String>,
    pub ca: Option<String>,
}