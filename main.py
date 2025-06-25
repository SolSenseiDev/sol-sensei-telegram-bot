import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers.withdraw import withdraw_router
from bot.handlers.start_buy_sell import router as start_buy_sell_router
from bot.handlers.buy_sell import router as buy_sell_router
from bot.handlers.main_menu import main_menu_router
from bot.handlers.start_wallets import start_wallets_router
from bot.handlers.start import start_router
from bot.handlers.wallets import wallets_router
from bot.handlers.swap import swap_router

# 🔧 Import Rust build logic
from manage_rust import build_rust

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")


async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    storage = MemoryStorage()  # Initialize FSM storage
    dp = Dispatcher(storage=storage)  # Pass storage to dispatcher

    # Include all routers
    dp.include_router(start_router)
    dp.include_router(wallets_router)
    dp.include_router(swap_router)
    dp.include_router(start_wallets_router)
    dp.include_router(main_menu_router)
    dp.include_router(buy_sell_router)
    dp.include_router(start_buy_sell_router)
    dp.include_router(withdraw_router)

    print("🤖 Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    # 🛠️ Build Rust before starting
    build_rust()

    # 🚀 Run the bot
    asyncio.run(main())