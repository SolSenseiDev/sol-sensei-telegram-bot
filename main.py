import asyncio
import os
import subprocess
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers.settings import router as settings_router
from bot.handlers.withdraw import withdraw_router
from bot.handlers.start_buy_sell import router as start_buy_sell_router
from bot.handlers.buy_sell import router as buy_sell_router
from bot.handlers.main_menu import main_menu_router
from bot.handlers.start_wallets import start_wallets_router
from bot.handlers.start import start_router
from bot.handlers.wallets import wallets_router
from bot.handlers.swap import swap_router
from bot.handlers.earn import earn_router

from manage_rust import build_rust, OUTPUT_BIN

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")


async def main():
    # 👷 Build Rust
    build_rust()

    # 🌐 Run Rust server (non-blocking)
    print("🌐 Starting Rust Axum server on localhost:3030...")
    rust_proc = subprocess.Popen([OUTPUT_BIN], cwd="bin")

    # 🤖 Launch the bot
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.include_router(start_router)
    dp.include_router(wallets_router)
    dp.include_router(swap_router)
    dp.include_router(start_wallets_router)
    dp.include_router(main_menu_router)
    dp.include_router(earn_router)
    dp.include_router(buy_sell_router)
    dp.include_router(start_buy_sell_router)
    dp.include_router(withdraw_router)
    dp.include_router(settings_router)

    print("🤖 Bot is running...")
    try:
        await dp.start_polling(bot)
    finally:
        print("🛑 Shutting down Rust server...")
        rust_proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
