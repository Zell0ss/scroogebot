# How to Deploy ScroogeBot as a Service

## Goal

By the end of this guide ScroogeBot will run as a systemd service that starts automatically on boot, restarts on crash, and logs to journald.

## Context

Use this when moving from development (`python scroogebot.py`) to production on a Linux VPS or home server.

---

## Steps

### 1. Prepare the production environment

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

---

### 2. Configure environment

```bash
sudo cp /opt/scroogebot/.env.example /opt/scroogebot/.env
sudo nano /opt/scroogebot/.env
# Fill in TELEGRAM_APIKEY and DATABASE_URL values
sudo chown scroogebot:scroogebot /opt/scroogebot/.env
sudo chmod 600 /opt/scroogebot/.env   # secrets only readable by owner
```

---

### 3. Run migrations

```bash
cd /opt/scroogebot
sudo -u scroogebot .venv/bin/alembic upgrade head
sudo -u scroogebot .venv/bin/python -c "import asyncio; from src.db.seed import seed; asyncio.run(seed())"
```

**Expected output**:
```
✓ Running upgrade  -> 2df3a1ef5417, initial schema
✓ Seeded basket: Cesta Agresiva
```

---

### 4. Create the systemd service file

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

**Why `WorkingDirectory`**: `config/config.yaml` and Alembic are resolved relative to CWD.

---

### 5. Enable and start

```bash
sudo systemctl daemon-reload
sudo systemctl enable scroogebot
sudo systemctl start scroogebot
```

**Verify**:
```bash
sudo systemctl status scroogebot
```

**Expected output**:
```
● scroogebot.service - ScroogeBot Telegram Investment Bot
     Loaded: loaded (/etc/systemd/system/scroogebot.service; enabled)
     Active: active (running) since ...
```

---

### 6. View logs

```bash
# Live logs
sudo journalctl -u scroogebot -f

# Last 50 lines
sudo journalctl -u scroogebot -n 50
```

---

## Updating the bot

```bash
cd /opt/scroogebot
sudo -u scroogebot git pull
sudo -u scroogebot .venv/bin/pip install -e .
sudo -u scroogebot .venv/bin/alembic upgrade head
sudo systemctl restart scroogebot
sudo systemctl status scroogebot
```

---

## Troubleshooting

### Problem: `Service failed to start`

**Solution**:
```bash
sudo journalctl -u scroogebot -n 30
# Look for ImportError, connection refused, or missing .env variable
```

### Problem: `ModuleNotFoundError` in systemd but works manually

**Cause**: Wrong Python path or `WorkingDirectory` not set.

**Solution**: Confirm `ExecStart` points to the venv Python: `/opt/scroogebot/.venv/bin/python`.

### Problem: DB connection refused

**Cause**: MariaDB not running or wrong host in `DATABASE_URL`.

**Solution**:
```bash
sudo systemctl status mariadb
# If stopped:
sudo systemctl start mariadb
```

### Problem: Bot stops responding after a few hours

**Cause**: Telegram network timeout kills the long-polling connection.

**Solution**: `Restart=on-failure` in the service file handles this — confirm it's set. Check `RestartSec` is not 0.
