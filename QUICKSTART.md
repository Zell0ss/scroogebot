# Quick Start: ScroogeBot

Get a working bot from the repo in ~10 minutes, then optionally deploy it as a production service.

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
/start               → confirms registration
/sel Cesta Agresiva  → select a basket as active context
/compra AAPL 3       → paper-buy 3 shares of AAPL
/cartera             → see open positions
```

---

## 6. Production deployment (systemd)

Use this when moving from `python scroogebot.py` to a Linux VPS or home server that starts automatically on boot and restarts on crash.

### 6.1 Prepare the production environment

```bash
# Create a dedicated system user (no login shell)
sudo useradd -r -s /sbin/nologin scroogebot

# Clone the repo to a stable location
sudo git clone https://github.com/zell0ss/scroogebot.git /opt/scroogebot
sudo chown -R scroogebot:scroogebot /opt/scroogebot

# Install dependencies
sudo -u scroogebot python3.11 -m venv /opt/scroogebot/.venv
sudo -u scroogebot /opt/scroogebot/.venv/bin/pip install -e "/opt/scroogebot[dev]"
```

### 6.2 Configure secrets

```bash
sudo cp /opt/scroogebot/.env.example /opt/scroogebot/.env
sudo nano /opt/scroogebot/.env          # fill in TELEGRAM_APIKEY and DB credentials
sudo chown scroogebot:scroogebot /opt/scroogebot/.env
sudo chmod 600 /opt/scroogebot/.env     # readable only by the service user
```

### 6.3 Run migrations

```bash
sudo -u scroogebot /opt/scroogebot/.venv/bin/alembic upgrade head
sudo -u scroogebot /opt/scroogebot/.venv/bin/python -c \
  "import asyncio; from src.db.seed import seed; asyncio.run(seed())"
```

### 6.4 Create the systemd unit

```bash
sudo nano /etc/systemd/system/scroogebot.service
```

Paste:

```ini
[Unit]
Description=ScroogeBot Telegram Investment Bot
After=network.target mariadb.service
Wants=mariadb.service

[Service]
Type=simple
User=scroogebot
Group=scroogebot
WorkingDirectory=/opt/scroogebot
EnvironmentFile=/opt/scroogebot/.env
ExecStart=/opt/scroogebot/.venv/bin/python scroogebot.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=scroogebot

[Install]
WantedBy=multi-user.target
```

> `WorkingDirectory` is required — `config/config.yaml` and Alembic resolve paths relative to CWD.

### 6.5 Enable and start

```bash
sudo systemctl daemon-reload
sudo systemctl enable scroogebot
sudo systemctl start scroogebot
sudo systemctl status scroogebot
```

### 6.6 View logs

```bash
sudo journalctl -u scroogebot -f       # live tail
sudo journalctl -u scroogebot -n 50    # last 50 lines
```

### 6.7 Updating

```bash
cd /opt/scroogebot
sudo -u scroogebot git pull
sudo -u scroogebot .venv/bin/pip install -e .
sudo -u scroogebot .venv/bin/alembic upgrade head
sudo systemctl restart scroogebot
sudo systemctl status scroogebot
```

---

## Makefile shortcuts (dev)

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

**`alembic upgrade head` fails** — ensure `DATABASE_URL_SYNC` is set in `.env` (Alembic uses the sync driver).

**Bot doesn't respond** — wrong or expired token; generate a new one with BotFather and update `.env`.

**`Service failed to start` (systemd)** — inspect logs:
```bash
sudo journalctl -u scroogebot -n 30
# Look for ImportError, connection refused, or missing .env variable
```

**`ModuleNotFoundError` in systemd but works manually** — confirm `ExecStart` points to the venv Python: `/opt/scroogebot/.venv/bin/python`.

**DB connection refused (systemd)** — check MariaDB is running:
```bash
sudo systemctl status mariadb
sudo systemctl start mariadb    # if stopped
```

**Bot stops responding after a few hours** — Telegram network timeout kills long-polling. `Restart=on-failure` in the service file handles this automatically; confirm it is set and `RestartSec` is not `0`.

---

## Further reading

- [USER_MANUAL.md](USER_MANUAL.md) — all commands with examples
- [ARCHITECTURE.md](ARCHITECTURE.md) — design decisions, data flow, component reference
- [GUIA_INICIO.md](GUIA_INICIO.md) — crash course in investing with the bot (Spanish)
