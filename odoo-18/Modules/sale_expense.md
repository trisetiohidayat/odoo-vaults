# sale_expense — Sale Expense

**Tags:** #odoo #odoo18 #sale #expense #reinvoice #hr #analytic
**Odoo Version:** 18.0
**Module Category:** Sale + HR Expense Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_expense` enables expense reinvoicing through sale orders. Employees submit expenses (with optional sale order assignment), managers approve them, and upon posting the expense sheet, the related analytic entries are converted into sale order lines for the customer's project/contract. This is the core module for "bill to customer" expense workflows.

**Technical Name:** `sale_expense`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_expense/`
**Depends:** `sale`, `hr_expense`, `analytic`
**Inherits From:** `hr.expense`, `hr.expense.split`, `sale.order`, `hr.expense.sheet`, `account.move.line`, `product.template`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/hr_expense.py` | `hr.expense` | SO link compute, reinvoiceability check, onchange |
| `models/hr_expense_split.py` | `hr.expense.split` | Same SO/reinvoice fields as parent |
| `models/sale_order.py` | `sale.order` | Expense O2M, expense count |
| `models/hr_expense_sheet.py` | `hr.expense.sheet` | SO count, SO line extraction from SQL, reset/reopen actions |
| `models/account_move_line.py` | `account.move.line` | Reinvoice logic from analytic lines |
| `models/product_template.py` | `product.template` | Expense policy tooltip |

---

## Models Reference

### `hr.expense` (models/hr_expense.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `sale_order_id` | Many2one | Link to sale order (compute+store, index btree_not_null) |
| `can_be_reinvoiced` | Boolean | Compute: checks expense_policy='sale' and has SO |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_can_be_reinvoiced()` | Returns True if product has expense_policy='sale' |
| `_compute_sale_order_id()` | Reads `analytic_account_id.sale_order_id` to find linked SO |
| `_onchange_sale_order_id()` | Loads SO partner into expense for consistency |
| `_get_split_values()` | Adds `sale_order_id` to expense split vals |

---

### `hr.expense.sheet` (models/hr_expense_sheet.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `sale_order_count` | Integer | Count of linked SOs |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_sale_order_count()` | Counts distinct SOs |
| `_get_sale_order_lines()` | Complex SQL: finds SOLs to create from expense analytic lines |
| `_sale_expense_reset_sol_quantities()` | Resets SOL quantities for reopened sheets |
| `action_reset_expense_sheets()` | Resets quantities, unlinks partial reinvoices |
| `action_open_sale_orders()` | Returns action for linked SOs |
| `_do_create_moves()` | Overrides to auto-create analytic account if missing |

#### Complex SQL in `_get_sale_order_lines()`

The method uses `psycopg2.execute_values` for high-performance bulk line creation:
- Joins `account_analytic_line` with `sale_order_line` on `so_line` (existing lines)
- Filters by `account_id` from the expense sheet's expense lines
- Sums amounts per SOL and product
- Returns vals dicts ready for `create()`

---

### `account.move.line` (models/account_move_line.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `_sale_can_be_reinvoice()` | Returns True only if `expense_policy='sale'` AND `sale_order_id` set |
| `_get_so_mapping_from_expense()` | Maps analytic lines to existing SOLs by product/amount |
| `_sale_determine_order()` | Finds the SO to reinvoice to |
| `_sale_prepare_sale_line_values()` | Adds expense qty (not amount!) to SOL vals |
| `_sale_create_reinvoice_sale_line()` | Creates SOL from expense, with `force_split_lines` option |

#### Reinvoice Logic

When an expense sheet is posted:
1. Analytic lines with expense entries are found
2. `_sale_determine_order()` resolves the target SO
3. `_get_so_mapping_from_expense()` maps to existing SOLs or prepares new ones
4. `_sale_prepare_sale_line_values()` builds SOL vals with `expense_id` link
5. `force_split_lines=True` forces a new SOL even if one exists (one SOL per expense)

---

## Security File

No standalone security file (`security/` directory does not exist).

---

## Data Files

| File | Content |
|------|---------|
| `data/sale_expense_data.xml` | Product data: default expense product with `expense_policy='sale'` |

---

## Critical Behaviors

1. **Expense→SO Link via Analytic Account**: The `sale_order_id` on `hr.expense` is not directly stored — it is computed from the expense's `analytic_account_id.sale_order_id`. Assigning an analytic account linked to a project/SOW to an expense automatically connects the expense to the correct SO.

2. **Qty-Based Reinvoice**: `_sale_prepare_sale_line_values()` adds the expense qty to SOL (not the amount). The amount is invoiced through the normal SO invoicing flow — expense reinvoicing is about recording the work/cost item, not the price.

3. **Force Split Lines**: `_sale_create_reinvoice_sale_line(force_split_lines=True)` always creates a new SOL per expense line, even if a SOL for the same product already exists. This ensures each expense maps to its own line for tracking.

4. **Sheet Reset on Unpost**: When an expense sheet is reset to draft (`action_reset_expense_sheets()`), `_sale_expense_reset_sol_quantities()` zeroes out the SOL quantities that were incremented from this sheet.

5. **Auto Analytic Account**: `_do_create_moves()` checks for missing analytic accounts on the expense sheet and auto-creates one if needed (useful when expenses are submitted without a project).

---

## v17→v18 Changes

- `_sale_expense_reset_sol_quantities()` added for sheet reset/reopen handling
- `action_reset_expense_sheets()` method added
- `_get_split_values()` now propagates `sale_order_id` to expense splits
- Complex SQL query in `_get_sale_order_lines()` optimized with `execute_values`

---

## Notes

- `sale_expense` is the core of the billable expenses workflow
- The `expense_policy='sale'` on `product.template` is the master switch for whether a product can be expensed and reinvoiced
- The SO receives SOLs with `expense_id` pointing to the source expense for full traceability
- `sale_expense_margin` extends this with purchase price computation from the expense
