---
tags: [odoo, odoo17, module, project_account]
research_depth: medium
---

# Project Account Module — Deep Reference

**Source:** `addons/project_account/models/`

## Overview
Links project tracking to analytic accounting. Enables project profitability analysis by pulling costs and revenues from multiple sources (purchase orders, analytic lines) into a project's `project.project` profitability view. This is the common intersection of `project` and `account` — used as a dependency by `sale_project` and `project_purchase`.

## Architecture

`project_account` extends `project.project` with analytic accounting integration. It does not define its own model; all code lives in an override of `project.project`.

### Module Dependencies
- `project` (base project model)
- `account` (analytic lines, moves)
- Used by: `sale_project`, `project_purchase` (those modules contribute their own sections)

---

## project.project (Extended)

**File:** `project_account/models/project_project.py`

### Profitability Sections Added

| Section ID | Label | Direction |
|------------|-------|-----------|
| `other_purchase_costs` | Vendor Bills | Costs |
| `other_revenues_aal` | Other Revenues | Revenue |
| `other_costs_aal` | Other Costs | Cost |

### `_add_purchase_items()`

Entry point for vendor bill costs. Called from the profitability getter. Queries `account.move.line` for vendor bills (`in_invoice`/`in_refund`) linked to the project's analytic account via `analytic_distribution`.

```python
def _add_purchase_items(self, profitability_items, with_action=True):
    domain = self._get_add_purchase_items_domain()
    # domain filters: move_type in ['in_invoice','in_refund'],
    #                 parent_state in ['draft','posted'],
    #                 price_subtotal > 0,
    #                 not already included in sale orders
    self._get_costs_items_from_purchase(domain, profitability_items, with_action=with_action)
```

### `_get_costs_items_from_purchase()`

Executes a raw SQL query on `account_move_line` using `analytic_distribution` (JSON field storing analytic account IDs and percentages). Handles:
- Multiple analytic accounts on one line (distribution percentages)
- Currency conversion to project currency
- Draft lines: counted as `to_bill`
- Posted lines: counted as `billed`
- `analytic_contribution` = sum of percentages for this project's analytic account / 100

```python
# Example analytic_distribution JSON:
# {"1,2,3": 60.0, "4,5": 40.0}
# Means: 60% goes to analytic accounts 1,2,3; 40% goes to 4,5
analytic_contribution = sum(
    pct for ids, pct in distribution.items()
    if str(self.analytic_account_id.id) in ids.split(',')
) / 100.0
```

### `_get_domain_aal_with_no_move_line()`

Returns domain for `account.analytic.line` records with no linked `move_line_id` (pure AAL entries, excluding those already flowing through `stock` or `mrp`):

```python
# Excludes: lines linked to a move_line, and manufacturing-order lines
[('auto_account_id', '=', self.analytic_account_id.id),
 ('move_line_id', '=', False),
 ('category', '!=', 'manufacturing_order')]
```

### `_get_items_from_aal()`

Searches pure analytic lines (no purchase order / vendor bill origin), aggregates by currency, and returns as `other_revenues_aal` (positive amounts) and `other_costs_aal` (negative amounts). All amounts go to `invoiced`/`billed` columns since there is no to-be-invoiced counterpart.

### `_get_profitability_labels()`

Extends parent labels with:
```python
'other_purchase_costs': _('Vendor Bills'),
'other_revenues_aal': _('Other Revenues'),
'other_costs_aal': _('Other Costs'),
```

### `_get_profitability_sequence_per_invoice_type()`

Extends parent sequences with:
```python
'other_purchase_costs': 11,
'other_revenues_aal': 14,
'other_costs_aal': 15,
```

### `action_profitability_items()`

Drill-down action from profitability section. Routes to different actions based on section:

| Section | Action |
|---------|--------|
| `other_revenues_aal` / `other_costs_aal` | `analytic.account_analytic_line_action_entries` (with pivot/graph views) |
| `other_purchase_costs` | `account.action_move_in_invoice_type` (vendor bills) |

The action respects single-record context: if `res_id` is provided, opens the form view directly; otherwise opens list with configured pivot/graph views.

---

## Profitability Data Flow

```
project_account
  ├─ other_purchase_costs    ← account.move.line (vendor bills with analytic_distribution)
  ├─ other_revenues_aal      ← account.analytic.line (positive, no move_line_id)
  └─ other_costs_aal          ← account.analytic.line (negative, no move_line_id)

sale_project (also depends on project_account)
  ├─ billable_milestones      ← sale.order.line (milestones)
  ├─ billable_tasks           ← sale.order.line (delivered via timesheets)
  └─ other_revenues           ← sale.order.line (manual, non-billable)

project_purchase (also depends on project_account)
  └─ purchase_costs           ← purchase.order.line (billable purchase)
```

---

## See Also
- [Modules/project](Modules/project.md) — project base model
- [Modules/analytic](Modules/analytic.md) — analytic accounting foundation
- [Modules/sale_project](Modules/sale_project.md) — sale order / project profitability
- [Modules/project_purchase](Modules/project_purchase.md) — purchase order costs
- [Modules/sale_timesheet](Modules/sale_timesheet.md) — time tracking costs
