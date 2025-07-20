use axum::{
    extract::Json,
    response::IntoResponse,
    routing::post,
    Router,
};
use serde_json::{json, Value};
use std::net::SocketAddr;

mod swap;
mod withdraw;
mod buy_sell;
mod utils;

use utils::JsonInput;

#[tokio::main]
async fn main() {
    let app = Router::new().route("/swap", post(handle_swap));

    let addr = SocketAddr::from(([127, 0, 0, 1], 3030));
    println!("🦀 Rust API running on http://{}/swap", addr);

    axum::Server::bind(&addr)
        .serve(app.into_make_service())
        .await
        .unwrap();
}

async fn handle_swap(Json(input): Json<JsonInput>) -> impl IntoResponse {
    let result: Value = match input.action.as_str() {
        "swap_sol_to_usdc" | "sol_to_usdc" | "swap_ALL_SOL_TO_USDC" => {
            swap::swap_sol_to_usdc_json(input).await.unwrap_or_else(error_json)
        }
        "swap_usdc_to_sol" | "usdc_to_sol" | "swap_ALL_USDC_TO_SOL" => {
            swap::swap_usdc_to_sol_json(input).await.unwrap_or_else(error_json)
        }
        "swap_sol_to_usdc_fixed" | "sol_to_usdc_fixed" => {
            swap::swap_sol_to_usdc_fixed_json(input).await.unwrap_or_else(error_json)
        }
        "swap_usdc_to_sol_fixed" | "usdc_to_sol_fixed" => {
            swap::swap_usdc_to_sol_fixed_json(input).await.unwrap_or_else(error_json)
        }
        "withdraw_sol" => {
            withdraw::handle_withdraw_sol(input).await.unwrap_or_else(error_json)
        }
        "withdraw_usdc" => {
            withdraw::handle_withdraw_usdc(input).await.unwrap_or_else(error_json)
        }
        "buy_fixed" => {
            buy_sell::buy_token_with_sol_fixed_json(input).await.unwrap_or_else(error_json)
        }
        "sell_fixed" => {
            buy_sell::sell_token_for_sol_fixed_json(input).await.unwrap_or_else(error_json)
        }
        _ => json!({
            "success": false,
            "error": "Unknown or missing action"
        }),
    };

    Json(result)
}

fn error_json<E: std::fmt::Display>(e: E) -> Value {
    json!({
        "success": false,
        "error": e.to_string().replace('"', "'")
    })
}