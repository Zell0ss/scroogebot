"""Prometheus metrics for ScroogeBot.

Exposes an HTTP endpoint (default :9090/metrics) that Prometheus can scrape.
All metric objects are module-level singletons — import and use directly.

Metrics exposed:
  scroogebot_alert_scans_total        counter  result=completed|skipped_closed
  scroogebot_alerts_generated_total   counter  strategy=<name>, signal=BUY|SELL
  scroogebot_scan_duration_seconds    histogram
  scroogebot_market_open              gauge    market=NYSE|BME|LSE …
  scroogebot_commands_total           counter  command=<name>, success=true|false
"""
import logging

from prometheus_client import Counter, Gauge, Histogram, start_http_server

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

alert_scans_total = Counter(
    "scroogebot_alert_scans_total",
    "Number of alert scan runs",
    ["result"],          # "completed" | "skipped_closed"
)

alerts_generated_total = Counter(
    "scroogebot_alerts_generated_total",
    "Number of trading alerts generated",
    ["strategy", "signal"],   # strategy name, "BUY" | "SELL"
)

scan_duration_seconds = Histogram(
    "scroogebot_scan_duration_seconds",
    "Wall-clock duration of a full alert scan (seconds)",
    buckets=[0.5, 1, 2, 5, 10, 30, 60],
)

market_open = Gauge(
    "scroogebot_market_open",
    "Whether a configured market is currently open (1 = open, 0 = closed)",
    ["market"],
)

commands_total = Counter(
    "scroogebot_commands_total",
    "Number of bot write-commands executed",
    ["command", "success"],   # success = "true" | "false"
)


# ---------------------------------------------------------------------------
# Server bootstrap
# ---------------------------------------------------------------------------

def start_metrics_server(port: int = 9090) -> None:
    """Start the Prometheus metrics HTTP server in a background thread.

    Safe to call from async context — prometheus_client uses a daemon thread.
    Logs a warning and continues if the port is already in use.
    """
    try:
        start_http_server(port)
        logger.info(f"Prometheus metrics server listening on :{port}/metrics")
    except OSError as exc:
        logger.warning(f"Could not start metrics server on port {port}: {exc}")
