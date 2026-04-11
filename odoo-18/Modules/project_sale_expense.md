---
Module: project_sale_expense
Version: 18.0.0
Type: addon
Tags: #odoo18 #project_sale_expense #project #sale #expense
---

## Overview

**Module:** `project_sale_expense`
**Depends:** `project_sale`, `hr_expense`
**Location:** `~/odoo/odoo18/odoo/addons/project_sale_expense/`
**Purpose:** Enables expense re-invoicing to customers via sale orders. Expenses linked to a SO/project generate both costs (expense) and revenues (re-invoiced). Also propagates analytic distribution from project's SO.

## Models

### `hr.expense` (project_sale_expense/models/hr_expense.py)

Inherits: `hr.expense`

| Method | Decorator | Description |
|---|---|---|
| `_compute_analytic_distribution()` | override | If no project_id in context and expense has `sale_order_id`: uses `sale_order_id.project_id._get_analytic_distribution()` |

### `project.project` (project_sale_expense/models/project_project.py)

Inherits: `project.project`

| Method | Decorator | Description |
|---|---|---|
| `_get_expenses_profitability_items(with_action=True)` | override | Reads expenses with `sheet_id.state in ['post', 'done']` linked to project's AA. Groups by `sale_order_id, product_id, currency_id`. Matches against sale order line `is_expense=True` states to compute revenues (to_invoice/invoiced). Distinguishes costs (from expense sheet) vs. revenues (from reinvoiced SOL). |
| `_get_already_included_profitability_invoice_line_ids()` | override | Excludes invoice lines from sale orders that have posted expense sheets (to avoid double-counting) |

### `account.move.line` (project_sale_expense/models/account_move_line.py)

Inherits: `account.move.line`

| Method | Decorator | Description |
|---|---|---|
| `_sale_determine_order()` | override | Merges `_get_so_mapping_from_project()` and `_get_so_mapping_from_expense()` to determine which SO to link vendor bill lines to; expense mapping takes precedence over project mapping |

### `hr.expense.sheet` (project_sale_expense/models/hr_expense_sheet.py)

Inherits: `hr.expense.sheet`

| Method | Decorator | Description |
|---|---|---|
| `_do_create_moves()` | override | Before expense move creation: if expense has SO with project and no explicit AA: creates project analytic account and sets distribution from project. |

## Security / Data

No `ir.model.access.csv`. No data XML files.

## Critical Notes

- v17→v18: No breaking changes.
- The profitability report shows: costs (from expense sheet post/done) and revenues (from reinvoiced sale order lines with `is_expense=True`).
- `_do_create_moves` ensures analytic distribution is always set from the project when expense is linked to a sale order.
- `account.move.line._sale_determine_order` uses expense mapping first, then project mapping — expense mapping wins for conflicts.