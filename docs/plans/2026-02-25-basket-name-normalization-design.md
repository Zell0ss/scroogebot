# Basket Name Normalization — Design

**Date:** 2026-02-25
**Status:** Approved

## Problem

`Basket.name` uses exact string comparison in 11 places. A user who types `/cesta Cancion` will not find a basket created as "Canción". Worse, creating both "cancion" and "Canción" produces two distinct rows — silent data corruption.

## Goal

- `/cesta cancion`, `/cesta Canción`, `/cesta CANCION` all resolve to the same basket.
- Creating "canción" when "cancion" already exists is rejected with a clear error.
- The original display name (`name`) is preserved exactly as the user typed it.

## Out of scope

- Tickers (already uppercased at input with `args[0].upper()`)
- `/buscar` (already uses `.ilike()` on `Asset.name`/`Asset.ticker`)
- Strategy names, market names

## Chosen Approach: `name_normalized` column (Option A)

A new DB column `name_normalized` stores the accent-stripped, lowercased form. A unique constraint on this column enforces global uniqueness. All lookups query by `name_normalized`. The original `name` is unchanged and used only for display.

### Why not MariaDB collation (Option B)?

`utf8mb4_unicode_ci` is case-insensitive but its accent sensitivity is version-dependent. The Python column approach is explicit, portable, and testable without DB knowledge.

---

## Architecture

### Normalization function — `src/utils/text.py` (new file)

```python
import unicodedata

def normalize_basket_name(name: str) -> str:
    """Accent-strip + lowercase. 'Canción Agresiva' → 'cancion agresiva'."""
    nfkd = unicodedata.normalize('NFKD', name.strip())
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()
```

Pure stdlib, no dependencies.

### DB model — `src/db/models.py`

Add to `Basket` class, after `name`:

```python
name_normalized: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
```

The `unique=True` is the safety net. The Python-level check before INSERT gives the friendly error message.

### Lookup pattern (all 11 sites)

Before:
```python
Basket.name == basket_name
```

After:
```python
Basket.name_normalized == normalize_basket_name(basket_name)
```

The input variable (`basket_name`, `name`, `basket_override`, `basket_name_arg`, `basket_cfg["name"]`) is already the raw string from the user or config — just wrap it.

### Creation pattern (`admin.py` `/crearcesta`)

```python
# Duplicate check (friendly error)
dup = await session.execute(
    select(Basket).where(Basket.name_normalized == normalize_basket_name(basket_name))
)
if dup.scalar_one_or_none():
    await update.message.reply_text(
        f'❌ Ya existe una cesta llamada `{basket_name}`. '
        'Los nombres no distinguen mayúsculas ni acentos.',
        parse_mode="Markdown",
    )
    return

basket = Basket(
    name=basket_name,
    name_normalized=normalize_basket_name(basket_name),
    strategy=strategy,
    ...
)
```

### Seed — `src/db/seed.py`

Add `name_normalized=normalize_basket_name(basket_cfg["name"])` to the `Basket(...)` constructor call.

---

## Alembic Migration

Three-step upgrade in a single migration function — add nullable, populate with Python `unicodedata`, then constrain:

```python
def upgrade():
    import unicodedata

    def _norm(s):
        nfkd = unicodedata.normalize('NFKD', s.strip())
        return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()

    # Step 1: add as nullable
    op.add_column('baskets', sa.Column('name_normalized', sa.String(100), nullable=True))

    # Step 2: populate existing rows
    conn = op.get_bind()
    for row in conn.execute(sa.text("SELECT id, name FROM baskets")):
        conn.execute(
            sa.text("UPDATE baskets SET name_normalized = :n WHERE id = :id"),
            {"n": _norm(row.name), "id": row.id},
        )

    # Step 3: enforce NOT NULL + UNIQUE
    op.alter_column('baskets', 'name_normalized', nullable=False)
    op.create_unique_constraint('uq_baskets_name_normalized', 'baskets', ['name_normalized'])


def downgrade():
    op.drop_constraint('uq_baskets_name_normalized', 'baskets', type_='unique')
    op.drop_column('baskets', 'name_normalized')
```

---

## Error Handling

| Scenario | Handling |
|---|---|
| "canción" when "cancion" exists | Python check → friendly message before hitting DB |
| Race condition (two concurrent creates) | `IntegrityError` on `UNIQUE` → generic "error interno" |
| Name contains only combining characters after strip | Extremely unlikely; would result in empty string → `nullable=False` rejects |

Uniqueness scope: **global** (includes inactive baskets). This prevents confusion if a basket is deactivated and recreated.

---

## Tests

New file `tests/test_normalize.py` — pure unit tests, no DB:

```python
from src.utils.text import normalize_basket_name

def test_accents():         assert normalize_basket_name("Canción") == "cancion"
def test_uppercase():       assert normalize_basket_name("Lab_AVANZADO") == "lab_avanzado"
def test_mixed():           assert normalize_basket_name("Cesta Agresiva") == "cesta agresiva"
def test_strips_spaces():   assert normalize_basket_name("  Eco  ") == "eco"
def test_already_normal():  assert normalize_basket_name("cartera") == "cartera"
def test_enie():            assert normalize_basket_name("España") == "espana"
def test_umlaut():          assert normalize_basket_name("Über") == "uber"
```

Existing tests that build `Basket` mocks: add `name_normalized="..."` where the field is accessed (minimal impact — most basket mock tests don't touch this field).

---

## Files Changed

| File | Change |
|---|---|
| `src/utils/text.py` | **new** — `normalize_basket_name()` |
| `src/db/models.py` | add `name_normalized` field to `Basket` |
| `src/db/migrations/versions/<hash>_add_basket_name_normalized.py` | **new** — 3-step migration |
| `src/db/seed.py` | populate `name_normalized` in constructor + lookup |
| `src/bot/handlers/admin.py` | 4 lookups + creation dup check + error message |
| `src/bot/handlers/baskets.py` | 2 lookups |
| `src/bot/handlers/orders.py` | 2 lookups |
| `src/bot/handlers/backtest.py` | 1 lookup |
| `src/bot/handlers/montecarlo.py` | 1 lookup |
| `tests/test_normalize.py` | **new** — 7 unit tests |

Total: 10 files, 11 lookup sites mechanically updated.
