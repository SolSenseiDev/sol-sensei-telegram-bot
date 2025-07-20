from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_earn_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📣 My Referral Code", callback_data="my_referral"),
                InlineKeyboardButton(text="🔑 Enter Referral Code", callback_data="enter_ref_code")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_main")
            ]
        ]
    )
