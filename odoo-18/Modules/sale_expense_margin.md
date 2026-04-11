# sale_expense_margin — Sale Expense Margin

**Tags:** #odoo #odoo18 #sale #expense #margin #purchase-price
**Odoo Version:** 18.0
**Module Category:** Sale + HR Expense / Margin
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_expense_margin` extends `sale_expense` to compute purchase price for reinvoiced expense lines using the expense's actual cost value. This ensures that expenses reinvoiced through sale orders have accurate cost basis for margin calculation.

**Technical Name:** `sale_expense_margin`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_expense_margin/`
**Depends:** `sale_expense`
**Inherits From:** `sale.order.line`, `account.move.line`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/sale_order_line.py` | `sale.order.line` | Pulls purchase_price from linked expense |
| `models/account_move_line.py` | `account.move.line` | Attaches expense_id to SOL on reinvoice |

---

## Models Reference

### `sale.order.line` (models/sale_order_line.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `expense_id` | Many2one | Link to `hr.expense` (the source expense) |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_purchase_price()` | For reinvoiced SOLs with `expense_id`: sets `purchase_price = expense_id.amount` (unit cost from expense) |

---

### `account.move.line` (models/account_move_line.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `_sale_prepare_sale_line_values()` | Adds `expense_id` to SOL vals when creating from expense |

---

## Critical Behaviors

1. **Expense as Purchase Price**: The expense's `amount` (total expense value) divided by qty becomes the purchase price. This captures the actual cost incurred.

2. **Margin Accuracy**: Without this module, reinvoiced expenses would use the product's standard_price (often zero or arbitrary) as purchase_price. This module ensures margin = sale price - actual expense cost.

3. **Linkage via `expense_id`**: The SOL stores the `expense_id` for traceability and to allow the override to identify which lines to process.

---

## v17→v18 Changes

No significant changes from v17 to v18 identified.

---

## Notes

- Thin module (~2 method overrides) that completes the expense→reinvoice margin chain
- Works in conjunction with `sale_stock_margin` and `sale_timesheet_margin` for non-expense lines
- Together, these three margin modules provide accurate cost basis for all three delivery types: stock, timesheet, and expense
