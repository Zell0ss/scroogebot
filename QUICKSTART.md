# Quick Start: ScroogeBot

In this guide you'll set up ScroogeBot and send your first paper trade from Telegram.

**Estimated time**: 10 minutes

---

## Prerequisites

- Python 3.11+
- MariaDB / MySQL running locally
- A Telegram account + bot token (from [@BotFather](https://t.me/BotFather))

---

## Step 1: Install

```bash
git clone https://github.com/zell0ss/scroogebot.git
cd scroogebot
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

**Expected output**:
```
Successfully installed scroogebot-0.1.0 ...
```

---

## Step 2: Configure

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```env
TELEGRAM_APIKEY=1234567890:ABCdef...   # from BotFather /newbot
DATABASE_URL=mysql+aiomysql://scroogebot:password@localhost/scroogebot
DATABASE_URL_SYNC=mysql+pymysql://scroogebot:password@localhost/scroogebot
```

Where to get each value:
- `TELEGRAM_APIKEY`: open [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token
- `DATABASE_URL` / `DATABASE_URL_SYNC`: your MariaDB host, user, password, database name

---

## Step 3: Database setup

```bash
# Create the database and user (adjust password)
sudo mysql -e "
  CREATE DATABASE scroogebot CHARACTER SET utf8mb4;
  CREATE USER 'scroogebot'@'localhost' IDENTIFIED BY 'password';
  GRANT ALL ON scroogebot.* TO 'scroogebot'@'localhost';
  FLUSH PRIVILEGES;
"

# Run migrations (creates all 9 tables)
alembic upgrade head

# Seed baskets and assets from config/config.yaml
python -c "import asyncio; from src.db.seed import seed; asyncio.run(seed())"
```

**Expected output**:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 2df3a1ef5417, initial schema
Seeded basket: Cesta Agresiva
Seeded basket: Cesta Conservadora
Seeded 6 assets.
```

---

## Step 4: Run the bot

```bash
python scroogebot.py
```

**Expected output**:
```
INFO  scroogebot - ScroogeBot starting — scanning every 5min
```

Now open your Telegram bot and send:

```
/start
```

**Expected response**:
```
¡Hola [YourName]! 🦆 Soy TioGilito.
Usa /valoracion para ver el estado de tus cestas.
Usa /cestas para ver las cestas disponibles.
```

---

## Step 5: Your first paper trade

```
/analiza AAPL
```
→ Shows RSI, SMA trend, 1-day change for Apple.

```
/compra AAPL 3
```
→ Paper-buys 3 shares of AAPL at the live market price.

```
/cartera
```
→ Shows your open positions.

---

## Next steps

- 📐 [Architecture](ARCHITECTURE.md) — understand how AlertEngine and strategies work
- 🤖 [Briefing](BRIEFING.md) — full technical context
- 🛠️ [Add a custom strategy](docs/HOW-TO-ADD-STRATEGY.md)
- 🚀 [Deploy as a service](docs/HOW-TO-DEPLOY.md)
- ⚙️ Edit `config/config.yaml` to change baskets, assets, or strategy parameters

---

## Troubleshooting

### Problem: `ModuleNotFoundError: No module named 'src'`

**Cause**: Not installed in editable mode or wrong directory.

**Solution**:
```bash
pip install -e .
```

### Problem: `Access denied for user` (DB error)

**Cause**: DB user lacks privileges.

**Solution**:
```bash
sudo mysql -e "GRANT ALL ON scroogebot.* TO 'scroogebot'@'localhost'; FLUSH PRIVILEGES;"
```

### Problem: Bot doesn't respond

**Cause**: Wrong or expired Telegram token.

**Solution**: Create a new token with BotFather and update `.env`.
