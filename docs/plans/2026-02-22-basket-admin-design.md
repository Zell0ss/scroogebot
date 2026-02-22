# Basket Admin Commands — Design

**Date:** 2026-02-22
**Status:** Approved

## Overview

Three new commands to manage baskets from Telegram, complementing the existing seed-based setup.

- `/estrategia <cesta> [nueva_estrategia]` — view or change basket strategy
- `/nuevacesta <nombre> <estrategia>` — create a new basket
- `/eliminarcesta <nombre>` — soft-delete a basket (only if no open positions)

Baskets seeded from `config.yaml` coexist with bot-created ones. The seed creates "official" baskets; users can create additional ones via bot.

---

## Commands

### `/estrategia <cesta> [nueva_estrategia]`

**Without second arg:** shows current strategy + list of available strategies.
**With second arg:** changes the strategy.

Access: OWNER of that basket only (read is open to any registered user).
Validation: `nueva_estrategia in STRATEGY_MAP` — same keys as AlertEngine.

```
/estrategia MiCesta
→ 📊 MiCesta usa estrategia: ma_crossover
   Disponibles: stop_loss, ma_crossover, rsi, bollinger, safe_haven

/estrategia MiCesta rsi
→ ✅ Estrategia de MiCesta cambiada a rsi
```

---

### `/nuevacesta <nombre> <estrategia>`

Any registered user can create a basket. The creator becomes OWNER automatically.

Steps:
1. Validate strategy is in STRATEGY_MAP
2. Check no basket with same name exists (active or inactive) → error if duplicate
3. Create `Basket(name, strategy, active=True)` + `BasketMember(user_id=caller.id, role="OWNER")` in a single transaction

```
/nuevacesta TechGrowth rsi
→ ✅ Cesta "TechGrowth" creada con estrategia rsi. Eres OWNER.
```

---

### `/eliminarcesta <nombre>`

OWNER of that basket only. Soft-delete: sets `basket.active = False`.

Steps:
1. Find basket by name (error if not found)
2. Check caller is OWNER of that basket
3. Check no open positions (`Position.quantity > 0`) — reject with message if any exist
4. `basket.active = False` + commit

AlertEngine already filters `Basket.active == True`, so the basket stops being scanned immediately.

```
/eliminarcesta TechGrowth
→ ✅ Cesta "TechGrowth" desactivada.

/eliminarcesta MiCesta  (con posiciones abiertas)
→ ❌ No se puede eliminar: MiCesta tiene posiciones abiertas (AAPL, SAN.MC).
```

---

## Access Control

Uniform pattern (same as `/adduser`):

```python
caller_user = await session.execute(select(User).where(User.tg_id == tg_id))
membership = await session.execute(
    select(BasketMember).where(
        BasketMember.user_id == caller.id,
        BasketMember.basket_id == basket.id,
        BasketMember.role == "OWNER",
    )
)
```

---

## Files Changed

- `src/bot/handlers/admin.py` — 3 new handlers + registration in `get_handlers()`
- `tests/test_basket_admin.py` — new test file

No DB migrations needed — all fields (`Basket.strategy`, `Basket.active`, `BasketMember.role`) already exist.

---

## Tests

| Test | What it checks |
|------|---------------|
| `test_estrategia_read` | Shows current strategy when no second arg |
| `test_estrategia_change_ok` | OWNER can change strategy |
| `test_estrategia_invalid` | Rejects unknown strategy name |
| `test_estrategia_not_owner` | MEMBER cannot change |
| `test_estrategia_basket_not_found` | Error on unknown basket |
| `test_nuevacesta_ok` | Creates basket + OWNER membership |
| `test_nuevacesta_duplicate` | Rejects duplicate name |
| `test_nuevacesta_invalid_strategy` | Rejects unknown strategy |
| `test_eliminarcesta_ok` | Soft-deletes empty basket |
| `test_eliminarcesta_with_positions` | Rejects if open positions exist |
| `test_eliminarcesta_not_owner` | MEMBER cannot delete |
