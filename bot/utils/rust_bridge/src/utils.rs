use anyhow::Result;
use bs58;
use serde::{Deserialize, Serialize};
use solana_sdk::signature::Keypair;

pub fn decode_keypair(base58_str: &str) -> Result<Keypair> {
    let bytes = bs58::decode(base58_str).into_vec()?;
    let keypair = Keypair::from_bytes(&bytes)?;
    Ok(keypair)
}

pub fn sol_to_lamports(sol: f64) -> u64 {
    (sol * 1_000_000_000f64) as u64
}

#[derive(Debug, Serialize, Deserialize)]
pub struct JsonInput {
    pub action: String,

    pub private_key: String,

    pub amount: Option<u64>,

    pub to_address: Option<String>,

    pub ca: Option<String>,

    pub slippage_bps: Option<u16>,

    pub total_fee_lamports: Option<u64>,
}
