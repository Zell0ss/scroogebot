"""Market open/close hours — UTC-based guard for the alert scheduler.

Reads open/close times from config.yaml under scheduler.market_hours.
Markets are always considered closed on Saturdays and Sundays.
Unknown markets return True so they are never silently skipped.
"""
from datetime import datetime, time
import logging

from src.config import app_config

logger = logging.getLogger(__name__)


def _parse_time(t: str) -> time:
    h, m = t.split(":")
    return time(int(h), int(m))


def is_market_open(market: str) -> bool:
    """Return True if *market* is currently within its configured open hours (UTC).

    Falls back to True for unknown markets so unrecognised tickers are not
    silently dropped from alert scans.
    """
    cfg = app_config.get("scheduler", {}).get("market_hours", {})
    hours = cfg.get(market.upper())
    if not hours:
        return True  # unknown market — allow
    now = datetime.utcnow()
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    open_t = _parse_time(hours["open"])
    close_t = _parse_time(hours["close"])
    return open_t <= now.time() < close_t


def any_market_open() -> bool:
    """Return True if at least one configured market is currently open (UTC)."""
    cfg = app_config.get("scheduler", {}).get("market_hours", {})
    if not cfg:
        return True  # no config — always scan
    return any(is_market_open(m) for m in cfg)
