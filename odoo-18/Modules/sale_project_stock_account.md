# sale_project_stock_account — Sale Project Stock Account

**Tags:** #odoo #odoo18 #sale #project #stock #account #anglo-saxon
**Odoo Version:** 18.0
**Module Category:** Sale + Project + Stock + Account Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_project_stock_account` extends `sale_project_stock` with Anglo-Saxon accounting filtering. It prevents expense-policy products (consumables billed as expenses rather than inventory) from appearing in COGS calculations, ensuring correct margin computation for project-based service orders that include consumable products.

**Technical Name:** `sale_project_stock_account`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_project_stock_account/`
**Depends:** `sale_project_stock`, `stock_account`
**Inherits From:** `stock.move`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/stock_move.py` | `stock.move` | Filters out expense-policy products from COGS |

---

## Models Reference

### `stock.move` (models/stock_move.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `_get_valid_moves_domain()` | Adds domain filter: excludes moves where `product_id.expense_policy` is set (expense-policy products not tracked as inventory for COGS) |

#### Critical Override Logic

```python
def _get_valid_moves_domain(self):
    domain = super()._get_valid_moves_domain()
    domain.append(('product_id.expense_policy', '=', False))  # exclude consumable billed products
    return domain
```

This filter is used by the Anglo-Saxon COGS reconciliation logic in `stock_account`. Products with `expense_policy` set (typically `'cost'` or `'sales_price'`) are billed as expenses rather than tracked as inventory — they should not generate COGS entries.

---

## Security File

No security file.

---

## Data Files

No data file.

---

## Critical Behaviors

1. **Expense Policy Exclusion**: Products with `expense_policy` (e.g., `'cost'`: billed at cost as expense) are excluded from the `_get_valid_moves_domain()` domain. This prevents them from participating in COGS computation.

2. **Chain with `sale_project_stock`**: This module extends `sale_project_stock` which already handles project→picking linkage and reinvoice logic. This module adds the accounting filter on top.

3. **Used by COGS Reconciliation**: The domain is consumed by `account.move._stock_account_anglo_saxon_reconcile_valuation()` to filter which stock moves to reconcile against invoice interim accounts.

---

## v17→v18 Changes

No significant changes from v17 to v18 identified.

---

## Notes

- Thin module (1 file, ~1 method override) that completes the project→stock→account chain
- The `expense_policy` field on `product.template` controls whether a product is tracked as inventory or expensed
- This module is part of the "project as contract" workflow where service companies bill consumables alongside professional services
