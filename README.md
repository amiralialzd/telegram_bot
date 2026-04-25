# 🍌 Nano Banana Bot

A Telegram bot for AI image generation powered by KieAI, built with Python and aiogram.

## Features

- 🎨 **Two AI Models** — Nano Banana Pro and Nano Banana 2
- 📐 **Quality Options** — 1K, 2K, 4K resolution
- 🖼️ **Aspect Ratios** — 1:1, 9:16, 16:9
- 📎 **Image + Prompt** — Upload a reference photo alongside your text prompt
- 💳 **Credit System** — Users start with 30 free credits, top up via Telegram Stars
- 🌍 **Multilingual** — Turkish and English UI with per-user language preference
- 🔁 **Repeat Generation** — Instantly regenerate with the same settings
- 📊 **Generation History** — All generations logged to PostgreSQL

## Tech Stack

| Layer | Technology |
|---|---|
| Bot Framework | aiogram 3.x |
| Language | Python 3.12 |
| Database | PostgreSQL via Supabase |
| Hosting | Railway |
| Image Generation | KieAI API |
| Payments | Telegram Stars (XTR) |

## Project Structure

```
bot/
├── handlers/
│   ├── __init__.py
│   ├── start.py        # /start, language toggle, main menu
│   ├── generate.py     # Image generation FSM flow
│   └── payment.py      # Telegram Stars payment handling
├── bot.py              # Entry point
├── config.py           # Environment variable loading
├── db.py               # Database layer (asyncpg)
├── keyboards.py        # Inline keyboards
├── states.py           # FSM states
├── texts.py            # TR/EN translations
├── requirements.txt
├── railway.toml
└── .env.example
```

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/telegram_bot.git
cd telegram_bot
```

### 2. Create `.env` file

```
BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=your_supabase_connection_string
KIE_API_KEY=your_kieai_api_key
```

### 3. Create database tables

Run in Supabase SQL Editor:

```sql
CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    telegram_id   BIGINT UNIQUE NOT NULL,
    full_name     TEXT,
    username      TEXT,
    credits       INTEGER NOT NULL DEFAULT 30,
    language      TEXT NOT NULL DEFAULT 'tr',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS generations (
    id            BIGSERIAL PRIMARY KEY,
    telegram_id   BIGINT NOT NULL REFERENCES users(telegram_id),
    model         TEXT NOT NULL,
    quality       TEXT NOT NULL,
    ratio         TEXT NOT NULL,
    prompt        TEXT NOT NULL,
    credits_spent INTEGER NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_generations_telegram_id ON generations(telegram_id);
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Run locally

```bash
python bot.py
```

## Deployment (Railway)

1. Push code to GitHub (make sure `.env` is in `.gitignore`)
2. Create new project on [Railway](https://railway.app) → Deploy from GitHub
3. Add environment variables in Railway → Variables:
   - `BOT_TOKEN`
   - `DATABASE_URL` (use Supabase pooler URL with port 6543)
   - `KIE_API_KEY`
4. Railway auto-detects `railway.toml` and runs `python bot.py`

## Credit Pricing

| Model | Quality | Credits |
|---|---|---|
| Nano Banana Pro | 1K | 17 |
| Nano Banana Pro | 2K | 17 |
| Nano Banana Pro | 4K | 21 |
| Nano Banana 2 | 1K | 7 |
| Nano Banana 2 | 2K | 10 |
| Nano Banana 2 | 4K | 10 |

New users receive **30 free welcome credits**.

## Payment Packages (Telegram Stars)

| Stars | Credits |
|---|---|
| 100 ⭐ | 100 |
| 250 ⭐ | 250 |
| 1000 ⭐ | 1000 |

## Environment Variables

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram bot token from @BotFather |
| `DATABASE_URL` | Supabase PostgreSQL connection string (pooler) |
| `KIE_API_KEY` | KieAI API key for image generation |

## License

MIT
