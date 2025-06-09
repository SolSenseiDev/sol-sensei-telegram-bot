//! Rust swapper entrypoint
#![allow(non_snake_case)]

mod swap;
mod utils;
mod withdraw;

use anyhow::Result;
use std::env;
use std::io::{self, BufRead};

#[tokio::main]
async fn main() -> Result<()> {
    let args: Vec<String> = env::args().collect();
    let mode = args.get(1).map(|s| s.as_str()).unwrap_or("");

    match mode {
        "withdraw_sol" => {
            if let Err(e) = withdraw::handle_withdraw_sol().await {
                eprintln!("withdraw_sol error: {}", e);
            }
        }
        "withdraw_usdc" => {
            if let Err(e) = withdraw::handle_withdraw_usdc().await {
                eprintln!("withdraw_usdc error: {}", e);
            }
        }
        "sol_to_usdc" => {
            let mut privkey_str = String::new();
            io::stdin().lock().read_line(&mut privkey_str)?;
            let privkey_str = privkey_str.trim();
            swap::swap_sol_to_usdc(privkey_str).await?;
        }
        "usdc_to_sol" => {
            let mut privkey_str = String::new();
            io::stdin().lock().read_line(&mut privkey_str)?;
            let privkey_str = privkey_str.trim();
            swap::swap_usdc_to_sol(privkey_str).await?;
        }
        "sol_to_usdc_fixed" => {
            let mut privkey_str = String::new();
            io::stdin().lock().read_line(&mut privkey_str)?;
            let privkey_str = privkey_str.trim();

            let mut amount_str = String::new();
            io::stdin().lock().read_line(&mut amount_str)?;
            let amount = amount_str.trim().parse::<u64>()?;
            swap::swap_sol_to_usdc_fixed(privkey_str, amount).await?;
        }
        "usdc_to_sol_fixed" => {
            let mut privkey_str = String::new();
            io::stdin().lock().read_line(&mut privkey_str)?;
            let privkey_str = privkey_str.trim();

            let mut amount_str = String::new();
            io::stdin().lock().read_line(&mut amount_str)?;
            let amount = amount_str.trim().parse::<u64>()?;
            swap::swap_usdc_to_sol_fixed(privkey_str, amount).await?;
        }
        _ => {
            utils::respond_empty(Err(anyhow::anyhow!("Unknown or missing mode")));
        }
    }

    Ok(())
}
