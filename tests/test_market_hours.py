"""Tests for src/scheduler/market_hours.py"""
from datetime import datetime
from unittest.mock import patch

import pytest

from src.scheduler.market_hours import is_market_open, any_market_open


def _mock_utcnow(hour: int, minute: int = 0, weekday: int = 1):
    """Build a fake datetime for patching (weekday: 0=Mon … 6=Sun)."""
    # Use a Monday (2026-02-23) as base, adjust weekday via isoweekday mapping
    # Simple: just pick known dates
    # Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
    base_days = {0: 23, 1: 24, 2: 25, 3: 26, 4: 27, 5: 28, 6: 1}  # Feb 2026
    day = base_days[weekday]
    month = 2 if weekday < 6 else 3
    return datetime(2026, month, day, hour, minute, 0)


class TestIsMarketOpen:
    def test_nyse_open_during_trading_hours(self):
        # 16:00 UTC is within NYSE 14:30–21:00
        with patch("src.scheduler.market_hours.datetime") as mock_dt:
            mock_dt.utcnow.return_value = _mock_utcnow(16, 0, weekday=1)  # Tuesday
            assert is_market_open("NYSE") is True

    def test_nyse_closed_before_open(self):
        # 13:00 UTC is before NYSE open at 14:30
        with patch("src.scheduler.market_hours.datetime") as mock_dt:
            mock_dt.utcnow.return_value = _mock_utcnow(13, 0, weekday=1)
            assert is_market_open("NYSE") is False

    def test_nyse_closed_after_close(self):
        # 22:00 UTC is after NYSE close at 21:00
        with patch("src.scheduler.market_hours.datetime") as mock_dt:
            mock_dt.utcnow.return_value = _mock_utcnow(22, 0, weekday=1)
            assert is_market_open("NYSE") is False

    def test_ibex_open_during_trading_hours(self):
        # 10:00 UTC is within BME 08:00–16:30
        with patch("src.scheduler.market_hours.datetime") as mock_dt:
            mock_dt.utcnow.return_value = _mock_utcnow(10, 0, weekday=1)
            assert is_market_open("BME") is True

    def test_ibex_closed_after_close(self):
        # 17:00 UTC is after BME close at 16:30
        with patch("src.scheduler.market_hours.datetime") as mock_dt:
            mock_dt.utcnow.return_value = _mock_utcnow(17, 0, weekday=1)
            assert is_market_open("BME") is False

    def test_closed_on_saturday(self):
        # NYSE would normally be open at 16:00 but it's Saturday
        with patch("src.scheduler.market_hours.datetime") as mock_dt:
            mock_dt.utcnow.return_value = _mock_utcnow(16, 0, weekday=5)  # Saturday
            assert is_market_open("NYSE") is False

    def test_closed_on_sunday(self):
        with patch("src.scheduler.market_hours.datetime") as mock_dt:
            mock_dt.utcnow.return_value = _mock_utcnow(16, 0, weekday=6)  # Sunday
            assert is_market_open("NYSE") is False

    def test_unknown_market_always_open(self):
        # Unknown markets should not silently block alert scans
        with patch("src.scheduler.market_hours.datetime") as mock_dt:
            mock_dt.utcnow.return_value = _mock_utcnow(3, 0, weekday=1)  # deep night
            assert is_market_open("CRYPTO") is True

    def test_case_insensitive(self):
        with patch("src.scheduler.market_hours.datetime") as mock_dt:
            mock_dt.utcnow.return_value = _mock_utcnow(16, 0, weekday=1)
            assert is_market_open("nyse") is True


class TestAnyMarketOpen:
    def test_returns_true_when_nyse_open(self):
        # 16:00 UTC — NYSE is open, BME is closed
        with patch("src.scheduler.market_hours.datetime") as mock_dt:
            mock_dt.utcnow.return_value = _mock_utcnow(16, 0, weekday=1)
            assert any_market_open() is True

    def test_returns_true_when_ibex_open(self):
        # 09:00 UTC — BME is open, NYSE not yet
        with patch("src.scheduler.market_hours.datetime") as mock_dt:
            mock_dt.utcnow.return_value = _mock_utcnow(9, 0, weekday=1)
            assert any_market_open() is True

    def test_returns_false_when_all_closed(self):
        # 23:00 UTC — both NYSE and BME are closed
        with patch("src.scheduler.market_hours.datetime") as mock_dt:
            mock_dt.utcnow.return_value = _mock_utcnow(23, 0, weekday=1)
            assert any_market_open() is False

    def test_returns_false_on_weekend(self):
        # Saturday 16:00 UTC
        with patch("src.scheduler.market_hours.datetime") as mock_dt:
            mock_dt.utcnow.return_value = _mock_utcnow(16, 0, weekday=5)
            assert any_market_open() is False
