import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, statement_cache_size=0)
    return _pool


async def get_or_create_user(telegram_id: int, full_name: str, username: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        if user is None:
            user = await conn.fetchrow(
                """
                INSERT INTO users (telegram_id, full_name, username, credits, language)
                VALUES ($1, $2, $3, 30, 'tr')
                RETURNING *
                """,
                telegram_id, full_name, username
            )
        return dict(user)


async def get_user(telegram_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        return dict(user) if user else None


async def set_language(telegram_id: int, lang: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET language = $1 WHERE telegram_id = $2",
            lang, telegram_id
        )


async def deduct_credits(telegram_id: int, amount: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            UPDATE users SET credits = credits - $1
            WHERE telegram_id = $2 AND credits >= $1
            RETURNING credits
            """,
            amount, telegram_id
        )
        if user is None:
            raise ValueError("Insufficient credits")
        return user["credits"]


async def add_credits(telegram_id: int, amount: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "UPDATE users SET credits = credits + $1 WHERE telegram_id = $2 RETURNING credits",
            amount, telegram_id
        )
        if user is None:
            raise ValueError("User not found")
        return user["credits"]


async def log_generation(telegram_id: int, model: str, quality: str,
                         ratio: str, prompt: str, credits_spent: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO generations (telegram_id, model, quality, ratio, prompt, credits_spent)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            telegram_id, model, quality, ratio, prompt, credits_spent
        )