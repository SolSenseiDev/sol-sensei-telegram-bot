import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage  # Импортируем память для хранения состояний

from bot.handlers.start import start_router
from bot.handlers.wallets import wallets_router
from bot.handlers.swap import swap_router

# 🔧 импортируем билд Rust
from manage_rust import build_rust

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    storage = MemoryStorage()  # Инициализируем storage
    dp = Dispatcher(storage=storage)  # Передаем storage в диспетчер

    dp.include_router(start_router)
    dp.include_router(wallets_router)
    dp.include_router(swap_router)

    print("🤖 Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    # 🛠️ билдим Rust перед запуском
    build_rust()

    # 🚀 запускаем бота
    asyncio.run(main())