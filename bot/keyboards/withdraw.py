from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_withdraw_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💸 Withdraw SOL", callback_data="withdraw_sol"),
            InlineKeyboardButton(text="💵 Withdraw USDC", callback_data="withdraw_usdc"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Back to Wallets", callback_data="wallets"),
            InlineKeyboardButton(text="🔄 Refresh", callback_data="withdraw_all"),
        ]
    ])
