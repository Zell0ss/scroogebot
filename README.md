# ScroogeBot 🦆

Telegram bot for managing shared paper-trading baskets with automatic strategy alerts and inline trade confirmations.

## Quick Start

```bash
git clone https://github.com/zell0ss/scroogebot.git && cd scroogebot
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in TELEGRAM_APIKEY and DB credentials
alembic upgrade head
python -c "import asyncio; from src.db.seed import seed; asyncio.run(seed())"
python scroogebot.py
```

## What it does

- `/valoracion` `/cartera` `/historial` — portfolio valuation, positions, order history
- `/analiza <TICKER>` — RSI(14), SMA20/50, trend, 1-day change
- `/compra` `/vende` — paper-buy and paper-sell at live market price
- `/cestas` `/cesta` — list and inspect shared baskets
- `/start` `/adduser` `/watchlist` — user registration, OWNER/MEMBER roles, watchlist
- **Automatic alerts** — APScheduler scans positions every 5 min, sends inline keyboard (✅ Ejecutar / ❌ Rechazar) to all basket members when a strategy triggers

## Documentation

- 📐 [Architecture](ARCHITECTURE.md) — design decisions, data flow, component overview
- 🚀 [Quick Start](QUICKSTART.md) — step-by-step first-run tutorial
- 🤖 [Briefing](BRIEFING.md) — full context for Claude-to-Claude handoff
- 🛠️ [How-to guides](docs/) — add strategies, deploy as service
- 📋 [Changelog](CHANGELOG.md) — version history

## Requirements

- Python 3.11+
- MariaDB / MySQL
- Telegram bot token ([BotFather](https://t.me/BotFather))
