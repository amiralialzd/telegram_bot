import os
from dotenv import load_dotenv

load_dotenv()

API     = os.getenv("BOT_TOKEN")
FAL_KEY = os.getenv("FAL_KEY")

if not API:
    raise ValueError("BOT_TOKEN is not set in environment variables")
if not FAL_KEY:
    raise ValueError("FAL_KEY is not set in environment variables")