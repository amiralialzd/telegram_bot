import secrets
from db import get_pool


async def generate_referral_code(telegram_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT referral_code FROM users WHERE telegram_id = $1", telegram_id
        )
        if user and user["referral_code"]:
            return user["referral_code"]

        while True:
            code = secrets.token_hex(5).upper()
            exists = await conn.fetchval(
                "SELECT 1 FROM users WHERE referral_code = $1", code
            )
            if not exists:
                break

        await conn.execute(
            "UPDATE users SET referral_code = $1 WHERE telegram_id = $2",
            code, telegram_id
        )
        return code


async def get_referral_stats(telegram_id: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        invited = await conn.fetchval(
            """
            SELECT COUNT(*) FROM users u
            JOIN users r ON r.referral_code = u.referred_by
            WHERE r.telegram_id = $1
            """,
            telegram_id
        )
        buyers = await conn.fetchval(
            "SELECT COUNT(DISTINCT buyer_id) FROM referral_purchases WHERE referrer_id = $1",
            telegram_id
        )
        user = await conn.fetchrow(
            "SELECT referral_earnings, referral_paid_out FROM users WHERE telegram_id = $1",
            telegram_id
        )
        earned   = user["referral_earnings"] if user else 0
        paid_out = user["referral_paid_out"] if user else 0

        return {
            "invited":   invited or 0,
            "buyers":    buyers or 0,
            "earned":    earned,
            "paid_out":  paid_out,
            "available": max(0, earned - paid_out),
        }


async def set_referred_by(telegram_id: int, referral_code: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        referrer = await conn.fetchrow(
            "SELECT telegram_id FROM users WHERE referral_code = $1", referral_code
        )
        if not referrer or referrer["telegram_id"] == telegram_id:
            return
        await conn.execute(
            "UPDATE users SET referred_by = $1 WHERE telegram_id = $2 AND referred_by IS NULL",
            referral_code, telegram_id
        )


async def process_referral_reward(buyer_id: int, stars_paid: int) -> dict | None:
    """
    Finds referrer, adds 30% reward, returns
    {referrer_id, reward_stars} so caller can send notification.
    Returns None if user wasn't referred.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        buyer = await conn.fetchrow(
            "SELECT referred_by FROM users WHERE telegram_id = $1", buyer_id
        )
        if not buyer or not buyer["referred_by"]:
            return None

        referrer = await conn.fetchrow(
            "SELECT telegram_id FROM users WHERE referral_code = $1",
            buyer["referred_by"]
        )
        if not referrer:
            return None

        referrer_id  = referrer["telegram_id"]
        reward_stars = max(1, int(stars_paid * 0.30))

        await conn.execute(
            "UPDATE users SET referral_earnings = referral_earnings + $1 WHERE telegram_id = $2",
            reward_stars, referrer_id
        )
        await conn.execute(
            """
            INSERT INTO referral_purchases (referrer_id, buyer_id, stars_paid, reward_stars)
            VALUES ($1, $2, $3, $4)
            """,
            referrer_id, buyer_id, stars_paid, reward_stars
        )
        return {"referrer_id": referrer_id, "reward_stars": reward_stars}