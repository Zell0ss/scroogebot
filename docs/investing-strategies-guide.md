# Investing Strategies — A Beginner's Guide

*Written for someone who knows what an asset is but has never invested a euro.*

---

## Table of Contents

1. [Why do people invest?](#1-why-do-people-invest)
2. [The two schools of analysis](#2-the-two-schools-of-analysis)
3. [Reading a price chart — the basics](#3-reading-a-price-chart--the-basics)
4. [What is a strategy?](#4-what-is-a-strategy)
5. [Strategy 1 — Stop-Loss / Take-Profit](#5-strategy-1--stop-loss--take-profit)
6. [Strategy 2 — Moving Average Crossover](#6-strategy-2--moving-average-crossover)
7. [Strategy 3 — RSI (Relative Strength Index)](#7-strategy-3--rsi-relative-strength-index)
8. [Strategy 4 — Bollinger Bands](#8-strategy-4--bollinger-bands)
9. [Strategy 5 — Safe Haven Rotation](#9-strategy-5--safe-haven-rotation)
10. [How ScroogeBot uses these strategies](#10-how-scroogebot-uses-these-strategies)
11. [Key takeaways](#11-key-takeaways)
12. [Further reading & videos](#12-further-reading--videos)

---

## 1. Why do people invest?

Money sitting in a bank account loses purchasing power over time because of **inflation** — every year, the same €100 buys slightly less than it did the year before. Historically, inflation runs at around 2–3% per year in developed economies.

Investing means putting your money to work in assets that (you hope) grow faster than inflation. Common investable assets include:

| Asset type | What it is | Rough long-term return |
|---|---|---|
| **Stocks / Shares** | Ownership stake in a company | ~7–10% per year (S&P 500 historical avg.) |
| **Bonds** | You lend money to a government or company | ~2–5% per year |
| **Gold** | Physical precious metal | ~5–7% per year long-term |
| **Cash** | Bank account / deposits | ~0–2%, beaten by inflation |

> **The core trade-off:** higher potential return always comes with higher risk of losing money. Stocks can fall 40% in a bad year. Gold can go sideways for a decade.

The strategies in this guide are tools that try to answer one question: **when should you buy, and when should you sell?**

---

## 2. The two schools of analysis

Before diving into strategies, you need to know there are two completely different philosophies for making investment decisions:

### Fundamental Analysis

Study the **underlying business or asset**. Is Apple profitable? Is its debt manageable? Will AI increase demand for its products? If the business is solid and the price is fair, you buy and hold for years.

*Best for:* Long-term investors, pension funds, Warren Buffett.

### Technical Analysis

Ignore the business entirely. Instead, study **price patterns and statistics** derived from historical price data. The idea is that prices move in patterns that repeat, and these patterns can be spotted before they fully play out.

*Best for:* Active traders, short-term strategies, algorithmic bots like ScroogeBot.

> **ScroogeBot uses technical analysis exclusively.** All five strategies below work purely from price history — no company earnings reports, no news reading required.

---

## 3. Reading a price chart — the basics

All technical strategies start with a **price chart**. The most common format is the **candlestick chart**, but for our purposes the simpler **line chart** (connecting daily closing prices) is enough to understand how each strategy works.

```
Price
  │                              ╭────
  │               ╭──────────────╯
  │           ╭───╯
  │     ╭─────╯
  │─────╯
  └──────────────────────────────────── Time
      Jan   Feb   Mar   Apr   May
```

Key terms you'll encounter:

- **Close price** — the price at market close each day. Most indicators are calculated from this.
- **Volume** — how many shares/units traded that day. High volume strengthens a signal.
- **Trend** — a sustained move upward (uptrend) or downward (downtrend).
- **Support** — a price level the market has repeatedly bounced up from.
- **Resistance** — a price level the market has repeatedly struggled to break above.
- **Volatility** — how wildly the price swings day to day.

---

## 4. What is a strategy?

A **trading strategy** is a set of rules that tells you:

1. **When to BUY** (open a position)
2. **When to SELL** (close a position)
3. **How much** to buy or sell

A good strategy must be **mechanical** — you apply the same rules every time, without emotion. The enemy of investing is fear and greed: panic-selling during crashes, and chasing rallies too late. Rules remove the emotion.

In ScroogeBot, each strategy is evaluated every 5 minutes for every asset in a basket. It returns one of three outcomes:

- **BUY signal** → alert sent to the group
- **SELL signal** → alert sent to the group
- **No signal** → nothing happens (hold)

---

## 5. Strategy 1 — Stop-Loss / Take-Profit

### The idea

This is the simplest strategy and the one every investor learns first. It answers: *"How much loss am I willing to tolerate before I cut my position? How much gain before I lock in profit?"*

You set two thresholds relative to your entry price:

- **Stop-loss:** if the price drops X% below where you bought, automatically sell. Prevents a small loss becoming a catastrophic one.
- **Take-profit:** if the price rises Y% above where you bought, automatically sell. Locks in gains before the market reverses.

### Example

You buy Apple at €100.

```
         Take-profit at +15%  ──  €115  ← SELL
         ─────────────────────────────────
         Entry price          ──  €100
         ─────────────────────────────────
         Stop-loss at −8%     ──  €92   ← SELL
```

If Apple climbs to €115, the bot sells and you pocket a 15% gain.
If Apple drops to €92, the bot sells and caps your loss at 8%.
If Apple trades between €92 and €115, nothing happens.

### How ScroogeBot implements it

```
stop_loss_pct:    8.0   (sell if down 8% from period open)
take_profit_pct: 15.0   (sell if up 15% from period open)
```

The reference price is the **first close price in the data window** (roughly 3 months of history). This means the strategy compares today's price to where the asset was ~3 months ago.

### The risk-reward ratio

In this configuration, you risk 8% to target 15% — a **1:1.875 ratio**. A common rule of thumb is to never accept worse than 1:2 (risk 1 to win 2). The closer your stop-loss, the more often you'll be stopped out by normal day-to-day noise.

### When it works best

- **Always useful as a safety net**, even when combined with other strategies.
- Most valuable in **volatile markets** where large swings are common.
- Less useful for long-term buy-and-hold portfolios where temporary dips are expected.

### When it fails

- If the price gaps down overnight past your stop-loss (common with news events), you might sell at a much worse price than intended.
- A stop-loss set too tight gets triggered by normal volatility — you sell at −8% and then the stock rebounds to +20%.

---

## 6. Strategy 2 — Moving Average Crossover

### What is a Moving Average?

A **Moving Average (MA)** smooths out the noisy day-to-day price fluctuations and shows the underlying trend. Instead of showing today's price, it shows the **average price over the last N days**.

A 20-day Moving Average on any given day = *(sum of the last 20 close prices) ÷ 20*

```
  Price (noisy)         Moving Average (smooth)
  │╭╮╭╮  ╭╮            │     ╭────────
  │╯╰╯╰──╯╰╮            │╭────╯
  │         ╰╮           ││
  │          ╰──          │╯
  └──────────────          └──────────────
```

### The crossover signal

The strategy uses **two** moving averages:

- A **fast MA** — short window, reacts quickly to price changes (ScroogeBot: 20 days)
- A **slow MA** — long window, filters out more noise (ScroogeBot: 50 days)

When the **fast MA crosses above the slow MA**, the trend is accelerating upward → **BUY signal**.
When the **fast MA crosses below the slow MA**, the trend is decelerating → **SELL signal**.

```
Price
  │              fast MA ╭── crossing above slow MA
  │                  ╭───╯────────── fast MA
  │            ╭─────╯   ╰───────── slow MA
  │      ╭─────╯
  │──────╯
  └──────┴─────┴─────┴──────────────── Time
             ↑ BUY here
```

### The Golden Cross and Death Cross

These are the famous versions of the MA crossover in long-term investing:

- **Golden Cross** — 50-day MA crosses above 200-day MA. Often treated as a major bullish signal for stocks.
- **Death Cross** — 50-day MA crosses below 200-day MA. Bearish warning.

ScroogeBot uses a faster version (MA20 / MA50) which is more sensitive and generates more signals but also more false ones.

### How ScroogeBot implements it

```
fast_period: 20   (20-day simple moving average)
slow_period: 50   (50-day simple moving average)
```

The signal fires **only on the day of the crossover** — not while the fast MA is merely above or below the slow one. This avoids generating repeated signals for an existing trend.

### When it works best

- **Trending markets** — when assets are consistently moving in one direction over weeks or months.
- Works well on **liquid, large-cap stocks** like Apple, Microsoft, Nvidia.
- Best with **daily or weekly timeframes** (less noise than intraday).

### When it fails

- **Sideways / choppy markets** — when the price oscillates without a clear trend, the two MAs crisscross repeatedly and generate a string of false signals (called "whipsaws").
- It is inherently **lagging** — by the time the crossover happens, the trend may be well underway and you're buying near the top.

### Visual analogy

Think of the fast MA as a speedboat — it turns quickly. The slow MA is a tanker — it turns slowly. When the speedboat overtakes the tanker (going the same direction), the market is accelerating. When the tanker overtakes the speedboat, momentum is shifting.

---

## 7. Strategy 3 — RSI (Relative Strength Index)

### What is momentum?

Before explaining RSI, understand **momentum**: markets tend to keep moving in the direction they're already moving — *until they don't*. A stock that's been rising for two weeks straight is likely to keep rising... but at some point, everyone who wanted to buy has already bought, and there are no more buyers to push the price higher. The stock becomes **overbought**.

RSI measures this.

### The RSI formula

RSI was invented by J. Welles Wilder in 1978. It produces a number between **0 and 100**:

```
RSI = 100 − (100 / (1 + RS))
where RS = average gain over N days / average loss over N days
```

You don't need to memorize the formula. The key is the output:

```
   100 ─────────────────────────────────
    70 ── OVERBOUGHT ZONE ──────────────  ← sell zone
    50 ── MIDLINE ───────────────────────
    30 ── OVERSOLD ZONE ───────────────   ← buy zone
     0 ─────────────────────────────────
```

- **RSI above 70** → the asset has risen very fast recently → possibly overbought → potential SELL
- **RSI below 30** → the asset has fallen very fast recently → possibly oversold → potential BUY
- **RSI around 50** → neutral, no strong signal

### The crossover signal (how ScroogeBot uses it)

A naive approach would be: "sell whenever RSI > 70, buy whenever RSI < 30." But this gives constant signals. ScroogeBot instead waits for a **zone exit crossover**:

- **BUY** fires when RSI was ≤ 30 yesterday and is > 30 today — the asset is *leaving* the oversold zone, suggesting the selling pressure has exhausted itself.
- **SELL** fires when RSI was ≥ 70 yesterday and is < 70 today — leaving the overbought zone.

```
RSI
  70 ─────────────╮─────────────
                  ╰──────────────  ← SELL signal fires as RSI exits overbought zone
  30 ──────╭─────────────────────
           │╰──────               ← BUY signal fires as RSI exits oversold zone
  Time:    Jan      Feb      Mar
```

### ScroogeBot configuration

```
period:     14   (14-day RSI, the standard)
oversold:   30
overbought: 70
```

### When it works best

- **Range-bound markets** — when a stock oscillates between support and resistance without a clear trend. RSI is excellent here.
- **Mean-reversion setups** — the idea that after an extreme move, the price tends to "snap back" toward the average.
- Useful as a **confirmation tool** alongside other strategies.

### When it fails

- In a **strong uptrend**, RSI can stay above 70 for weeks. Selling because "RSI is overbought" means selling your best performers.
- In a **strong downtrend**, RSI can stay below 30 while the stock keeps crashing. Buying an "oversold" stock in a bear market is dangerous.

> **Key lesson:** RSI says "fast" or "slow" — it does not say "up" or "down." Always check the trend direction before acting on RSI signals.

---

## 8. Strategy 4 — Bollinger Bands

### The building blocks

Bollinger Bands were invented by John Bollinger in 1983. They are built from two concepts you already understand:

1. **Moving Average** — the middle band is a 20-day simple MA (same as before)
2. **Standard Deviation** — a measure of how spread out prices have been

The three bands are:
```
Upper band  = MA(20) + 2 × standard_deviation(20)
Middle band = MA(20)
Lower band  = MA(20) − 2 × standard_deviation(20)
```

### What they look like

```
Price
  │    ╭──────────────────── Upper band (MA + 2σ)
  │   ╱╲   ╭──── price ─────────────────────────
  │  ╱  ╲─╯╱────────────── Middle band (MA20)
  │ ╱    ╰╯╲─────────────── Lower band (MA − 2σ)
  │╱          ╲
  └───────────────────────────────────── Time
```

### The key property: volatility

When the market is quiet, the bands **narrow** (squeeze). When volatility spikes, the bands **widen**. This makes Bollinger Bands a built-in volatility gauge.

Statistically, roughly **95% of all price action falls within the bands** (the 2-standard-deviation zone). When the price reaches or breaks through a band, something unusual is happening.

### How ScroogeBot uses it

- **BUY** when the current price touches or falls below the **lower band** — the asset has moved unusually far down; the expectation is a reversion to the middle.
- **SELL** when the current price touches or rises above the **upper band** — unusually far up; expect a pullback.

```
Upper band ───────────────────────────── SELL if price touches this
              ╭────────╮
Middle ────────╯        ╰──────────────── MA20
                         ╰─────
Lower band ───────────────────────────── BUY if price touches this
```

### ScroogeBot configuration

```
period:  20   (20-day MA for the middle band)
std_dev:  2   (bands are 2 standard deviations wide)
```

### When it works best

- **Mean-reversion in quiet, range-bound markets** — great for stable blue-chip stocks or ETFs that oscillate in a predictable range.
- **Detecting breakouts** — a price breaking decisively outside the bands after a long squeeze often signals the start of a strong new trend.
- Works well **combined with RSI** (both are mean-reversion indicators and confirm each other).

### When it fails

- **Strong trends** — in a sustained bull run, the price can "walk the upper band" for weeks. Every time it touches the upper band, ScroogeBot would want to sell — but the price keeps going up.
- Like RSI, Bollinger Bands work best when the market is consolidating, not trending.

> **John Bollinger's own warning:** "A tag of a band is not in itself a buy or sell signal." The bands show where price *is* relative to recent history — they don't tell you what it will do next.

---

## 9. Strategy 5 — Safe Haven Rotation

### The concept: not all assets fall together

When a stock market crisis hits — a recession, a pandemic, a war — investors panic and sell stocks. But they don't just hold cash. They **rotate** their money into assets that historically hold value or even rise during crises:

| Safe haven asset | Why it's considered safe |
|---|---|
| **Gold (GLD)** | Physical, limited supply, no counterparty risk, 5,000 years of value storage |
| **US Treasury Bonds (TLT)** | Backed by the US government; demand rises in crises |
| **Short-term Treasuries (SHY, VGSH)** | Near-cash safety, very low volatility |
| **Bond ETFs (BND)** | Diversified bonds, stable income |

### What is a drawdown?

A **drawdown** measures how far a price has fallen from its most recent peak:

```
                Peak price: €120
                ─────────────────
Current price: €100

Drawdown = (120 − 100) / 120 = 16.7%
```

A drawdown of 16.7% means you've lost 16.7% from the highest point this asset reached.

### How ScroogeBot implements it

The SafeHaven strategy watches the **drawdown from the rolling peak** of each risky asset:

```
drawdown_threshold: 8%   (from safe_haven or stop_loss config)
```

- If a non-safe-haven asset drops **8% or more from its recent peak** → **SELL signal** with 80% confidence
- If the asset is itself a safe haven (GLD, TLT, BND, SHY, VGSH) → **no signal** (never sell safe havens via this strategy)

The logic: if your risky assets (like Santander, Iberdrola) are falling significantly from their highs, something bad may be happening in the market. Time to exit and move to safety.

### The portfolio rotation idea

In practice, a full safe-haven rotation strategy would:
1. **Sell** the falling risky asset (ScroogeBot does this)
2. **Buy** a safe haven asset with the proceeds (the human operator decides this via the alert keyboard)

This is called **tactical asset allocation** — shifting the portfolio mix based on market conditions, rather than holding a fixed allocation forever.

### How ScroogeBot uses it: the Conservative Basket

```yaml
# config/config.yaml
- name: "Cesta Conservadora"
  strategy: safe_haven
  assets:
    - SAN.MC   (Banco Santander — risky: will trigger SELL on drawdown)
    - IBE.MC   (Iberdrola — risky: will trigger SELL on drawdown)
    - GLD      (Gold ETF — safe haven: never sells, only holds)
```

The conservative basket already holds GLD as a defensive position. If Santander or Iberdrola draw down 8%+ from their recent peaks, the bot alerts the group to sell them.

### When it works best

- **Market corrections and bear markets** — protects capital when broad markets fall.
- **Crisis events** (rate hikes, geopolitical conflicts, recessions) — gold and bonds tend to rally when stocks crash.
- Ideal for **conservative or capital-preservation portfolios**.

### When it fails

- **Inflation spikes** — both gold AND bonds can fall during high inflation (2022 was painful for bond holders).
- **False drawdowns** — normal market corrections of 10–15% happen even in healthy bull markets. Rotating to safe havens at every 8% dip means missing the recovery.
- Gold sometimes moves with risk assets (2020 COVID crash, gold fell initially alongside stocks).

---

## 10. How ScroogeBot uses these strategies

ScroogeBot runs an **AlertEngine** every 5 minutes. For each basket, it:

1. Fetches the latest prices from Yahoo Finance
2. Runs each asset through the basket's assigned strategy
3. If a signal fires (BUY or SELL), checks whether the same alert already exists to avoid duplicates
4. Sends a Telegram message to the group with a confirmation keyboard:
   - **✅ Ejecutar** → places a paper trade automatically
   - **❌ Rechazar** → dismisses the alert

```
Basket: Cesta Agresiva       Strategy: MA Crossover (MA20/MA50)
Assets: AAPL, MSFT, NVDA     Risk profile: Aggressive

Basket: Cesta Conservadora   Strategy: Safe Haven (8% drawdown)
Assets: SAN.MC, IBE.MC, GLD  Risk profile: Conservative
```

The `/backtest` command lets you test any strategy on historical data — running each strategy across years of daily prices to see metrics like total return, Sharpe ratio, max drawdown, and win rate.

### Combining strategies

No single strategy is best in all market conditions. Professional fund managers often combine them:

| Condition | Best strategy |
|---|---|
| Strong uptrend | MA Crossover (ride the trend) |
| Sideways, range-bound | RSI or Bollinger Bands (mean reversion) |
| Market uncertainty / crisis | Safe Haven Rotation |
| Any condition | Stop-Loss/Take-Profit (always active as safety net) |

---

## 11. Key takeaways

1. **No strategy wins 100% of the time.** A strategy with a 55% win rate and good risk management beats one with 80% wins but massive losses on the 20% losers.

2. **The trend is your friend.** Before applying any indicator, always check: is this asset in an uptrend, downtrend, or sideways? It changes how you interpret everything.

3. **Backtesting isn't a guarantee.** A strategy that worked perfectly on historical data may fail when the market changes. Past performance ≠ future results.

4. **Risk management is more important than picking winners.** Stop-losses and position sizing (how much to put into any one bet) matter more than finding the perfect entry point.

5. **Paper trading first.** ScroogeBot is a paper-trading bot — it simulates trades without real money. Use it to test strategies with zero financial risk before committing capital.

---

## 12. Further reading & videos

### Stop-Loss / Take-Profit

- [eToro — How to Set Stop-Loss and Take-Profit Targets](https://www.etoro.com/trading/how-to-set-stop-loss-and-take-profit-targets/)
- [Admiral Markets — How to Use Stop Loss and Take Profit](https://admiralmarkets.com/education/articles/forex-basics/how-to-use-stop-loss-and-take-profit-in-forex-trading)
- [FOREX.com — Stop Losses and Take Profits Course](https://www.forex.com/en/trading-academy/courses/how-to-trade/stop-losses-and-take-profits/)
- YouTube search: **"stop loss take profit explained beginners"** → look for videos from channels like Investopedia, Trading 212, or Rayner Teo

### Moving Averages & Crossover

- [Babypips — How to Use Moving Average Crossovers](https://www.babypips.com/learn/forex/moving-average-crossover-trading)
- [TrendSpider — Moving Average Crossover Strategies](https://trendspider.com/learning-center/moving-average-crossover-strategies/)
- [Morpher — Mastering the Moving Average Crossover Strategy](https://www.morpher.com/blog/moving-average-crossover)
- YouTube search: **"moving average crossover strategy explained"** → look for "golden cross death cross" videos

### RSI (Relative Strength Index)

- [StockCharts ChartSchool — RSI](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/relative-strength-index-rsi) *(the gold standard reference)*
- [Fidelity — RSI Indicator Guide](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/RSI)
- [OANDA — Understanding the RSI](https://www.oanda.com/us-en/trade-tap-blog/trading-knowledge/understanding-the-relative-strength-index/)
- YouTube search: **"RSI indicator explained beginners"** → Rayner Teo and Adam Khoo have clear explainers

### Bollinger Bands

- [Charles Schwab — Bollinger Bands: What They Are and How to Use Them](https://www.schwab.com/learn/story/bollinger-bands-what-they-are-and-how-to-use-them)
- [Fidelity — Understanding Bollinger Bands](https://www.fidelity.com/viewpoints/active-investor/understanding-bollinger-bands)
- [Babypips — How to Use Bollinger Bands](https://www.babypips.com/learn/forex/bollinger-bands)
- YouTube search: **"Bollinger Bands trading strategy explained"** → look for videos by Rayner Teo or the official Bollinger Bands channel

### Safe Haven Assets & Defensive Investing

- [Chase — What Are Safe Haven Assets?](https://www.chase.com/personal/investments/learning-and-insights/article/what-are-safe-haven-assets)
- [SmartAsset — Safe Haven Assets](https://smartasset.com/investing/safe-haven-assets)
- [J.P. Morgan — Rethinking Safe Haven Assets](https://am.jpmorgan.com/br/en/asset-management/adv/insights/ltcma/rethinking-safe-haven-assets/)
- YouTube search: **"safe haven assets investing explained gold bonds"** → look for videos from financial education channels like Two Cents or The Plain Bagel

### General investing fundamentals (start here if completely new)

- [Khan Academy — Stocks and bonds](https://www.khanacademy.org/economics-finance-domain/core-finance/stock-and-bonds) *(free, excellent, goes from zero)*
- YouTube channel: **The Plain Bagel** — clear, unbiased investing fundamentals
- YouTube channel: **Two Cents (PBS)** — personal finance, very beginner-friendly
- YouTube channel: **Investopedia** — covers all the above indicators with visuals

---

*This guide is for educational purposes about how ScroogeBot's strategies work. It is not financial advice. Paper trading (simulated) involves no real money. Before investing real capital, consult a qualified financial advisor.*
