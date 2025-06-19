//! 🚀 Rust swapper entrypoint (Unified JSON Input)
#![allow(non_snake_case)]

mod swap;
mod utils;
mod withdraw;
mod buy_sell;

use anyhow::Result;
use std::io::{self, Read};
use crate::utils::JsonInput;
use serde_json::Value;

#[tokio::main]
async fn main() -> Result<()> {
    let mut buffer = String::new();
    io::stdin().read_to_string(&mut buffer)?;
    let input: JsonInput = serde_json::from_str(&buffer)?;

    let result: Result<Value> = match input.action.as_str() {
        // === SWAP ===
        "swap_sol_to_usdc" | "sol_to_usdc" | "swap_ALL_SOL_TO_USDC" => {
            swap::swap_sol_to_usdc_json(input).await
        }
        "swap_usdc_to_sol" | "usdc_to_sol" | "swap_ALL_USDC_TO_SOL" => {
            swap::swap_usdc_to_sol_json(input).await
        }
        "swap_sol_to_usdc_fixed" | "sol_to_usdc_fixed" => {
            swap::swap_sol_to_usdc_fixed_json(input).await
        }
        "swap_usdc_to_sol_fixed" | "usdc_to_sol_fixed" => {
            swap::swap_usdc_to_sol_fixed_json(input).await
        }

        // === WITHDRAW ===
        "withdraw_sol" => {
            withdraw::handle_withdraw_sol(input).await?;
            return Ok(());
        }
        "withdraw_usdc" => {
            withdraw::handle_withdraw_usdc(input).await?;
            return Ok(());
        }

        // === BUY / SELL ===
        "buy_fixed" => {
            buy_sell::buy_token_with_sol_fixed(
                &input.private_key,
                input.ca.as_deref().unwrap_or(""),
                input.amount.unwrap_or(0),
            ).await?;
            return Ok(());
        }
        "sell_fixed" => {
            buy_sell::sell_token_for_sol_fixed(
                &input.private_key,
                input.ca.as_deref().unwrap_or(""),
                input.amount.unwrap_or(0),
            ).await?;
            return Ok(());
        }

        _ => Err(anyhow::anyhow!("Unknown or missing action")),
    };

    match result {
        Ok(json) => {
            println!("{}", serde_json::to_string(&json)?);
        }
        Err(e) => {
            println!(
                r#"{{"success": false, "error": "{}"}}"#,
                e.to_string().replace('"', "'")
            );
        }
    }

    Ok(())
}