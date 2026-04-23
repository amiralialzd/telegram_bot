import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from config import API
from handlers import start, payment, generate

async def main():
    bot = Bot(token=API, default=DefaultBotProperties(parse_mode='HTML'))
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(payment.router)   # payment before generate
    dp.include_router(generate.router)

    print("Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())