from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def format_dollar_balance(amount: float) -> str:
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.1f}M $"
    elif amount >= 1_000:
        return f"{amount / 1_000:.0f}K $"
    else:
        return f"{amount:.2f} $"


def get_buy_sell_keyboard_with_wallets(
    ca: str,
    wallets: list[tuple[str, float]],  # [(address, sol_balance)]
    selected: set[str],
    mode: str,
    token_price: float | None = None,
    token_balances: dict[str, float] | None = None
) -> InlineKeyboardMarkup:
    buy_text = "🟢 Buy ✅" if mode == "buy" else "🟢 Buy"
    sell_text = "🔴 Sell ✅" if mode == "sell" else "🔴 Sell"

    buttons = []

    # --- Mode Switch ---
    buttons.append([
        InlineKeyboardButton(text=buy_text, callback_data=f"sm:buy:{ca}"),
        InlineKeyboardButton(text=sell_text, callback_data=f"sm:sell:{ca}")
    ])

    # --- Wallets Section ---
    buttons.append([
        InlineKeyboardButton(text="💼 Wallets", callback_data=f"refresh:{ca}")
    ])

    # --- Wallet buttons with balances ---
    for i, (address, sol_balance) in enumerate(wallets, start=1):
        short = f"{address[:4]}...{address[-4:]}"
        selected_flag = "✅" if address in selected else ""

        if mode == "buy":
            balance_text = f"{sol_balance:.3f} SOL"
        else:
            if token_price and token_balances and address in token_balances:
                dollar_value = token_balances[address]
                balance_text = format_dollar_balance(dollar_value)
            else:
                balance_text = "0.00 $"

        buttons.append([
            InlineKeyboardButton(
                text=f"({i}) {short} {selected_flag}".strip(),
                callback_data=f"tw:{address}"
            ),
            InlineKeyboardButton(
                text=balance_text,
                callback_data=f"refresh:{ca}"
            )
        ])

    # --- Action Section ---
    buttons.append([
        InlineKeyboardButton(text="⚙️ Action", callback_data=f"refresh:{ca}")
    ])

    # --- Amount Buttons ---
    if mode == "buy":
        buttons += [
            [
                InlineKeyboardButton(text="Buy 0.1 SOL", callback_data=f"buy:0.1:{ca}"),
                InlineKeyboardButton(text="Buy 0.25 SOL", callback_data=f"buy:0.25:{ca}")
            ],
            [
                InlineKeyboardButton(text="Buy 0.5 SOL", callback_data=f"buy:0.5:{ca}"),
                InlineKeyboardButton(text="💸 Enter custom amount", callback_data=f"buy:custom:{ca}")
            ]
        ]
    else:
        buttons += [
            [
                InlineKeyboardButton(text="Sell 25 %", callback_data=f"sell:25:{ca}"),
                InlineKeyboardButton(text="Sell 50 %", callback_data=f"sell:50:{ca}")
            ],
            [
                InlineKeyboardButton(text="Sell 100 %", callback_data=f"sell:100:{ca}"),
                InlineKeyboardButton(text="📉 Enter custom percent", callback_data=f"sell:custom:{ca}")
            ]
        ]

    # --- Navigation ---
    buttons.append([
        InlineKeyboardButton(text="↩️ Back", callback_data="back_to_main"),
        InlineKeyboardButton(text="🔄 Refresh", callback_data=f"refresh:{ca}")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)