---
Module: project_stock_account
Version: 18.0.0
Type: addon
Tags: #odoo18 #project_stock_account #project #stock #analytic
---

## Overview

**Module:** `project_stock_account`
**Depends:** `stock_account`, `project_stock` (auto_install: True)
**Location:** `~/odoo/odoo18/odoo/addons/project_stock_account/`
**License:** LGPL-3
**Purpose:** Generates analytic account entries for stock pickings linked to projects. Adds a "Materials" (other_costs) section to the project profitability panel. Validates mandatory analytic plans before posting picking entries. Extends `account.analytic.applicability` with `stock_picking` business domain.

---

## Models

### `stock.picking.type` (models/stock_picking_type.py, 1–9)

Inherits: `stock.picking.type`

| Field | Type | Line | Description |
|---|---|---|---|
| `analytic_costs` | Boolean | 9 | If set, validating pickings of this type generates analytic entries for the selected project. Also enables product re-invoicing to the customer. |

### `stock.move` (models/stock_move.py, 1–48)

Inherits: `stock.move`

| Method | Line | Description |
|---|---|---|
| `_get_analytic_distribution()` | 12 | Returns `picking_id.project_id._get_analytic_distribution()` if `picking_type_id.analytic_costs` is set and picking has a project; falls back to `super()`. |
| `_prepare_analytic_line_values(account_field_values, amount, unit_amount)` | 18 | Sets `name = picking_id.name` and `category = 'picking_entry'` for picking-linked analytic lines. Inherits other values from parent. |
| `_get_valid_moves_domain()` | 25 | Returns `['&', ('picking_id.project_id', '!=', False), ('picking_type_id.analytic_costs', '!=', False)]`. Defines moves eligible for analytic entry generation. |
| `_account_analytic_entry_move()` | 28 | Filters to valid picking moves (`OR([[('picking_id', '=', False)], domain])`) and calls super on them. Excludes picking moves from standard move line analytic handling. |
| `_prepare_analytic_lines()` | 34 | Validates mandatory analytic plans on the picking's project before generating AALs. Raises `ValidationError` listing missing plan names if any required plans are not set on the project. |

**ValidationError thrown by `_prepare_analytic_lines`:** `"'<plan_names>' analytic plan(s) required on the project '<project_name>' linked to the stock picking."`

### `project.project` (models/project_project.py, 1–65)

Inherits: `project.project`

| Method | Line | Description |
|---|---|---|
| `_get_profitability_labels()` | 11 | Adds `'other_costs': _lt('Materials')` to profitability section labels. |
| `_get_profitability_sequence_per_invoice_type()` | 17 | Assigns sequence `12` to `other_costs`. |
| `_get_profitability_items(with_action=True)` | 23 | Calls `_get_items_from_aal_picking`. Appends `other_costs` to `costs.data` and updates `costs.total.billed`. |
| `_get_items_from_aal_picking(with_action=True)` | 31 | Reads `account.analytic.line` with `category='picking_entry'` and `auto_account_id` in project AA, excluding move_line-linked AALs (`_get_domain_aal_with_no_move_line`). Aggregates amounts by currency, converts to project currency. Returns `{'id': 'other_costs', 'sequence': 12, 'billed': total_costs, 'to_bill': 0.0, 'action': ...}` for `account.group_account_readonly` users. |

#### Profitability — Materials Section
| Property | Value |
|---|---|
| Section ID | `other_costs` |
| Sequence | `12` |
| Type | `costs` (billed only) |
| Source | `account.analytic.line` (category=`picking_entry`, no move_line) |
| Access | `account.group_account_readonly` for action link |

### `account.analytic.line` (models/account_analytic_line.py, 1–9)

Inherits: `account.analytic.line`

| Field | Line | Description |
|---|---|---|
| `category` selection_add | 9 | Adds `('picking_entry', 'Inventory Transfer')`. Distinguishes stock transfer costs from `manufacturing_order` category. |

### `account.analytic.applicability` (models/analytic_applicability.py, 1–15)

Inherits: `account.analytic.applicability`

| Field | Line | Description |
|---|---|---|
| `business_domain` selection_add | 10 | Adds `('stock_picking', 'Stock Picking')`. Enables applicability rules for stock picking business domain. `ondelete='cascade'`. |

---

## Views

**XML:** `views/stock_picking_type_views.xml`

---

## Critical Notes

- Analytic entries are generated only for pickings where: (a) the picking has a `project_id`, AND (b) the picking type has `analytic_costs=True`.
- `category='picking_entry'` distinguishes stock transfer costs from `manufacturing_order` category used by `project_mrp_account`.
- Mandatory plan validation raises `ValidationError` at picking validation time if the project lacks required plans.
- `account.analytic.applicability` with `business_domain='stock_picking'` allows rules-based analytic distribution per picking.
- v17→v18: No breaking changes.