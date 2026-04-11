---
Module: sale_gelato_stock
Version: 18.0
Type: addon
Tags: #sale #gelato #stock
---

# sale_gelato_stock — Gelato/Stock Bridge

**Summary:** Technical bridge between `sale_gelato` and `sale_stock`.

**Depends:** `sale_gelato`, `sale_stock`
**Auto-install:** True
**License:** LGPL-3
**Source:** `~/odoo/odoo18/odoo/addons/sale_gelato_stock/`

## Overview

`sale_gelato_stock` is a thin auto-install bridge that combines `sale_gelato` (print-on-demand integration) with `sale_stock` (sales order warehouse/picking logic). It prevents stock moves from being created for Gelato print-on-demand products while maintaining the rest of the `sale_stock` behavior.

---

## Models

### `sale.order.line` — `SaleOrderLine`

**File:** `models/sale_order_line.py`

```python
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _action_launch_stock_rule(self, **kwargs):
        gelato_lines = self.filtered(lambda l: l.product_id.gelato_product_uid)
        super(SaleOrderLine, self - gelato_lines)._action_launch_stock_rule(**kwargs)
```

**Key Methods:**

- `_action_launch_stock_rule(**kwargs)` (line 9) — Filters out Gelato product lines (`gelato_product_uid` is set) before calling the parent method. This prevents Gelato products from triggering stock picking creation through `sale_stock` rules, since Gelato manages its own fulfillment.

---

## What It Does

| Behavior | Without `sale_gelato_stock` | With `sale_gelato_stock` |
|---|---|---|
| Gelato product lines | Would create stock moves/pickings | No picking created |
| Non-Gelato product lines | Normal stock flow | Normal stock flow |

This is a pure technical bridge — no new fields, views, or data files.
