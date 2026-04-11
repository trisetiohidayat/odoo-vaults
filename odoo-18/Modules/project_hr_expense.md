---
Module: project_hr_expense
Version: 18.0.0
Type: addon
Tags: #odoo18 #project_hr_expense #project #expense
---

## Overview

**Module:** `project_hr_expense`
**Depends:** `project_account`, `hr_expense` (auto_install: True)
**Location:** `~/odoo/odoo18/odoo/addons/project_hr_expense/`
**Purpose:** Links expense reports to projects for profitability tracking. Inherits analytic distribution from project context during expense creation. Surfaces posted/done expense sheets as costs in the project profitability panel.

---

## Models

### `hr.expense` (models/hr_expense.py, 1–25)

Inherits: `hr.expense` — pre-populates analytic distribution from project context.

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_compute_analytic_distribution()` | override | 7 | If `project_id` in context, uses `project._get_analytic_distribution()` instead of default computation. Only applies if `analytic_distribution` is empty. |
| `create(vals_list)` | `@api.model_create_multi` | 16 | On creation with `project_id` in context, pre-fills `analytic_distribution` from the project's analytic distribution if not already set. |

### `project.project` (models/project.py, 1–126)

Inherits: `project.project` — adds expense section to profitability report.

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_get_expense_action(domain=None, expense_ids=None)` | private | 16 | Builds `ir.actions.act_window` for expense list filtered by domain/IDs. Sets `context: {project_id: self.id}`. Single expense → form view; multiple → list/kanban/graph/pivot. |
| `_get_add_purchase_items_domain()` | override | 31 | Adds `('expense_id', '=', False)` to exclude vendor bill lines that originated from an expense. Prevents double-counting with purchase orders. |
| `action_profitability_items(section_name, domain=None, res_id=False)` | override | 37 | Delegates `section_name='expenses'` to `_get_expense_action`. Passes through to parent for other sections. |
| `action_open_project_expenses()` | action | 42 | Smart-button action. Filters `hr.expense` by `analytic_distribution in self.account_id.ids`. |
| `_get_profitability_labels()` | override | 50 | Adds `'expenses': self.env._('Expenses')` to the profitability section labels. |
| `_get_profitability_sequence_per_invoice_type()` | override | 55 | Assigns sequence `13` to the `expenses` section. |
| `_get_already_included_profitability_invoice_line_ids()` | override | 60 | Excludes account move lines linked to `expense_sheet_id` from parent billing logic. Prevents double-counting expenses with vendor bills. |
| `_get_expenses_profitability_items(with_action=True)` | private | 70 | Reads `hr.expense` grouped by currency for `sheet_id.state in ('post', 'done')` linked to project's AA. Converts to project currency. Only `group_hr_expense_team_approver` users get clickable expense IDs. Returns `{'costs': {'id': 'expenses', 'billed': -amount_billed, 'to_bill': 0.0, 'action': ...}}`. |
| `_get_profitability_aal_domain()` | override | 108 | Excludes analytic lines whose `move_line_id` links to an expense (`move_line_id.expense_id = False`). Filters out expense-driven AAL entries. |
| `_get_profitability_items(with_action=True)` | override | 114 | Calls parent method, merges `_get_expenses_profitability_items` result into `costs.data`. Updates `costs.total` `{billed, to_bill}`. |

#### Profitability — Expenses Section
| Property | Value |
|---|---|
| Section ID | `expenses` |
| Sequence | `13` |
| Type | `costs` only (no to_bill) |
| Source model | `hr.expense` |
| Filter | `sheet_id.state in ('post', 'done')` + analytic distribution match |
| Access check | `group_hr_expense_team_approver` for action links |
| Billed formula | `-sum(untaxed_amount_currency)` per currency, converted to project currency |

---

## Views

**XML:** `views/project_project_views.xml`

`ir.embedded.actions` record — id `project_embedded_action_hr_expenses`. Adds "Expenses" button to project dashboard. Visible to `hr_expense.group_hr_expense_user`. Calls `action_open_project_expenses` via `python_method`. Sequence: `77`.

---

## Security / Data

No `ir.model.access.csv` (bridge module).
**Demo data:** `data/project_hr_expense_demo.xml`
**License:** LGPL-3

---

## Critical Notes

- **v17→v18:** No breaking changes.
- Expenses are tracked as **costs only** (billed) in project profitability — no "to_bill" component.
- Expenses are excluded from the AAL domain to prevent double-counting: the expense sheet posts its own journal entries.
- Only users with `group_hr_expense_team_approver` see clickable expense links in the profitability panel.
- `auto_install=True` — installs automatically when both `project_account` and `hr_expense` are present.