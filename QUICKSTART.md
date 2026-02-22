# Quick Start: ScroogeBot

Get a working bot from the repo in ~10 minutes.

**Prerequisites**: Python 3.11+, MariaDB/MySQL, a Telegram bot token from [@BotFather](https://t.me/BotFather).

---

## 1. Install

```bash
git clone https://github.com/zell0ss/scroogebot.git
cd scroogebot
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

---

## 2. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```env
TELEGRAM_APIKEY=1234567890:ABCdef...
DATABASE_URL=mysql+aiomysql://scroogebot:password@localhost/scroogebot
DATABASE_URL_SYNC=mysql+pymysql://scroogebot:password@localhost/scroogebot
```

- `TELEGRAM_APIKEY`: [@BotFather](https://t.me/BotFather) → `/newbot` → copy token
- `DATABASE_URL*`: your MariaDB host, user, password, DB name

---

## 3. Database

```bash
# Create DB and user (requires sudo mysql access)
sudo mysql -e "
  CREATE DATABASE scroogebot CHARACTER SET utf8mb4;
  CREATE USER 'scroogebot'@'localhost' IDENTIFIED BY 'password';
  GRANT ALL ON scroogebot.* TO 'scroogebot'@'localhost';
  FLUSH PRIVILEGES;
"

# Run all migrations (creates all 10 tables)
.venv/bin/alembic upgrade head

# Seed model baskets + assets from config/config.yaml
make seed
# or: .venv/bin/python -c "import asyncio; from src.db.seed import seed; asyncio.run(seed())"
```

---

## 4. Register yourself

The bot requires users to be pre-registered. Start the bot first:

```bash
make run
# or: .venv/bin/python scroogebot.py
```

Send `/start` in Telegram — the bot will show your **Telegram ID**. Then register from the bot (if you're the first user, you need to insert directly):

```bash
# Direct DB insert for the first admin user (replace with your actual tg_id and username)
sudo mysql scroogebot -e "INSERT INTO users (tg_id, username, first_name) VALUES (123456789, 'yourusername', 'YourName');"
```

Subsequent users can be added via `/register <tg_id> <username>` from any registered user.

---

## 5. First trade

```
/start          → confirms registration
/sel Cesta Agresiva   → select a basket as active context
/compra AAPL 3  → paper-buy 3 shares of AAPL
/cartera        → see open positions
```

---

## Makefile shortcuts

```bash
make run        # start the bot
make seed       # (re)seed model baskets from config.yaml
make migrate    # alembic upgrade head
make test       # run full test suite
make test-v     # verbose tests
make logs       # tail scroogebot.log
```

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'src'`** — run `pip install -e .` from the repo root.

**`Access denied for user`** — run:
```bash
sudo mysql -e "GRANT ALL ON scroogebot.* TO 'scroogebot'@'localhost'; FLUSH PRIVILEGES;"
```

**Bot doesn't respond** — wrong or expired token; generate a new one with BotFather and update `.env`.

**`alembic upgrade head` fails** — ensure `DATABASE_URL_SYNC` is set in `.env` (Alembic uses the sync driver).

---

## Further reading

- [USER_MANUAL.md](USER_MANUAL.md) — all commands with examples
- [ARCHITECTURE.md](ARCHITECTURE.md) — design decisions, data flow, component reference
- [GUIA_INICIO.md](GUIA_INICIO.md) — crash course in investing with the bot (Spanish)
