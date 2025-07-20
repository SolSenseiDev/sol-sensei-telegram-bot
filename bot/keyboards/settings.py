from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_settings_keyboard(slippage: int, fee: float) -> InlineKeyboardMarkup:
    """
    Build an inline keyboard showing current slippage and fee,
    with buttons to change each and a back-to-main option.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Slippage: {slippage}%",
                    callback_data="settings_slippage"
                ),
                InlineKeyboardButton(
                    text="Change Slippage",
                    callback_data="settings_enter_slippage"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"Fee: {fee} SOL",
                    callback_data="settings_fee"
                ),
                InlineKeyboardButton(
                    text="Change Fee",
                    callback_data="settings_enter_fee"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Back to Main",
                    callback_data="back_to_main"
                ),
            ],
        ]
    )
