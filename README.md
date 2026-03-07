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

- `/valoracion` `/historial` — portfolio valuation with live prices, order history
- `/analiza <TICKER>` — RSI(14), SMA20/50, trend, 1-day change
- `/compra` `/vende` — paper-buy and paper-sell at live market price
- `/cesta [nombre]` `/nuevacesta` `/eliminarcesta` — list, inspect, create, and remove baskets
- `/backtest [período]` — historical strategy simulation (vectorbt)
- `/montecarlo <cesta>` — Monte Carlo simulator: percentile returns, VaR, CVaR, Sharpe
- `/sizing <TICKER>` — position sizing with ATR-based stop and risk budget
- `/estrategia <cesta>` — view or change strategy + per-basket stop-loss %
- `/start` `/adduser` `/watchlist` `/buscar` — registration, roles, watchlist, ticker search
- **Automatic alerts** — APScheduler scans positions every 5 min; stop-loss layer applied on top of any strategy; inline keyboard (✅ Ejecutar / ❌ Rechazar) sent to all basket members

## Documentation

- 📖 [User Manual](USER_MANUAL.md) — all commands with examples (Spanish)
- 🇪🇸 [Guía de inicio](GUIA_INICIO.md) — crash course de inversión con el bot (Spanish)
- 🚀 [Quick Start](QUICKSTART.md) — get a working bot from the repo in ~10 minutes
- 📐 [Architecture](ARCHITECTURE.md) — design decisions, data flow, component overview
- 📋 [Changelog](CHANGELOG.md) — version history

## Video guides

- 🎬 [Estrategias de ScroogeBot](docs/video/Estrategias_de_ScroogeBot.mp4) — overview of the 5 built-in strategies
- 🎬 [Guía para invertir en España](docs/video/Guía_para_invertir_en_España.mp4) — investing basics for Spanish-speaking users
- 🎬 [Fondos, fondos indexados y etfs](docs/video/Fondos,_ETFs_y_Fiscalidad.mp4) — investing basics for Spanish-speaking users

## Requirements

- Python 3.11+
- MariaDB / MySQL
- Telegram bot token ([BotFather](https://t.me/BotFather))
