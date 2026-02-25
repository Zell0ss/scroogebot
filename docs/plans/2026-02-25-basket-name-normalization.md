# Basket Name Normalization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make basket name lookups and uniqueness checks case-insensitive and accent-insensitive so `/cesta cancion` finds "Canción" and creating "canción" when "cancion" exists is rejected.

**Architecture:** A new `name_normalized` column on `Basket` stores the accent-stripped, lowercased form. A `normalize_basket_name()` function in `src/utils/text.py` (pure stdlib, `unicodedata`) normalizes on write and on lookup. A `UNIQUE` constraint on `name_normalized` enforces global uniqueness at the DB level.

**Tech Stack:** Python 3.11, SQLAlchemy 2.0 async, Alembic, MariaDB. Virtual env at `.venv/`. Run tests with `.venv/bin/pytest tests/ -q`.

---

## Task 1: normalize_basket_name() utility + tests (TDD)

**Files:**
- Create: `src/utils/__init__.py` (empty)
- Create: `src/utils/text.py`
- Create: `tests/test_normalize.py`

**Step 1: Create the tests first**

Create `tests/test_normalize.py`:

```python
from src.utils.text import normalize_basket_name

def test_accents():
    assert normalize_basket_name("Canción") == "cancion"

def test_uppercase():
    assert normalize_basket_name("Lab_AVANZADO") == "lab_avanzado"

def test_mixed():
    assert normalize_basket_name("Cesta Agresiva") == "cesta agresiva"

def test_strips_spaces():
    assert normalize_basket_name("  Eco  ") == "eco"

def test_already_normal():
    assert normalize_basket_name("cartera") == "cartera"

def test_enie():
    assert normalize_basket_name("España") == "espana"

def test_umlaut():
    assert normalize_basket_name("Über") == "uber"
```

**Step 2: Run tests — confirm they fail**

```bash
cd /data/scroogebot && .venv/bin/pytest tests/test_normalize.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.utils'`

**Step 3: Create the utility**

Create `src/utils/__init__.py` (empty file).

Create `src/utils/text.py`:

```python
import unicodedata


def normalize_basket_name(name: str) -> str:
    """Accent-strip + lowercase for case/accent-insensitive basket lookups.

    Examples:
        'Canción' → 'cancion'
        'Lab_AVANZADO' → 'lab_avanzado'
        '  Eco  ' → 'eco'
    """
    nfkd = unicodedata.normalize('NFKD', name.strip())
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()
```

**Step 4: Run tests — confirm they pass**

```bash
cd /data/scroogebot && .venv/bin/pytest tests/test_normalize.py -v
```

Expected: 7 tests PASS.

**Step 5: Run full suite**

```bash
cd /data/scroogebot && .venv/bin/pytest tests/ -q
```

Expected: all existing tests still pass.

**Step 6: Commit**

```bash
cd /data/scroogebot && git add src/utils/ tests/test_normalize.py
git commit -m "feat(utils): normalize_basket_name() for accent/case-insensitive matching"
```

---

## Task 2: Add name_normalized to Basket model + Alembic migration

**Files:**
- Modify: `src/db/models.py`
- Run: `alembic revision --autogenerate` + `alembic upgrade head`

**Step 1: Add field to models.py**

In `src/db/models.py`, the `Basket` class currently starts:
```python
class Basket(Base):
    __tablename__ = "baskets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
```

Add `name_normalized` immediately after `name`:

```python
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, server_default="")
```

The `server_default=""` is temporary — it lets Alembic generate the column as NOT NULL without requiring data already populated. We'll fix it in the migration.

**Step 2: Generate migration**

```bash
cd /data/scroogebot && .venv/bin/alembic revision --autogenerate -m "add_basket_name_normalized"
```

Expected: new file in `src/db/migrations/versions/`.

**Step 3: Replace the generated migration body**

Open the generated file and replace its `upgrade()` and `downgrade()` with:

```python
import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    import unicodedata

    def _norm(s: str) -> str:
        nfkd = unicodedata.normalize('NFKD', s.strip())
        return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()

    # Step 1: add as nullable (no server_default needed — we populate manually)
    op.add_column('baskets', sa.Column('name_normalized', sa.String(100), nullable=True))

    # Step 2: populate existing rows using Python unicodedata
    conn = op.get_bind()
    for row in conn.execute(sa.text("SELECT id, name FROM baskets")):
        conn.execute(
            sa.text("UPDATE baskets SET name_normalized = :n WHERE id = :id"),
            {"n": _norm(row.name), "id": row.id},
        )

    # Step 3: apply NOT NULL + UNIQUE
    op.alter_column('baskets', 'name_normalized', nullable=False)
    op.create_unique_constraint('uq_baskets_name_normalized', 'baskets', ['name_normalized'])


def downgrade() -> None:
    op.drop_constraint('uq_baskets_name_normalized', 'baskets', type_='unique')
    op.drop_column('baskets', 'name_normalized')
```

Also remove the `server_default=""` from models.py now (it was only scaffolding):

```python
    name_normalized: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
```

**Step 4: Apply migration**

```bash
cd /data/scroogebot && .venv/bin/alembic upgrade head
```

Expected: `Running upgrade ... → <hash>, add_basket_name_normalized`

**Step 5: Run full suite**

```bash
cd /data/scroogebot && .venv/bin/pytest tests/ -q
```

Expected: all tests pass.

**Step 6: Commit**

```bash
cd /data/scroogebot && git add src/db/models.py src/db/migrations/
git commit -m "feat(db): add Basket.name_normalized column (accent/case normalized)"
```

---

## Task 3: Update seed.py

**Files:**
- Modify: `src/db/seed.py`

**Step 1: Add import**

At the top of `src/db/seed.py`, add:

```python
from src.utils.text import normalize_basket_name
```

**Step 2: Update the Basket lookup**

Find:
```python
result = await session.execute(
    select(Basket).where(Basket.name == basket_cfg["name"])
)
```

Replace with:
```python
result = await session.execute(
    select(Basket).where(Basket.name_normalized == normalize_basket_name(basket_cfg["name"]))
)
```

**Step 3: Populate name_normalized on creation**

Find the `Basket(...)` constructor call:
```python
basket = Basket(
    name=basket_cfg["name"],
    strategy=basket_cfg["strategy"],
    ...
)
```

Add `name_normalized`:
```python
basket = Basket(
    name=basket_cfg["name"],
    name_normalized=normalize_basket_name(basket_cfg["name"]),
    strategy=basket_cfg["strategy"],
    ...
)
```

**Step 4: Run full suite**

```bash
cd /data/scroogebot && .venv/bin/pytest tests/ -q
```

**Step 5: Commit**

```bash
cd /data/scroogebot && git add src/db/seed.py
git commit -m "feat(seed): populate name_normalized on basket creation"
```

---

## Task 4: Update all basket lookups in handlers

**Files:**
- Modify: `src/bot/handlers/admin.py`
- Modify: `src/bot/handlers/baskets.py`
- Modify: `src/bot/handlers/orders.py`
- Modify: `src/bot/handlers/backtest.py`
- Modify: `src/bot/handlers/montecarlo.py`

All 5 files follow the same pattern. Add the import, then replace every `Basket.name ==` lookup.

### admin.py

**Step 1: Add import** at top of `src/bot/handlers/admin.py`:

```python
from src.utils.text import normalize_basket_name
```

**Step 2: Replace 4 lookups** — search for all occurrences of `Basket.name == basket_name` (there are 3) and `Basket.name == basket_name` in the adduser handler (line ~129). Replace each with:

```python
Basket.name_normalized == normalize_basket_name(basket_name)
```

Also update the duplicate check in `/crearcesta` (line ~411):

Before:
```python
dup_result = await session.execute(select(Basket).where(Basket.name == basket_name, Basket.active == True))
if dup_result.scalar_one_or_none():
    await update.message.reply_text(f"Ya existe una cesta con el nombre '{basket_name}'.")
    return
```

After:
```python
dup_result = await session.execute(
    select(Basket).where(Basket.name_normalized == normalize_basket_name(basket_name))
)
if dup_result.scalar_one_or_none():
    await update.message.reply_text(
        f"❌ Ya existe una cesta llamada `{basket_name}`. "
        "Los nombres no distinguen mayúsculas ni acentos.",
        parse_mode="Markdown",
    )
    return
```

Note: the dup check removes `Basket.active == True` — uniqueness is global, including inactive baskets.

**Step 3: Populate name_normalized in /crearcesta**

Find the `Basket(...)` constructor in the creation handler (line ~416):
```python
basket = Basket(
    name=basket_name, strategy=strategy, active=True, cash=Decimal("10000"),
    stop_loss_pct=Decimal(str(stop_loss_pct)) if stop_loss_pct else None,
)
```

Add `name_normalized`:
```python
basket = Basket(
    name=basket_name,
    name_normalized=normalize_basket_name(basket_name),
    strategy=strategy, active=True, cash=Decimal("10000"),
    stop_loss_pct=Decimal(str(stop_loss_pct)) if stop_loss_pct else None,
)
```

### baskets.py

**Step 1: Add import** at top of `src/bot/handlers/baskets.py`:

```python
from src.utils.text import normalize_basket_name
```

**Step 2: Replace 2 lookups**

Line ~31 (cmd_cesta):
```python
# Before
select(Basket).where(Basket.name == name, Basket.active == True)
# After
select(Basket).where(Basket.name_normalized == normalize_basket_name(name), Basket.active == True)
```

Line ~116 (cmd_cestas active basket selection):
```python
# Before
select(Basket).where(Basket.name == basket_name, Basket.active == True)
# After
select(Basket).where(Basket.name_normalized == normalize_basket_name(basket_name), Basket.active == True)
```

### orders.py

**Step 1: Add import** at top of `src/bot/handlers/orders.py`:

```python
from src.utils.text import normalize_basket_name
```

**Step 2: Replace 2 lookups**

Line ~95 (basket override):
```python
# Before
select(Basket).where(Basket.name == basket_override, Basket.active == True)
# After
select(Basket).where(Basket.name_normalized == normalize_basket_name(basket_override), Basket.active == True)
```

Line ~159 (active basket):
```python
# Before
select(Basket).where(Basket.name == basket_name, Basket.active == True)
# After
select(Basket).where(Basket.name_normalized == normalize_basket_name(basket_name), Basket.active == True)
```

### backtest.py

**Step 1: Add import** at top of `src/bot/handlers/backtest.py`:

```python
from src.utils.text import normalize_basket_name
```

**Step 2: Replace 1 lookup** (line ~69):

```python
# Before
select(Basket).where(Basket.name == basket_name_arg, Basket.active == True)
# After
select(Basket).where(Basket.name_normalized == normalize_basket_name(basket_name_arg), Basket.active == True)
```

### montecarlo.py

**Step 1: Add import** at top of `src/bot/handlers/montecarlo.py`:

```python
from src.utils.text import normalize_basket_name
```

**Step 2: Replace 1 lookup** (line ~117):

```python
# Before
select(Basket).where(Basket.name == basket_name, Basket.active == True)
# After
select(Basket).where(Basket.name_normalized == normalize_basket_name(basket_name), Basket.active == True)
```

### Run and commit

**Step 3: Run full suite**

```bash
cd /data/scroogebot && .venv/bin/pytest tests/ -q
```

Any tests that build Basket objects directly may fail with "missing name_normalized". Fix those by adding `name_normalized="test_basket"` (or the normalized form) to the Basket constructor in the test setup. Look for `Basket(name=` in test files.

**Step 4: Commit**

```bash
cd /data/scroogebot && git add src/bot/handlers/ tests/
git commit -m "feat(handlers): use name_normalized for all basket lookups"
```

---

## Final verification

```bash
cd /data/scroogebot && .venv/bin/pytest tests/ -v
```

Expected: all tests green.

**Manual test in Telegram (after `sudo systemctl restart scroogebot`):**

```
/cesta lab_avanzado          → should find "Lab_Avanzado"
/cesta LAB_AVANZADO          → same
/compra AAPL 1 @lab avanzado → should find basket if it exists
/crearcesta Canción ma_crossover → creates OK
/crearcesta cancion ma_crossover → ❌ Ya existe una cesta...
```
