//! Rust swapper entrypoint
#![allow(non_snake_case)]

mod swap;
mod ata;
mod utils;

use anyhow::Result;
use std::env;
use std::io::{self, BufRead};

#[tokio::main]
async fn main() -> Result<()> {
    let args: Vec<String> = env::args().collect();
    let mode = args.get(1).map(|s| s.as_str()).unwrap_or("");

    // Приватный ключ в stdin
    let mut privkey_str = String::new();
    io::stdin().lock().read_line(&mut privkey_str)?;
    let privkey_str = privkey_str.trim();

    // Вызов нужной функции (она сама отправит JSON-ответ)
    match mode {
        "sol_to_usdc" => swap::swap_sol_to_usdc(privkey_str).await?,
        "usdc_to_sol" => swap::swap_usdc_to_sol(privkey_str).await?,
        "create_wsol_ata" => ata::create_wsol_ata(privkey_str).await?,
        _ => utils::respond_empty(Err(anyhow::anyhow!("Unknown or missing mode"))),
    }

    Ok(())
}
