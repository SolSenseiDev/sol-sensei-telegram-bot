from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_swap_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 all SOL → USDC", callback_data="swap_all_sol_usdc"),
            InlineKeyboardButton(text="🎯 fixed SOL → USDC", callback_data="swap_fixed_sol_usdc")
        ],
        [
            InlineKeyboardButton(text="🔄 all USDC → SOL", callback_data="swap_all_usdc_sol"),
            InlineKeyboardButton(text="🎯 fixed USDC → SOL", callback_data="swap_fixed_usdc_sol")
        ],
        [
            InlineKeyboardButton(text="⬅️ Back to Wallets", callback_data="back_to_wallets"),
            InlineKeyboardButton(text="♻️ Refresh", callback_data="refresh_swap_menu")
        ]
    ])


def get_create_ata_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🛠 Создать wSOL ATA (≈0.002 SOL)",
                callback_data="create_wsol_ata"
            )
        ]
    ])