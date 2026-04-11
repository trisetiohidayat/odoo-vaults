# Odoo 18 - project_account Module

## Overview

Links project profitability to accounting. Extends `project.project` with vendor bill tracking and analytic line integration for profitability calculations. This is the common module referenced by `sale_project` and `project_purchase`.

## Source Path

`~/odoo/odoo18/odoo/addons/project_account/`

## Key Model

### project.project (extended)

Extends `project.project` with accounting-based profitability sections.

**Profitability Sections Added:**

1. **`other_purchase_costs`** (Vendor Bills)
   - Displayed as "Vendor Bills" in the profitability view.
   - Section sequence: `11`
   - Computed via `_get_costs_items_from_purchase()`.

2. **`other_revenues_aal`** (Other Revenues)
   - From `account.analytic.line` records with no `move_line_id` and category not in `manufacturing_order` or `picking_entry`.
   - Section sequence: `14`
   - All amounts go to `invoiced` (billed) column.

3. **`other_costs_aal`** (Other Costs)
   - Same source as `other_revenues_aal` — negative `amount` on analytic lines.
   - Section sequence: `15`
   - All amounts go to `billed` column.

**Key Methods:**

### `_add_purchase_items(profitability_items, with_action=True)`

Adds vendor bills section to profitability data. Calls `_get_costs_items_from_purchase()` with domain from `_get_add_purchase_items_domain()`.

- Checks `account.group_account_invoice` or `account.group_account_readonly` before adding actions.
- Appends to `profitability_items['costs']['data']`.

### `_get_add_purchase_items_domain()`

Returns domain for vendor bill search:
```python
[
    ('move_type', 'in', ['in_invoice', 'in_refund']),
    ('parent_state', 'in', ['draft', 'posted']),
    ('price_subtotal', '>', 0),
    ('id', 'not in', purchase_order_line_invoice_line_ids),
]
```
Excludes bills already linked to purchase order lines (those are tracked via `project_purchase` instead).

### `_get_costs_items_from_purchase(domain, profitability_items, with_action=True)`

Searches `account.move.line` with `analytic_distribution` matching project's analytic account.

1. Reads with `sudo()`: `balance`, `parent_state`, `company_currency_id`, `analytic_distribution`, `move_id`, `date`.
2. Converts to project currency per move line using `company_currency_id._convert()`.
3. Computes `analytic_contribution` — percentage of analytic distribution belonging to this project (handles multi-account distributions).
4. Splits by `parent_state`: `draft` → `amount_to_invoice`; `posted` → `amount_invoiced`.
5. If both are zero (bill cancelled = vendor credit), section is not shown.
6. Adds `action` for navigation to vendor bills if `with_action=True` and user has access.
7. Updates `costs.total.billed` and `costs.total.to_bill`.

### `action_profitability_items(section_name, domain=None, res_id=False)`

Routes to the correct action based on section type:
- `other_revenues_aal` / `other_costs_aal` / `other_costs`:
  - Action: `analytic.account_analytic_line_action_entries`
  - Context: `{'group_by_date': True}`
  - If `res_id`: opens form view.
  - Else: replaces views with pivot + graph views specific to project.
- `other_purchase_costs`:
  - Action: `account.action_move_in_invoice_type`
  - Domain: `[('id', 'in', record_ids)]`
  - If `res_id`: opens form view.

### `_get_domain_aal_with_no_move_line()`

Returns `[('account_id', '=', self.account_id.id), ('move_line_id', '=', False)]`.
Note: Does NOT filter by `project_id` — allows for analytic lines not linked to a specific project (overhead costs).

### `_get_items_from_aal(with_action=True)`

Retrieves other revenues and costs from `account.analytic.line`:
1. Domain: `account_id = project.account_id` AND `move_line_id = False` AND category not in `['manufacturing_order', 'picking_entry']`.
2. `search_read` with `sudo()`: `id`, `amount`, `currency_id`.
3. Groups by `currency_id` in a dict: `{currency_id: {costs: float, revenues: float}}`.
4. Negative `amount` → costs. Positive `amount` → revenues.
5. Converts all amounts to project currency via `currency._convert()`.
6. All amounts placed in `invoiced` / `billed` column (no "to bill/invoice" for AAL items).
7. Adds action for `group_account_readonly` users.

### `action_open_analytic_items()`

Opens the analytic line list view filtered to the project's analytic account:
- Action: `analytic.account_analytic_line_action_entries`
- Domain: `[('account_id', '=', self.account_id.id)]`
- Context: preserves `create`, sets `default_account_id`.

## Cross-Model Relationships

| Model | Field | Purpose |
|-------|-------|---------|
| `project.project` | `account_id` (`account.analytic.account`) | Links project to analytic account for profitability |
| `account.move.line` | (via search) | Source for vendor bills with analytic distribution |
| `account.analytic.line` | `account_id` | Source for other revenues/costs |
| `account.move` | (via move_id) | Navigation target from profitability |

## Edge Cases & Failure Modes

1. **Multi-account analytic distribution**: `analytic_contribution` is computed as sum of percentages for this project's account_id in the distribution dict. Example: distribution `{1: 50, 2: 50}` for project account 1 → contribution = 0.5.
2. **Currency conversion**: All amounts converted to project currency using `company_currency_id._convert()` with move line date. Handles multi-currency vendor bills.
3. **Bill = vendor credit**: If `amount_invoiced` and `amount_to_invoice` are both zero (e.g., posted refund = credit note), the section is not shown.
4. **Purchase order bills**: Bills linked to `purchase.order.line` are excluded via `_get_add_purchase_items_domain` — those are tracked in `project_purchase` instead. This avoids double-counting.
5. **No analytic account on project**: If project has no `account_id`, profitability calculations return empty. `account_id` is required for this module's functionality.
6. **AAL without project**: `_get_domain_aal_with_no_move_line()` does NOT filter by `project_id` — this captures analytic lines created directly (overhead/other costs not linked to a specific task/project).
7. **Manufacturing/picking entries**: Excluded from `other_revenues_aal` and `other_costs_aal` via domain filter on `category`. These are tracked via `mrp_account` instead.
8. **Privacy**: `sudo()` is used to read `account.move.line` and `account.analytic.line`. Access control is enforced at the action level via group checks.

## Security Groups

- `account.group_account_invoice`: Full access to vendor bills section + action.
- `account.group_account_readonly`: Read-only access to vendor bills; access to AAL actions.
- Without either group: no actionable items in vendor bills section, but costs may still display (read-only).

## Integration Points

- **project**: Extends `project.project`. Project must have `account_id` set for profitability to work.
- **account**: Reads `account.move.line` and `account.move`. Uses `account.analytic.account` currency for conversion.
- **analytic**: Reads `account.analytic.line` records. The AAL source is used for non-timesheet, non-manufacturing costs/revenues.
- **sale_project**: Depends on `project_account` for profitability data. The `sale_line_id` on tasks links to billing.
- **project_purchase**: Tracks purchase order costs separately. `project_account` shows vendor bills NOT from PO.
- **mrp_account**: Manufacturing orders have their own profitability section. `project_account` excludes `category IN ['manufacturing_order', 'picking_entry']`.

## Profitability Data Flow

```
project_project._compute_profitability_items()
        ↓
_calls _add_purchase_items()         → project_account
_calls _get_items_from_aal()          → project_account
calls super() (sale/delivery)         → sale_project / project_stock
        ↓
Sections merged into profitability dict
        ↓
Frontend: Kanban card shows costs/revenues
         profitability_action shows detailed breakdown
```

## Source Files

- `project_account/models/project_project.py` — Main extension.
- `project_account/models/project_update.py` — Project update status colors.