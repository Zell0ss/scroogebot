import logging

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from prometheus_client import REGISTRY

from src.config import app_config
from src.scheduler.market_hours import is_market_open

logger = logging.getLogger(__name__)


def _get_counter(name: str, labels: dict) -> int:
    v = REGISTRY.get_sample_value(name, labels)
    return int(v) if v is not None else 0


def _get_float(name: str) -> float:
    v = REGISTRY.get_sample_value(name)
    return float(v) if v is not None else 0.0


async def cmd_estado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show operational metrics since last bot restart."""
    if not update.message:
        return

    # --- Scans ---
    completed = _get_counter("scroogebot_alert_scans_total", {"result": "completed"})
    skipped   = _get_counter("scroogebot_alert_scans_total", {"result": "skipped_closed"})

    # --- Average scan duration ---
    dur_sum   = _get_float("scroogebot_scan_duration_seconds_sum")
    dur_count = _get_float("scroogebot_scan_duration_seconds_count")
    avg_dur   = dur_sum / dur_count if dur_count > 0 else None

    # --- Alerts breakdown: {strategy}·{signal} ---
    alerts_parts: list[str] = []
    total_alerts = 0
    for mf in REGISTRY.collect():
        if mf.name == "scroogebot_alerts_generated":
            for sample in mf.samples:
                if sample.name == "scroogebot_alerts_generated_total" and sample.value > 0:
                    count = int(sample.value)
                    total_alerts += count
                    alerts_parts.append(
                        f"{sample.labels['strategy']}·{sample.labels['signal']} x{count}"
                    )

    # --- Markets ---
    market_cfg = app_config.get("scheduler", {}).get("market_hours", {})
    market_parts: list[str] = []
    for market in market_cfg:
        if is_market_open(market):
            market_parts.append(f"🟢 {market}: abierto")
        else:
            market_parts.append(f"🔴 {market}: cerrado")

    # --- Commands breakdown (successful only, sorted by frequency) ---
    cmd_counts: dict[str, int] = {}
    for mf in REGISTRY.collect():
        if mf.name == "scroogebot_commands":
            for sample in mf.samples:
                if (
                    sample.name == "scroogebot_commands_total"
                    and sample.labels.get("success") == "true"
                    and sample.value > 0
                ):
                    cmd_counts[sample.labels["command"]] = int(sample.value)
    cmd_parts = [
        f"{cmd} x{n}"
        for cmd, n in sorted(cmd_counts.items(), key=lambda x: -x[1])
    ]

    # --- Build message ---
    lines = ["📊 *ScroogeBot — estado*", ""]

    lines.append(
        f"🔄 Escaneos: {completed} completados · {skipped} omitidos (mercado cerrado)"
    )

    if total_alerts:
        lines.append(f"⚠️ Alertas: {total_alerts} ({', '.join(alerts_parts)})")
    else:
        lines.append("💤 Alertas: ninguna generada")

    if avg_dur is not None:
        lines.append(f"⏱ Duración media escaneo: {avg_dur:.2f} s")

    if market_parts:
        lines.append(" · ".join(market_parts))

    if cmd_parts:
        lines.append(f"📋 Comandos: {' · '.join(cmd_parts)}")
    else:
        lines.append("📋 Comandos: ninguno aún")

    lines += ["", "_Contadores desde el último arranque._"]

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def get_handlers():
    return [CommandHandler("estado", cmd_estado)]
