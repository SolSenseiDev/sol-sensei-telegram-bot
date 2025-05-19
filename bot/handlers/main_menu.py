from aiogram import Router
from aiogram.types import CallbackQuery

main_menu_router = Router()

@main_menu_router.callback_query(lambda c: c.data == "buy_sell")
async def buy_sell_handler(callback: CallbackQuery):
    await callback.answer("🚧 Раздел 'Buy & Sell' в разработке", show_alert=True)

@main_menu_router.callback_query(lambda c: c.data == "settings")
async def settings_handler(callback: CallbackQuery):
    await callback.answer("⚙️ Настройки скоро появятся", show_alert=True)

@main_menu_router.callback_query(lambda c: c.data == "help")
async def help_handler(callback: CallbackQuery):
    await callback.answer("❓ Обратитесь к @admin или напишите /start", show_alert=True)