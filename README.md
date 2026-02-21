# ScroogeBot 🦆

A Telegram investment bot for managing shared paper-trading baskets with automatic strategy alerts.

> *"Soy TioGilito"* — monitors your shared portfolios, fires RSI/MA-crossover alerts, and lets the group confirm trades right from Telegram.

## Features

| Command | Description |
|---------|-------------|
| `/start` | Register your Telegram account |
| `/cestas` | List all active baskets |
| `/cesta <name>` | Basket details (assets, members, cash) |
| `/valoracion` | EUR-converted portfolio valuation |
| `/cartera` | Open positions by basket |
| `/historial` | Recent order history |
| `/analiza <TICKER>` | RSI(14), SMA20/50, trend, 1d change |
| `/compra <TICKER> <qty>` | Paper-buy at live price |
| `/vende <TICKER> <qty>` | Paper-sell at live price |
| `/adduser @user OWNER\|MEMBER <basket>` | Add a member to a basket (OWNER only) |
| `/watchlist` | View your watchlist |
| `/addwatch <TICKER> Name \| note` | Add ticker to watchlist |

**Automatic alerts:** APScheduler scans positions every N minutes against the basket's strategy (StopLoss or MA-Crossover). When triggered, an inline keyboard is sent to all basket members to confirm or reject the trade.

## Architecture

```
src/
├── config.py              # pydantic-settings + config/config.yaml loader
├── db/
│   ├── models.py          # SQLAlchemy 2.0 async ORM (9 tables)
│   ├── base.py            # async_session_factory
│   ├── seed.py            # idempotent seeder from config.yaml
│   └── migrations/        # Alembic
├── data/
│   ├── base.py            # Abstract DataProvider
│   └── yahoo.py           # YahooDataProvider (yfinance)
├── portfolio/
│   └── engine.py          # PortfolioEngine — valuation with FX conversion
├── orders/
│   ├── base.py            # Abstract OrderExecutor
│   └── paper.py           # PaperTradingExecutor — updates cash + position
├── strategies/
│   ├── base.py            # Strategy ABC + Signal dataclass
│   ├── stop_loss.py       # StopLossStrategy (stop% / take-profit%)
│   └── ma_crossover.py    # MACrossoverStrategy (fast/slow MA crossover)
├── alerts/
│   └── engine.py          # AlertEngine — scans baskets, deduplicates, notifies
└── bot/
    ├── bot.py             # Application wiring + APScheduler + CallbackQueryHandler
    └── handlers/
        ├── portfolio.py   # /valoracion /cartera /historial
        ├── orders.py      # /compra /vende
        ├── baskets.py     # /cestas /cesta
        ├── analysis.py    # /analiza (RSI + SMA via ta library)
        └── admin.py       # /start /adduser /watchlist /addwatch
```

## Tech Stack

- **Python 3.11** — async throughout
- **python-telegram-bot v20+** — native async
- **SQLAlchemy 2.0** async + **aiomysql** — MariaDB
- **Alembic** — migrations
- **pydantic-settings** — `.env` + `config.yaml`
- **yfinance** — market data
- **ta 0.11** — RSI, SMA indicators
- **APScheduler 3.x** — async scheduler

## Setup

### 1. Prerequisites

- Python 3.11+
- MariaDB / MySQL
- A Telegram bot token ([BotFather](https://t.me/BotFather))

### 2. Install

```bash
git clone https://github.com/zell0ss/scroogebot.git
cd scroogebot
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 3. Configure

Copy `.env.example` to `.env` and fill in:

```env
TELEGRAM_APIKEY=your_bot_token
DATABASE_URL=mysql+aiomysql://user:pass@localhost/scroogebot
DATABASE_URL_SYNC=mysql+pymysql://user:pass@localhost/scroogebot
```

Edit `config/config.yaml` to define your baskets, assets, and strategy parameters.

### 4. Database

```bash
# Create DB (adjust credentials as needed)
mysql -u root -e "CREATE DATABASE scroogebot CHARACTER SET utf8mb4;"
mysql -u root -e "GRANT ALL ON scroogebot.* TO 'your_user'@'localhost';"

# Run migrations
alembic upgrade head

# Seed baskets and assets from config.yaml
python -c "import asyncio; from src.db.seed import seed; asyncio.run(seed())"
```

### 5. Run

```bash
python scroogebot.py
```

## Configuration

`config/config.yaml` controls baskets, assets, strategy parameters, and scheduler interval:

```yaml
scheduler:
  interval_minutes: 5

strategies:
  stop_loss:
    stop_loss_pct: 8.0      # sell if down >8% from period open
    take_profit_pct: 15.0   # sell if up >15% from period open
  ma_crossover:
    fast_period: 20
    slow_period: 50

baskets:
  - name: "Cesta Agresiva"
    strategy: ma_crossover
    risk_profile: aggressive
    cash: 10000.0
    assets: [AAPL, MSFT, GOOGL]
```

## Development

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src

# Add a migration after model changes
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Roadmap

See [docs/plans/2026-02-21-part3-backtest-advanced.md](docs/plans/2026-02-21-part3-backtest-advanced.md) for Part 3:

- `/backtest <TICKER> <strategy>` — vectorbt-powered backtesting
- RSIStrategy + BollingerBandsStrategy
- SafeHavenStrategy (rotate to bonds/gold on VIX spike)
- Market-hours-aware scheduler
- systemd service file

## License

MIT
