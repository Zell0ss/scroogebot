# /buscar Command Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement `/buscar <texto>` — a ticker search command that checks local DB assets first, then supplements with Yahoo Finance results.

**Architecture:** `SearchResult` dataclass added to `src/data/models.py`. `search_yahoo()` added to `YahooDataProvider` (not the ABC — search is Yahoo-specific). Handler does the async DB query itself, calls `search_yahoo()` for supplementary results, deduplicates by ticker, formats and replies.

**Tech Stack:** Python 3.11, yfinance 1.2.0 (`yf.Search`), SQLAlchemy async, python-telegram-bot v20+

---

## Task 1: `SearchResult` dataclass

**Files:**
- Modify: `src/data/models.py`
- Modify: `tests/test_sizing.py` — NO, use a new file
- Create: `tests/test_search.py`

**Step 1: Write the failing test**

Create `tests/test_search.py`:

```python
from src.data.models import SearchResult


def test_search_result_in_basket():
    r = SearchResult(
        ticker="SAN.MC",
        name="Banco Santander",
        exchange="MCE",
        type="Equity",
        in_basket=True,
        basket_name="Cesta Conservadora",
    )
    assert r.ticker == "SAN.MC"
    assert r.in_basket is True
    assert r.basket_name == "Cesta Conservadora"


def test_search_result_not_in_basket():
    r = SearchResult(
        ticker="SAN",
        name="Banco Santander S.A.",
        exchange="NYSE",
        type="Equity",
        in_basket=False,
        basket_name=None,
    )
    assert r.in_basket is False
    assert r.basket_name is None
```

**Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_search.py -v
```
Expected: `ImportError: cannot import name 'SearchResult' from 'src.data.models'`

**Step 3: Add `SearchResult` to `src/data/models.py`**

Append to the end of `src/data/models.py`:

```python
@dataclass
class SearchResult:
    ticker:      str
    name:        str
    exchange:    str
    type:        str        # "Equity", "ETF", "Fund", etc.
    in_basket:   bool
    basket_name: str | None
```

**Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_search.py -v
```
Expected: 2 PASSED

**Step 5: Commit**

```bash
git add src/data/models.py tests/test_search.py
git commit -m "feat(data): add SearchResult dataclass"
```

---

## Task 2: `search_yahoo()` on `YahooDataProvider`

**Files:**
- Modify: `src/data/yahoo.py`
- Modify: `tests/test_search.py` (append)

**Step 1: Write failing tests**

Append to `tests/test_search.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from src.data.yahoo import YahooDataProvider
from src.data.models import SearchResult


def _mock_quotes():
    return [
        {"symbol": "SAN", "shortname": "Banco Santander S.A.", "exchange": "NYQ", "typeDisp": "Equity"},
        {"symbol": "SAN.MC", "longname": "BANCO SANTANDER S.A.", "exchange": "MCE", "typeDisp": "Equity"},
        {"symbol": "BSBR", "shortname": "Banco Santander Brasil", "exchange": "NYQ", "typeDisp": "Equity"},
    ]


def test_search_yahoo_returns_search_results():
    provider = YahooDataProvider()
    mock_search = MagicMock()
    mock_search.quotes = _mock_quotes()
    with patch("yfinance.Search", return_value=mock_search):
        results = provider.search_yahoo("banco santander", max_results=5)
    assert len(results) == 3
    assert all(isinstance(r, SearchResult) for r in results)
    assert results[0].ticker == "SAN"
    assert results[0].in_basket is False
    assert results[0].basket_name is None


def test_search_yahoo_uses_shortname_with_fallback():
    provider = YahooDataProvider()
    mock_search = MagicMock()
    # Only longname available (no shortname)
    mock_search.quotes = [
        {"symbol": "BSAC", "longname": "Banco Santander Chile", "exchange": "NYQ", "typeDisp": "Equity"},
    ]
    with patch("yfinance.Search", return_value=mock_search):
        results = provider.search_yahoo("santander chile")
    assert results[0].name == "Banco Santander Chile"


def test_search_yahoo_skips_empty_symbols():
    provider = YahooDataProvider()
    mock_search = MagicMock()
    mock_search.quotes = [
        {"symbol": "", "shortname": "Bad entry", "exchange": "NYQ", "typeDisp": "Equity"},
        {"symbol": "SAN", "shortname": "Banco Santander S.A.", "exchange": "NYQ", "typeDisp": "Equity"},
    ]
    with patch("yfinance.Search", return_value=mock_search):
        results = provider.search_yahoo("santander")
    assert len(results) == 1
    assert results[0].ticker == "SAN"


def test_search_yahoo_returns_empty_on_error():
    provider = YahooDataProvider()
    with patch("yfinance.Search", side_effect=Exception("network error")):
        results = provider.search_yahoo("santander")
    assert results == []
```

**Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_search.py::test_search_yahoo_returns_search_results -v
```
Expected: `AttributeError: 'YahooDataProvider' object has no attribute 'search_yahoo'`

**Step 3: Add `search_yahoo()` to `src/data/yahoo.py`**

Add `import yfinance as yf` is already present. Add this method inside the `YahooDataProvider` class:

```python
def search_yahoo(self, query: str, max_results: int = 8) -> list:
    """Search Yahoo Finance by name or ticker. Returns list[SearchResult]."""
    from src.data.models import SearchResult
    try:
        quotes = yf.Search(query, max_results=max_results).quotes
    except Exception as e:
        logger.warning("yf.Search failed for %r: %s", query, e)
        return []
    results = []
    for q in quotes:
        ticker = q.get("symbol", "")
        if not ticker:
            continue
        name = q.get("shortname") or q.get("longname") or ticker
        results.append(SearchResult(
            ticker=ticker,
            name=name,
            exchange=q.get("exchange", ""),
            type=q.get("typeDisp", "Equity"),
            in_basket=False,
            basket_name=None,
        ))
    return results
```

Note: the import of `SearchResult` is inside the method to avoid a circular import (models imports nothing from yahoo, but keeping it inline is safe and explicit).

**Step 4: Run all search tests**

```bash
.venv/bin/pytest tests/test_search.py -v
```
Expected: 6 PASSED (2 from Task 1 + 4 new)

**Step 5: Run full suite to check no regressions**

```bash
.venv/bin/pytest tests/ -v --ignore=tests/test_data.py
```
Expected: all passing (test_data.py is excluded — it makes live network calls that are flaky)

**Step 6: Commit**

```bash
git add src/data/yahoo.py tests/test_search.py
git commit -m "feat(data): add search_yahoo() to YahooDataProvider"
```

---

## Task 3: `/buscar` handler

**Files:**
- Create: `src/bot/handlers/search.py`
- Modify: `src/bot/bot.py`

**Step 1: Create `src/bot/handlers/search.py`**

```python
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select, or_

from src.db.base import async_session_factory
from src.db.models import Asset, Basket, BasketAsset
from src.data.models import SearchResult
from src.data.yahoo import YahooDataProvider

logger = logging.getLogger(__name__)
_provider = YahooDataProvider()

MAX_RESULTS = 8
MIN_LOCAL_BEFORE_YAHOO = 3
MIN_QUERY_LEN = 2


def _format_results(query: str, local: list[SearchResult], yahoo: list[SearchResult]) -> str:
    if not local and not yahoo:
        return f'❌ Sin resultados para "{query}". Prueba con otro nombre o ticker.'

    lines = [f'🔍 *"{query}"*', ""]

    if local:
        lines.append("📌 *En tus cestas:*")
        for r in local:
            lines.append(f"  {r.ticker} — {r.name} ({r.exchange} · {r.type}) [{r.basket_name}]")

    if yahoo:
        if local:
            lines.append("")
        lines.append("🌐 *Yahoo Finance:*")
        for r in yahoo:
            lines.append(f"  {r.ticker} — {r.name} ({r.exchange} · {r.type})")

    # Suggest actions using the first local ticker, or first yahoo ticker
    first = local[0] if local else yahoo[0]
    lines += [
        "",
        f"▶ `/analiza {first.ticker}` · `/sizing {first.ticker}` · `/compra {first.ticker} 10`",
    ]
    return "\n".join(lines)


async def cmd_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /buscar <nombre o ticker>\nEjemplo: /buscar banco santander")
        return

    query = " ".join(context.args).strip()
    if len(query) < MIN_QUERY_LEN:
        await update.message.reply_text("La búsqueda debe tener al menos 2 caracteres.")
        return

    # 1. Local DB search
    async with async_session_factory() as session:
        rows = (await session.execute(
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
        )).all()

    local: list[SearchResult] = [
        SearchResult(
            ticker=asset.ticker,
            name=asset.name or asset.ticker,
            exchange=asset.market or "",
            type="Equity",
            in_basket=True,
            basket_name=basket.name,
        )
        for asset, basket in rows
    ]

    # 2. Yahoo fallback if local results are few
    yahoo: list[SearchResult] = []
    if len(local) < MIN_LOCAL_BEFORE_YAHOO:
        local_tickers = {r.ticker for r in local}
        remaining = MAX_RESULTS - len(local)
        all_yahoo = _provider.search_yahoo(query, max_results=MAX_RESULTS)
        yahoo = [r for r in all_yahoo if r.ticker not in local_tickers][:remaining]

    await update.message.reply_text(
        _format_results(query, local, yahoo),
        parse_mode="Markdown",
    )


def get_handlers():
    return [CommandHandler("buscar", cmd_buscar)]
```

**Step 2: Register in `src/bot/bot.py`**

Add import after `sizing_handlers` import:

```python
from src.bot.handlers.search import get_handlers as search_handlers
```

Add registration loop inside `run()` after the `sizing_handlers` loop:

```python
for handler in search_handlers():
    app.add_handler(handler)
```

**Step 3: Verify import**

```bash
.venv/bin/python -c "from src.bot.handlers.search import get_handlers; print('OK')"
```
Expected: `OK`

**Step 4: Run full test suite**

```bash
.venv/bin/pytest tests/ -v --ignore=tests/test_data.py
```
Expected: all passing (6 search tests + 50 sizing tests + others)

**Step 5: Commit**

```bash
git add src/bot/handlers/search.py src/bot/bot.py
git commit -m "feat(bot): /buscar command — local DB + Yahoo Finance ticker search"
```

---

## Task 4: Update `USER_MANUAL.md`

**Files:**
- Modify: `USER_MANUAL.md`

**Step 1: Add `/buscar` section**

In `USER_MANUAL.md`, add a new section under **Análisis técnico**, before `/analiza`:

```markdown
### `/buscar <texto>`

Busca tickers por nombre de empresa o símbolo. Primero busca entre los activos
de tus cestas (resultados marcados con 📌), y si hay pocos resultados consulta
también Yahoo Finance.

```
/buscar santander
/buscar banco santander
/buscar NVDA
```

**Muestra:**
- Activos en tus cestas que coincidan (con la cesta a la que pertenecen)
- Resultados adicionales de Yahoo Finance si hay menos de 3 locales
- Ticker, nombre, exchange y tipo (Equity, ETF, etc.)
- Sugerencia de comandos para el primer resultado
```

**Step 2: Add to summary table**

In the Resumen de comandos table, add after `/analiza`:

```
| `/buscar <texto>` | Buscar tickers por nombre | Registrado |
```

**Step 3: Commit**

```bash
git add USER_MANUAL.md
git commit -m "docs: add /buscar to USER_MANUAL"
```

---

## Final verification

```bash
# All tests pass
.venv/bin/pytest tests/ --ignore=tests/test_data.py -v

# Import chain is clean
.venv/bin/python -c "
from src.bot.handlers.search import get_handlers
from src.data.models import SearchResult
print('SearchResult fields:', [f.name for f in SearchResult.__dataclass_fields__.values()])
print('Handlers:', get_handlers())
"
```

Expected output:
```
SearchResult fields: ['ticker', 'name', 'exchange', 'type', 'in_basket', 'basket_name']
Handlers: [<CommandHandler for /buscar>]
```
