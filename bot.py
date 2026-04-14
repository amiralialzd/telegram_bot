import asyncio
import os
import fal_client
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from config import API, FAL_KEY
from handlers import start, generate

async def main():

    os.environ["FAL_KEY"] = FAL_KEY

    bot = Bot(token=API, default=DefaultBotProperties(parse_mode='HTML'))
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(generate.router)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())