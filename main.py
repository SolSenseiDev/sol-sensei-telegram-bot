import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
import os

from bot.handlers.start import start_router
from bot.handlers.wallets import wallets_router
from bot.handlers.main_menu import main_menu_router  # 🔹 Added

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # 🔹 Register all routers
    dp.include_router(start_router)
    dp.include_router(main_menu_router)   # 🔹 Connect main menu router
    dp.include_router(wallets_router)

    print("🤖 Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
