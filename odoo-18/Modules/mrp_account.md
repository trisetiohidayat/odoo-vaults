# mrp_account - Accounting - MRP

**Module:** `mrp_account`
**Depends:** `mrp`, `stock_account`
**Category:** Manufacturing/Manufacturing
**Auto-install:** True

---

## Purpose

Adds analytic accounting to Manufacturing Orders (MO). Tracks labor costs, workcenter costs, and component valuations through stock.valuation.layer records linked to analytic accounts. Enables cost structure reporting and BoM-based cost computation.

---

## Key Extensions

### mrp.production Extension

**File:** `models/mrp_production.py`

| Field | Type | Description |
|---|---|---|
| `extra_cost` | `Float` | Additional unit cost added to finished product valuation |
| `show_valuation` | `Boolean` | Computed, True if any finished move is done |

**Key Methods:**

- `_cal_price(consumed_moves)` - Sets price_unit on the finished move based on:
  - Sum of `stock.valuation.layer` values from consumed components (negative)
  - Workcenter costs from `workorder_ids._cal_cost()`
  - `extra_cost * quantity`
  - Byproduct cost sharing via `move_byproduct_ids.cost_share`

- `_post_labour()` - Posts labor journal entries when MO is done (real_time valuation only):
  - Groups workorder costs by `workcenter_id.expense_account_id`
  - Creates `account.move` with journal `stock_journal`
  - Links `account.move.line` to `mrp.workorder.productivity.account_move_line_id`
  - Updates `time_ids` with the move line reference

- `_post_inventory()` - Calls `_post_labour()` after standard inventory posting

- `_get_backorder_mo_vals()` - Carries `extra_cost` to backorder MOs

- `action_view_stock_valuation_layers()` - Opens SVL list filtered to this MO

---

### mrp.workorder Extension

**File:** `models/mrp_workorder.py`

| Field | Type | Description |
|---|---|---|
| `mo_analytic_account_line_ids` | `Many2many` | Analytic lines from MO-level raw material consumption |
| `wc_analytic_account_line_ids` | `Many2many` | Analytic lines from workcenter time costing |

**Key Methods:**

- `_create_or_update_analytic_entry()` - Called on `_compute_duration` and `_set_duration`:
  - Computes `value = -(duration / 60.0) * workcenter_id.costs_hour`
  - Uses `account.analytic.account._perform_analytic_distribution()` to create lines

- `_prepare_analytic_line_values()` - Returns base vals with:
  - `category = 'manufacturing_order'`
  - `ref = production_id.name`
  - Product set to MO product, UoM = hours

- `action_cancel()` - Deletes associated analytic lines before cancel

---

### account.analytic.account Extension

**File:** `models/analytic_account.py`

| Field | Type | Description |
|---|---|---|
| `production_ids` | `Many2many` | MOs linked to this analytic account |
| `production_count` | `Integer` | Computed count of linked MOs |
| `bom_ids` | `Many2many` | BoMs using this analytic account |
| `bom_count` | `Integer` | Computed count |
| `workcenter_ids` | `Many2many` | Workcenters using this analytic account |
| `workorder_count` | `Integer` | Computed count |

**Actions:**
- `action_view_mrp_production()` - List/form view of linked MOs
- `action_view_mrp_bom()` - List/form view of linked BoMs
- `action_view_workorder()` - List view of work orders

---

### account.analytic.line Extension

**File:** `models/analytic_account.py`

| Field | Type | Description |
|---|---|---|
| `category` | `Selection` | Added `manufacturing_order` option |

`business_domain` on `account.analytic.applicability` also extends with `'manufacturing_order'`.

---

### mrp.workcenter Extension

**File:** `models/mrp_workcenter.py`

| Field | Type | Description |
|---|---|---|
| `costs_hour_account_ids` | `Many2many` | Computed from analytic_distribution |
| `expense_account_id` | `Many2one` | Account used for labor expense posting; falls back to product's expense account |

---

### mrp.workorder.productivity Extension

**File:** `models/mrp_workcenter.py`

| Field | Type | Description |
|---|---|---|
| `account_move_line_id` | `Many2one` | Links time logs to journal entry lines from `_post_labour()` |

---

### account.move Extension

**File:** `models/account_move.py`

| Field | Type | Description |
|---|---|---|
| `wip_production_ids` | `Many2many` | MOs that this WIP journal entry is based on |
| `wip_production_count` | `Integer` | Computed count |
| `timesheet_invoice_id` | `Many2one` | (from hr_timesheet) Links to the invoice that included this timesheet |

**Action:** `action_view_wip_production()` - Opens linked WIP MOs

---

### stock.move Extension

**File:** `models/stock_move.py`

Overrides accounting source/destination account methods for production locations:

- `_get_src_account()` - Returns `location_id.valuation_out_account_id` or `production` account for production-out moves
- `_get_dest_account()` - Returns `location_dest_id.valuation_in_account_id` or `production` account for production-in moves

Also handles `_filter_anglo_saxon_moves` to include BoM-kitted moves in purchase invoice valuation.

---

### product.product Extension

**File:** `models/product.py`

- `_set_price_from_bom()` - Sets `standard_price` from BoM cost calculation
- `_compute_bom_price()` - Sums:
  - Workcenter operations: `(duration_expected / 60) * operation._total_cost_per_hour()`
  - BoM lines: component qty * component cost (recursive for sub-Boms)
  - Applies byproduct cost_share deduction
- `_compute_average_price()` - Handles kit-type products by exploding BoM recursively

---

## Valuation Flow

### WIP (Work In Progress) Valuation

1. **MO confirmation** - No journal entry yet
2. **Component consumption** - `stock.move` consumes raw materials; SVL created with `value = -component_cost`
3. **MO done** - `_cal_price()` sets finished move price_unit:
   ```
   total_cost = -sum(svl_values) + workcenter_costs + extra_cost
   finished_move.price_unit = total_cost * (1 - byproduct_cost_share/100) / quantity
   ```
4. **Labor posting** (`_post_labour`) - Creates journal entry debiting `expense_account` and crediting `stock_valuation`

### Stock Valuation Layer Link

SVLs are created for:
- Component consumption (raw material out)
- Finished product receipt
- Byproduct receipt
- Additional landed costs

Each SVL can be linked to an `account.move` via the `stock.valuation.layer.stock_landed_cost_id` or `mrp_production_id` link.

---

## Cost Computation Hierarchy

1. **Material cost** = Sum of `stock.valuation.layer.value` for consumed components (negative values)
2. **Workcenter cost** = Sum of `workorder._cal_cost()` where each workorder cost = `duration / 60 * workcenter_id.costs_hour`
3. **Extra cost** = `extra_cost * finished_qty`
4. **Byproduct offset** = `total_cost * cost_share / 100` per byproduct
5. **Finished product unit cost** = `(material + workcenter + extra - byproduct_offset) / quantity`

---

## Dependencies

```
stock_account
  └── mrp_account
        └── mrp (core)
        └── stock_account (valuation)
```

Auto-installs with `mrp_account` when both `mrp` and `stock_account` are installed.

---

## Views and Reports

- `report/report_mrp_templates.xml` - Cost structure report template
- `wizard/mrp_wip_accounting.xml` - WIP accounting wizard for manual labor cost entry