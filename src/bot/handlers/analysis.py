import logging

import ta.momentum
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from src.data.yahoo import YahooDataProvider

logger = logging.getLogger(__name__)
_provider = YahooDataProvider()


async def cmd_analiza(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /analiza TICKER")
        return
    ticker = context.args[0].upper()
    msg = await update.message.reply_text(f"⏳ Analizando {ticker}...")
    try:
        price = _provider.get_current_price(ticker)
        ohlcv = _provider.get_historical(ticker, period="3mo", interval="1d")
        close = ohlcv.data["Close"]

        rsi_series = ta.momentum.RSIIndicator(close=close, window=14).rsi()
        rsi_val = rsi_series.iloc[-1] if rsi_series is not None and not rsi_series.empty else None
        sma20 = close.rolling(20).mean().iloc[-1]
        sma50 = close.rolling(50).mean().iloc[-1]
        change_1d = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100
        sign = "+" if change_1d >= 0 else ""

        lines = [
            f"📊 *Análisis: {ticker}*",
            f"💰 Precio: {price.price:.2f} {price.currency}",
            f"📅 Cambio 1d: {sign}{change_1d:.2f}%",
            "",
            f"SMA 20: {sma20:.2f}",
            f"SMA 50: {sma50:.2f}",
            f"Tendencia: {'📈 Alcista' if sma20 > sma50 else '📉 Bajista'}",
        ]
        if rsi_val is not None:
            if rsi_val > 70:
                rsi_label = "sobrecomprado 🔴"
            elif rsi_val < 30:
                rsi_label = "sobrevendido 🟢"
            else:
                rsi_label = "neutral ⚪"
            lines.append(f"RSI (14): {rsi_val:.1f} — {rsi_label}")
        lines.append(f"\n🔍 [Finviz](https://finviz.com/quote.ashx?t={ticker})")
        await msg.edit_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"❌ Error analizando {ticker}: {e}")


def get_handlers():
    return [CommandHandler("analiza", cmd_analiza)]
