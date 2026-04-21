import os
from dotenv import load_dotenv

load_dotenv()

API = os.getenv("BOT_TOKEN")

if not API:
    raise ValueError("BOT_TOKEN is not set in .env file")