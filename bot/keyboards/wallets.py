from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_wallets_keyboard(wallets: list, balances_sol: dict, balances_usdc: dict, selected: set[str] = None) -> InlineKeyboardMarkup:
    keyboard = []
    selected = selected or set()

    for i, wallet in enumerate(wallets, start=1):
        addr = wallet.address
        short_addr = f"{addr[:4]}...{addr[-4:]}"
        sol = balances_sol.get(addr, 0.0)
        usdc = balances_usdc.get(addr, 0.0)

        label = f"({i}) ✅ {short_addr}" if addr in selected else f"({i}) {short_addr}"

        keyboard.append([
            InlineKeyboardButton(text=label, callback_data=f"select_wallet:{addr}"),
            InlineKeyboardButton(text=f"{sol:.3f} SOL", callback_data=f"copy_wallet_balance:{addr}"),
            InlineKeyboardButton(text=f"{usdc:.3f} USDC", callback_data=f"copy_wallet_balance:{addr}")
        ])

    keyboard.append([
        InlineKeyboardButton(text="➕ Create Wallet", callback_data="new_wallet"),
        InlineKeyboardButton(text="🔑 Add Wallet", callback_data="add_wallet"),
        InlineKeyboardButton(text="♻️ Refresh", callback_data="wallets")
    ])
    keyboard.append([
        InlineKeyboardButton(text="🔁 Swap", callback_data="swap_wallet"),
        InlineKeyboardButton(text="📤 Withdraw", callback_data="withdraw_all"),
        InlineKeyboardButton(text="❌ Delete", callback_data="delete_wallet")
    ])
    keyboard.append([
        InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


