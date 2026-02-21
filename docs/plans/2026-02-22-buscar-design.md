# Design: /buscar command — Ticker Search

**Date:** 2026-02-22
**Status:** Approved

---

## Problem

Users know the company name but not the exact ticker symbol needed for `/analiza`, `/sizing`, or `/compra`. There is no way to discover tickers from within the bot.

---

## Goals

- `/buscar <texto>` → list of matching tickers with exchange and type
- Local DB results first (assets in baskets), marked with their basket
- Yahoo Finance fallback when local results < 3
- No new DB tables or migrations

## Non-goals

- Fuzzy/phonetic matching (LIKE is sufficient)
- Pagination (max 8 results total)
- Adding found tickers to a basket from this command

---

## Architecture

Approach A — `search_yahoo()` on `YahooDataProvider` (composition, not ABC extension).

The `DataProvider` ABC is **not modified** — search is Yahoo-specific and not meaningful to abstract. The handler does the async DB query itself, then calls `provider.search_yahoo()` for supplementary results.

```
src/data/models.py          # + SearchResult dataclass
src/data/yahoo.py           # + search_yahoo(query, max_results) → list[SearchResult]
src/bot/handlers/search.py  # cmd_buscar + get_handlers()
src/bot/bot.py              # + import + registration loop
USER_MANUAL.md              # + /buscar section and table row
```

---

## Data model

```python
# src/data/models.py

@dataclass
class SearchResult:
    ticker:      str
    name:        str
    exchange:    str
    type:        str        # "Equity", "ETF", "Fund", etc.
    in_basket:   bool       # True if asset exists in local DB
    basket_name: str | None # basket name if in_basket, else None
```

---

## YahooDataProvider.search_yahoo()

```python
def search_yahoo(self, query: str, max_results: int = 8) -> list[SearchResult]:
    results = yf.Search(query, max_results=max_results).quotes
    out = []
    for q in results:
        ticker = q.get("symbol", "")
        name = q.get("shortname") or q.get("longname") or ticker
        exchange = q.get("exchange", "")
        typ = q.get("typeDisp", "Equity")
        if ticker:
            out.append(SearchResult(
                ticker=ticker, name=name, exchange=exchange,
                type=typ, in_basket=False, basket_name=None
            ))
    return out
```

---

## Handler flow

```python
async def cmd_buscar(update, context):
    query = " ".join(context.args).strip()

    # 1. Local DB search (async)
    async with async_session_factory() as session:
        rows = await session.execute(
            select(Asset, Basket)
            .join(BasketAsset, BasketAsset.asset_id == Asset.id)
            .join(Basket, BasketAsset.basket_id == Basket.id)
            .where(
                or_(
                    Asset.name.ilike(f"%{query}%"),
                    Asset.ticker.ilike(f"%{query}%"),
                ),
                Basket.active == True,
                BasketAsset.active == True,
            )
        )
    local = [SearchResult(ticker=a.ticker, name=a.name or a.ticker,
                          exchange=a.market or "", type="Equity",
                          in_basket=True, basket_name=b.name)
             for a, b in rows.all()]

    # 2. Yahoo fallback if local < 3
    yahoo = []
    if len(local) < 3:
        local_tickers = {r.ticker for r in local}
        all_yahoo = provider.search_yahoo(query, max_results=8)
        yahoo = [r for r in all_yahoo if r.ticker not in local_tickers]
        yahoo = yahoo[:8 - len(local)]

    # 3. Format and reply
```

---

## Response format

```
🔍 "banco santander"

📌 En tus cestas:
  SAN.MC — Banco Santander (MCE · Equity) [Cesta Conservadora]

🌐 Yahoo Finance:
  SAN    — Banco Santander, S.A. (NYSE · Equity)
  BSBR   — Banco Santander Brasil SA (NYSE · Equity)
  BSAC   — Banco Santander Chile (NYSE · Equity)

▶ /analiza SAN.MC · /sizing SAN.MC · /compra SAN.MC 10
```

If no results anywhere:
```
❌ Sin resultados para "xyzzy". Prueba con otro nombre o ticker.
```

---

## Error handling

- `yf.Search` network error → log warning, show only local results (or "sin resultados de Yahoo" note)
- Empty query → usage message
- Query too short (< 2 chars) → reject with message

---

## Testing

- `test_search_yahoo_returns_results()` — mock `yf.Search`, verify `SearchResult` list
- `test_search_yahoo_empty_query_raises()` — verify empty quotes handled
- `test_search_result_deduplication()` — local ticker excluded from Yahoo results
- Handler tested via import smoke test only (consistent with other handlers)
