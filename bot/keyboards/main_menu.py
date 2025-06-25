from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🟢 Buy & Sell", callback_data="buy_sell"),
                InlineKeyboardButton(text="💼 Wallets", callback_data="wallets")
            ],
            [
                InlineKeyboardButton(text="⚙️ Settings", callback_data="settings"),
                InlineKeyboardButton(text="❓ Help", callback_data="help")
            ]
        ]
    )