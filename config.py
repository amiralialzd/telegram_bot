import os
from dotenv import load_dotenv

load_dotenv()

API = os.getenv("BOT_TOKEN")
if not API:
    raise ValueError("BOT_TOKEN is not set in environment variables")

KIE_API_KEY = os.getenv("KIE_API_KEY")
if not KIE_API_KEY:
    raise ValueError("KIE_API_KEY is not set in environment variables")