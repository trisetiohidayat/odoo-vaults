---
tags:
  - #odoo19
  - #modules
  - #sale
  - #stock
  - #product
---

# sale_stock_product_expiry

## Overview

| Property | Value |
|----------|-------|
| Module | `sale_stock_product_expiry` |
| Path | `odoo/addons/sale_stock_product_expiry/` |
| Category | Sales / Stock / Product |
| Dependencies | `sale_stock`, `stock` |
| Key Concept | Show expired-stock availability in sale order lines |

---

## Purpose

Integrates **product expiration tracking** (stock lot/serial number expiry dates) into the **sale order line stock check** flow. When a sale order line is being confirmed, Odoo checks available stock quantities. This module ensures that for products tracked by expiration date (`use_expiration_date = True`), the available quantity shown to the salesperson reflects only non-expired stock -- not quantities reserved in expired lots.

Without this module, sale orders could promise delivery of expired goods.

---

## Architecture

### Inheritance Chain

```
sale.order.line                (sale module)
    └── SaleOrderLine
            _inherit = 'sale.order.line'
            └── sale_stock_product_expiry
```

### Model Extended

**File:** `models/sale_order_line.py`

#### `use_expiration_date`

```python
use_expiration_date = fields.Boolean(
    related='product_id.use_expiration_date'
)
```

A **related** boolean field that mirrors the product's expiration tracking setting. Used to conditionally trigger the custom stock read logic.

---

#### `_read_qties(date, wh)`

Overrides the sale stock module's stock availability read to exclude expired quantities.

```python
def _read_qties(self, date, wh):
    res = super()._read_qties(date, wh)
    if any(self.mapped('use_expiration_date')):
        for res_record, read_record in zip(
            res,
            self.mapped('product_id').with_context(warehouse_id=wh).read(
                ['free_qty']
            )
        ):
            res_record['free_qty'] = read_record['free_qty']
    return res
```

**What it does:**

| Step | Action |
|------|--------|
| 1 | Calls parent `_read_qties()` which returns standard stock quantities |
| 2 | Checks if any lines in the result use expiration tracking |
| 3 | For lines with `use_expiration_date = True`: re-read `free_qty` from the product with the default context |
| 4 | The product's `free_qty` (via `stock.quant`) only counts **non-expired** quantities |
| 5 | Overwrites the standard quantity with the non-expired quantity |

---

## How Expiration Tracking Works in Odoo

Products configured with `use_expiration_date = True` track stock in lots/serials, each with an `expiration_date`. The `stock.quant` model filters out expired lots when computing `free_qty`:

```
Product "Medicine A" (use_expiration_date=True)
        │
        ├── Lot L1: qty=100, expiration_date=2026-12-31  → counted in free_qty
        ├── Lot L2: qty=50,  expiration_date=2025-01-01   → expired, NOT counted
        └── Lot L3: qty=25,  expiration_date=2026-06-15  → counted in free_qty

        free_qty (standard) = 175
        free_qty (non-expired) = 125
```

The standard `sale_stock` `_read_qties()` reads from the quants without expiration filtering. This module replaces the quantity for expiration-tracked products with the non-expired count.

---

## Data Flow

```
Salesperson adds product to sale order line
        │
        ▼
  sale_order_line._read_qties() called
  (during availability check / confirmation)
        │
        ▼
  Parent _read_qties() returns standard free_qty
        │
        ▼
  use_expiration_date = True?
        │
        ├── No → return standard quantity
        │
        └── Yes → re-read from product_id.free_qty
                  (which filters out expired lots)
                  │
                  ▼
            free_qty = only non-expired stock
```

---

## Key Code Pattern

```python
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    use_expiration_date = fields.Boolean(related='product_id.use_expiration_date')

    def _read_qties(self, date, wh):
        res = super()._read_qties(date, wh)
        if any(self.mapped('use_expiration_date')):
            for res_record, read_record in zip(
                res,
                self.mapped('product_id').with_context(warehouse_id=wh).read(['free_qty'])
            ):
                # Replace with non-expired quantity
                res_record['free_qty'] = read_record['free_qty']
        return res
```

---

## Related Modules

| Module | Role |
|--------|------|
| `sale` | Sale order line model |
| `sale_stock` | Stock availability checks on sale lines |
| `stock` | Stock quants with expiration_date tracking |
| `product` | Product with `use_expiration_date` field |

---

## Expiration Date Fields (stock module reference)

Products with `use_expiration_date = True` have these date fields on lots:

| Field | Purpose |
|-------|---------|
| `expiration_date` | Primary expiry date |
| `use_expiration_date` | Enable tracking on product |
| `expiration_reminder_1` | Days before expiry to alert |
| `removal_date` | Date when lot should be removed |
| `alert_date` | Date for expiration alert |

These dates are set at lot/serial number creation and drive the `free_qty` computation in `stock.quant`.

---

## Related Documentation

- [[Modules/Stock]] -- Stock quants, lots, and expiration tracking
- [[Modules/Sale]] -- Sale order and stock integration
- [[Modules/Product]] -- Product expiration settings
