from aiogram import Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

main_menu_router = Router()

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

# Menu button handlers (temporary stubs)

@main_menu_router.callback_query(lambda c: c.data == "buy_sell")
async def buy_sell_handler(callback: CallbackQuery):
    await callback.answer("🚧 The 'Buy & Sell' section is under development", show_alert=True)

@main_menu_router.callback_query(lambda c: c.data == "settings")
async def settings_handler(callback: CallbackQuery):
    await callback.answer("⚙️ Settings will be available soon", show_alert=True)

@main_menu_router.callback_query(lambda c: c.data == "help")
async def help_handler(callback: CallbackQuery):
    await callback.answer("❓ Contact @admin or type /start", show_alert=True)