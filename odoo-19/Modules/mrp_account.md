---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #mrp
  - #accounting
  - #manufacturing
---

# Module: mrp_account

## Overview

**Technical Name:** `mrp_account`
**Category:** Supply Chain/Manufacturing
**Dependencies:** `mrp`, `stock_account`
**Auto-install:** True (installs automatically when both `mrp` and `stock_account` are present)
**License:** LGPL-3

`mrp_account` bridges the **Manufacturing (MRP)** and **Accounting** modules in Odoo 19, enabling full cost tracking and valuation throughout the production lifecycle. It adds analytic accounting integration to workcenters and production orders (via `analytic.mixin`), creates WIP (Work-in-Progress) journal entries, posts labour cost journal entries on MO completion, and provides BoM-based cost computation for products. It is the prerequisite module for all manufacturing-specific accounting features, including the Cost of Production reporting.

**Post-init hook:** `_configure_journals`. When `mrp_account` is installed on top of an existing chart of accounts, the hook searches all companies with a chart template installed (in `parent_path` order — root companies first) and propagates the `property_stock_account_production_cost_id` from the template data via `ChartTemplate._post_load_data()`. This ensures the production valuation account is set correctly without requiring manual re-configuration.

---

## Architecture

```
mrp_account/
├── __init__.py                 # Registers models, report, wizard + _configure_journals hook
├── models/
│   ├── account_move.py         # WIP link tracking on account.move; kit qty invoicing fix
│   ├── analytic_account.py     # Analytic account MRP links; MO/BoM/WC stat buttons
│   ├── mrp_production.py        # WIP moves, extra_cost, _cal_price, _post_labour
│   ├── mrp_workcenter.py        # Expense account, analytic distribution on workcenters
│   ├── mrp_workorder.py         # Analytic line creation on workorder duration changes
│   ├── product.py               # BoM cost button; production account on product category
│   └── stock_move.py            # Production move valuation; kit price unit override
├── wizard/
│   └── mrp_wip_accounting.py   # WIP journal entry wizard + line model
├── report/
│   ├── mrp_report_mo_overview.py  # MO overview with real cost (done moves)
│   └── stock_valuation_report.py  # Cost of Production section in valuation report
└── tests/                     # Full test suite
```

---

## Models Extended

### 1. `account.move` — WIP Journal Entries

**File:** `mrp_account/models/account_move.py`

Extends the standard `account.move` model to track WIP (Work-in-Progress) journal entries linked to manufacturing orders.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `wip_production_ids` | Many2many (`mrp.production`) | Production orders associated with this WIP journal entry. Set via `wip_move_production_rel` link table. `copy=False` — not duplicated on normal move duplication. |
| `wip_production_count` | Integer (computed) | Count of associated manufacturing orders. Used for the stat button in the form view header. |

#### Method: `copy(default=None)` (Override)

Copies the WIP production association when the account move is duplicated. Operates in sudo mode to bypass access restrictions on the production relation:

```python
def copy(self, default=None):
    records = super().copy(default)
    for record, source in zip(records.sudo(), self.sudo()):
        record.wip_production_ids = source.wip_production_ids
    return records
```

The `sudo()` call is necessary because the user performing the copy may lack write access to `wip_production_ids` on the target record. The zip pairs the duplicated records with their sources in order.

#### Method: `_compute_wip_production_count()`

```python
def _compute_wip_production_count(self):
    for account in self:
        account.wip_production_count = len(account.wip_production_ids)
```

Trivial length computation. Required because the stat button cannot directly display `len()` in the view — it needs a named computed field.

#### Method: `action_view_move_wip()`

Smart action on `mrp.production` that opens the WIP journal entries linked to this MO. Single WIP entry opens in form view; multiple open in list view with domain filter:

```python
def action_view_move_wip(self):
    self.ensure_one()
    action = {'res_model': 'account.move', 'type': 'ir.actions.act_window'}
    if len(self.wip_move_ids) == 1:
        action.update({'view_mode': 'form', 'res_id': self.wip_move_ids.id})
    else:
        action.update({
            'name': _("WIP Entries of %s", self.name),
            'domain': [('id', 'in', self.wip_move_ids.ids)],
            'view_mode': 'list,form',
            'views': [(self.env.ref('account.view_move_tree').id, 'list')],
        })
    return action
```

The button is `invisible="wip_move_count == 0"` in the form view XML and requires `account.group_account_user`. It appears in the stat button area of the MO form header alongside the manufacturing statistics.

#### Method: `action_view_wip_production()`

Smart action that opens the related MO(s). Returns a window action configured for single-record form view or a list view depending on count:

```python
def action_view_wip_production(self):
    self.ensure_one()
    action = {'res_model': 'mrp.production', 'type': 'ir.actions.act_window'}
    if len(self.wip_production_ids) == 1:
        action.update({'view_mode': 'form', 'res_id': self.wip_production_ids.id})
    else:
        action.update({
            'name': _("WIP MOs of %s", self.name),
            'domain': [('id', 'in', self.wip_production_ids.ids)],
            'view_mode': 'list,form',
        })
    return action
```

#### L3 — Cross-Model Edge Cases

- When an `account.move` is duplicated via `copy()`, the wizard field `copy=False` on `wip_production_ids` is overridden by the explicit loop that re-assigns the WIP relations. This ensures WIP associations survive duplication.
- The `wip_production_ids` link table (`wip_move_production_rel`) uses a composite primary key of `move_id` + `production_id`. Duplicate moves for the same MO produce multiple rows.
- `action_view_wip_production` respects access rights via `ir.actions.act_window` defaults; users without `mrp.group_mrp_user` see an empty list.
- The reversal entries created by the WIP wizard also have `wip_production_ids` set, enabling traceability from both the original and reversed entries back to the MO.

---

### 2. `account.move.line` — Kit Product Invoicing

**File:** `mrp_account/models/account_move.py`

Extends `account.move.line` to handle kit-type (phantom) products in invoiced quantity reporting.

#### Method: `_get_invoiced_qty_per_product()` (Override)

Replaces phantom kit products with their exploded components when computing quantities for vendor bills or customer invoices. This is critical for companies that sell kits — without this override, kit-level invoicing would report inflated or meaningless quantities.

```python
def _get_invoiced_qty_per_product(self):
    qties = defaultdict(float)
    res = super()._get_invoiced_qty_per_product()
    invoiced_products = self.env['product.product'].concat(*res.keys())
    bom_kits = self.env['mrp.bom']._bom_find(
        invoiced_products, company_id=self.company_id[:1].id, bom_type='phantom'
    )
    for product, qty in res.items():
        bom_kit = bom_kits[product]
        if bom_kit:
            invoiced_qty = product.uom_id._compute_quantity(qty, bom_kit.product_uom_id, round=False)
            factor = invoiced_qty / bom_kit.product_qty
            dummy, bom_sub_lines = bom_kit.explode(product, factor)
            for bom_line, bom_line_data in bom_sub_lines:
                qties[bom_line.product_id] += bom_line.product_uom_id._compute_quantity(
                    bom_line_data['qty'], bom_line.product_id.uom_id
                )
        else:
            qties[product] += qty
    return qties
```

The algorithm:
1. Calls the parent method to get raw quantities keyed by product.
2. Finds all phantom BoMs for the invoiced products via `_bom_find`.
3. For each kit product, converts the invoiced quantity to the BoM's base UoM, then computes the explosion factor.
4. Explodes the kit using `bom_kit.explode(product, factor)` — returns a tuple where the first element (`dummy`) is the product recordset (discarded) and the second is the sub-lines dict mapping BoM line records to their quantity data. Each `(bom_line, bom_line_data)` pair yields the component and its proportional quantity.
5. Accumulates component quantities into the `qties` dictionary.
6. Non-kit products pass through unchanged.

#### L3 — Cross-Model Edge Cases

- Phantom kits with multi-level nesting (kits within kits) are handled recursively by `mrp.bom.explode()`, which is called per kit level.
- The factor calculation (`qty / bom_kit.product_qty`) converts from the kit's UoM to the BoM's base UoM before exploding.
- If a kit's BoM references another phantom kit, the inner kit is also exploded. The `qties` dictionary accumulates across all levels.
- Products not found in any phantom BoM are passed through as-is.
- The `company_id[:1]` access pattern handles the case where a move line has no company (empty recordset) — returns `None` to `_bom_find`, which then ignores the company filter.
- `round=False` preserves fractional quantities through the UoM conversion, critical for accurate proportional breakdown.

---

### 3. `account.analytic.account` — MRP Links

**File:** `mrp_account/models/analytic_account.py`

Extends `account.analytic.account` to provide a bidirectional link with MRP records, enabling analytic cost reporting for manufacturing.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `production_ids` | Many2many (`mrp.production`) | MOs that use this analytic account for cost tracking. |
| `production_count` | Integer (computed) | Count of linked MOs. |
| `bom_ids` | Many2many (`mrp.bom`) | Bills of Materials linked to this analytic account. |
| `bom_count` | Integer (computed) | Count of linked BoMs. |
| `workcenter_ids` | Many2many (`mrp.workcenter`) | Workcenters that post costs to this analytic account. |
| `workorder_count` | Integer (computed) | Total work orders from both linked workcenters and linked productions. |

#### Computed Field Details

**`_compute_production_count()`**

```python
def _compute_production_count(self):
    for account in self:
        account.production_count = len(account.production_ids)
```

Simply `len(self.production_ids)`. Inexpensive since the relation is a direct Many2many. No database aggregation needed.

**`_compute_bom_count()`**

```python
def _compute_bom_count(self):
    for account in self:
        account.bom_count = len(account.bom_ids)
```

Same pattern as production_count.

**`_compute_workorder_count()`**

```python
def _compute_workorder_count(self):
    for account in self:
        account.workorder_count = len(
            account.workcenter_ids.order_ids | account.production_ids.workorder_ids
        )
```

Computes the union of workorders from two sources:
1. `workcenter_ids.order_ids` — workorders using this workcenter.
2. `production_ids.workorder_ids` — workorders on MOs linked to this analytic account.

Uses Python set union (`|`) on recordsets — the union is computed in-memory after two separate database queries. For accounts linked to thousands of records, this could become expensive.

#### Methods

**`action_view_mrp_production()`**
Opens the list of MOs filtered to those linked to this analytic account. Sets `default_analytic_account_id` in context so new MOs are pre-linked. Single MO opens directly in form view.

**`action_view_mrp_bom()`**
Opens the BoM list filtered to this account. Same context pre-linking pattern.

**`action_view_workorder()`**
Opens workorders from both linked workcenters and linked productions. Uses `create: False` context to prevent accidental workorder creation from the analytic account view.

#### L3 — Cross-Model Edge Cases

- When an analytic account is deleted, the Many2many relations cascade-delete via the implicit `ondelete='cascade'` on the auto-created relational table.
- The union query for `workorder_count` does NOT filter by company. If a user has cross-company access, they see workorders from all companies — potential data leakage in multi-company setups. The base `account.analytic.account` model itself enforces company restrictions via record rules, but the computed field does not re-filter after union.
- BoM creation from analytic account context (`default_analytic_account_id`) does not trigger validation of analytic applicability rules during BoM creation — the test `test_mandatory_analytic_plan_bom` explicitly confirms this, as applicability rules should not block BoM creation.
- The `workorder_count` union uses `|` (set union). In Python, recordset union preserves the order of the first operand for common records. The `len()` call materializes the union, which could fail for very large recordsets if the underlying SQL would exceed `max_recursive_depth` or hit query size limits.

---

### 4. `account.analytic.line` — Manufacturing Category

**File:** `mrp_account/models/analytic_account.py`

Adds a new `category` option for analytic lines originating from manufacturing.

#### Fields Modified

| Field | Type | Change |
|-------|------|--------|
| `category` | Selection | Added `('manufacturing_order', 'Manufacturing Order')` to the selection list. |

#### L3 — Edge Cases

- Analytic lines with `category = 'manufacturing_order'` are created by `mrp_workorder.py` via `_create_or_update_analytic_entry_for_record()`. The category enables filtering and reporting of manufacturing-specific costs separately from other analytic categories (e.g., `general`, `sale`, `purchase`).
- When an analytic applicability plan is set to `business_domain = 'manufacturing_order'`, it forces mandatory analytic distribution on MOs. The test suite confirms that BoM and workcenter creation remain unconstrained even when this domain is active, as these are configuration records not transaction records.

---

### 5. `account.analytic.applicability` — Manufacturing Domain

**File:** `mrp_account/models/analytic_account.py`

Extends applicability to cover the manufacturing order business domain.

#### Fields Modified

| Field | Type | Change |
|-------|------|--------|
| `business_domain` | Selection | Added `('manufacturing_order', 'Manufacturing Order')`. On delete: `'cascade'` — if a plan is deleted, applicability records are removed. |

---

### 6. `mrp.workcenter` — Analytic and Expense Accounts

**File:** `mrp_account/models/mrp_workcenter.py`

Extends `mrp.workcenter` with analytic distribution support and an expense account.

#### Inheritance

Uses `_inherit = ['mrp.workcenter', 'analytic.mixin']`. The `analytic.mixin` (from the `analytic` module) provides the `analytic_distribution` JSON field and its associated machinery for automatic analytic line generation and distribution splitting.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `costs_hour_account_ids` | Many2many (`account.analytic.account`) | Computed from `analytic_distribution`. Extracts all analytic account IDs referenced in the distribution JSON. Stored for performance. |
| `expense_account_id` | Many2one (`account.account`) | The account to which workcenter labour costs are posted when the MO is marked done. Falls back to the product's expense account if not set. `check_company=True`. |

#### Computed Field: `_compute_costs_hour_account_ids()`

```python
def _compute_costs_hour_account_ids(self):
    for record in self:
        record.costs_hour_account_ids = bool(record.analytic_distribution) and self.env['account.analytic.account'].browse(
            list({int(account_id) for ids in record.analytic_distribution for account_id in ids.split(",")})
        ).exists()
```

The `analytic_distribution` JSON uses Odoo's compound ID format for keys: `"{account_id},{plan_id}"` (e.g., `"2,3"` means analytic account ID 2 in plan 3). The `_compute_costs_hour_account_ids` method:
1. Iterates all keys in the JSON dict (`record.analytic_distribution`).
2. Splits each key on commas — both the account ID and plan ID are extracted as integers.
3. Deduplicates using a set comprehension.
4. Browses all extracted IDs as `account.analytic.account` records and calls `.exists()` to filter out deleted/invalid accounts.
5. Returns an empty recordset if `analytic_distribution` is falsy (`bool(record.analytic_distribution)` guard).

The double extraction (account ID AND plan ID as separate integers) means the set may include plan IDs alongside account IDs. This is harmless for the browse/exists check — non-account IDs simply return empty from `exists()`. The field is `store=True` for performance — it recomputes only when `analytic_distribution` changes.

#### Fields Inherited from `analytic.mixin`

| Field | Type | Source |
|-------|------|--------|
| `analytic_distribution` | Json | `analytic.mixin` |

The `analytic_distribution` JSON field stores a mapping of analytic account IDs (in compound format) to percentage allocations. This drives automatic creation of analytic lines when workorder time is recorded. The distribution can split costs across multiple analytic accounts simultaneously.

---

### 7. `mrp.workcenter.productivity` — Labour Link

**File:** `mrp_account/models/mrp_workcenter.py`

Extends the time-tracking record for workcenter productivity logs.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `account_move_line_id` | Many2one (`account.move.line`) | Links a productivity (time) record to the labour cost journal entry line generated at MO completion. Used to track which specific time block drove which journal entry. |

#### L3 — Edge Cases

- Set in `_post_labour()` of `mrp.production` via `workorders[line.account_id].time_ids.write({'account_move_line_id': line.id})`. The mapping is by account because multiple workorders may share the same expense account.
- When a workorder is cancelled, the associated `account_move_line_id` is not explicitly cleared. The productivity record is deleted along with the workorder, leaving the linked move line without a reference — a potential orphan reference.
- The field is not `ondelete='cascade'` on the related `account.move.line`, so deleting a journal entry does not delete the productivity record.
- When the same workorder has multiple time blocks (start/stop cycles), each `mrp.workcenter.productivity` record can be linked to the same journal entry line, since `_post_labour` aggregates all time into a single per-account amount.

---

### 8. `mrp.workorder` — Analytic Line Creation

**File:** `mrp_account/models/mrp_workorder.py`

Extends `mrp.workorder` to create analytic lines for workcentre time costs. This is the primary mechanism for capturing labour costs against analytic accounts.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `mo_analytic_account_line_ids` | Many2many (`account.analytic.line`) | Analytic lines created against the MO's analytic account (from `production_id.analytic_distribution`). |
| `wc_analytic_account_line_ids` | Many2many (`account.analytic.line`) | Analytic lines created against the workcenter's analytic distribution. |

Both fields use custom relation table names (`mrp_workorder_mo_analytic_rel` and `mrp_workorder_wc_analytic_rel`). `copy=False` — analytic lines are transaction records and should not be duplicated.

#### Method: `_compute_duration()` (Override)

```python
def _compute_duration(self):
    res = super()._compute_duration()
    self._create_or_update_analytic_entry()
    return res
```

Hooks into the parent's duration computation. Called whenever workorder duration changes (timer start/stop, manual adjustment, UI save). Triggers analytic line creation or update after the duration is recalculated. The return value from `super()` is passed through unchanged.

#### Method: `_set_duration()` (Override)

```python
def _set_duration(self):
    res = super()._set_duration()
    self._create_or_update_analytic_entry()
    return res
```

Called when duration is set explicitly (e.g., from the UI). Same hook pattern as `_compute_duration`. Both hooks call the same analytic entry method, which means if a timer starts and then duration is set explicitly, the method runs twice per transaction.

#### Method: `_create_or_update_analytic_entry()` (L3 Core)

```python
def _create_or_update_analytic_entry(self):
    for wo in self:
        if not wo.id:
            continue
        hours = wo.duration / 60.0
        value = -hours * wo.workcenter_id.costs_hour
        wo._create_or_update_analytic_entry_for_record(value, hours)
```

Key formula: **cost = duration (minutes) / 60 x costs_hour**. The value is negative (cost/expense by accounting convention). Skips records without an ID (new unsaved records). Delegates to the workcenter-level analytic distribution handling.

The `if not wo.id: continue` check prevents analytic entry creation for newly created (unsaved) workorders. This is important because `_compute_duration` can be triggered during record creation via `default_get` or computed field evaluation before the record is persisted.

#### Method: `_create_or_update_analytic_entry_for_record(value, hours)` (L3 Core)

```python
def _create_or_update_analytic_entry_for_record(self, value, hours):
    self.ensure_one()
    if self.workcenter_id.analytic_distribution or self.wc_analytic_account_line_ids or self.mo_analytic_account_line_ids:
        wc_analytic_line_vals = self.env['account.analytic.account']._perform_analytic_distribution(
            self.workcenter_id.analytic_distribution, value, hours,
            self.wc_analytic_account_line_ids, self
        )
        if wc_analytic_line_vals:
            self.wc_analytic_account_line_ids += self.env['account.analytic.line'].sudo().create(wc_analytic_line_vals)
```

Uses the analytic mixin's `_perform_analytic_distribution()` to split costs across multiple analytic accounts per the workcenter's distribution. This method:
1. Checks if the workcenter has a distribution or if existing lines are already linked.
2. Calls `_perform_analytic_distribution()` which returns a list of value dicts, one per distribution line.
3. Creates new analytic lines using `sudo()` to bypass access restrictions.
4. Appends to `wc_analytic_account_line_ids`.

Note: The `mo_analytic_account_line_ids` path is currently not populated in this method — the MO-level analytic distribution is handled separately by the `analytic.mixin` behavior on `mrp.production`.

#### Method: `_prepare_analytic_line_values(account_field_values, amount, unit_amount)`

Constructs the dictionary for analytic line creation:

```python
{
    'name': _("[WC] %s", self.display_name),
    'amount': amount,                  # negative = cost
    **account_field_values,           # analytic_distribution, account_id, etc.
    'unit_amount': unit_amount,       # hours
    'product_id': self.product_id.id,
    'product_uom_id': ref('uom.product_uom_hour'),
    'company_id': self.company_id.id,
    'ref': self.production_id.name,
    'category': 'manufacturing_order',
}
```

The line is named with `[WC]` prefix to distinguish workcenter costs from other analytic entries. References the MO name in `ref` for traceability. The `category = 'manufacturing_order'` enables filtering in analytic reports.

#### Method: `action_cancel()` (Override)

```python
def action_cancel(self):
    (self.mo_analytic_account_line_ids | self.wc_analytic_account_line_ids).unlink()
    return super().action_cancel()
```

Deletes both sets of analytic lines before calling `super()`. Ensures no orphaned analytic lines remain for cancelled workorders. The union `|` is safe here because `unlink()` on an empty recordset is a no-op.

#### Method: `unlink()` (Override)

```python
def unlink(self):
    (self.mo_analytic_account_line_ids | self.wc_analytic_account_line_ids).unlink()
    return super().unlink()
```

Same cleanup pattern as `action_cancel()` — deletes analytic lines before record removal. The `sudo()` is not needed because the calling user context is inherited.

#### L3 — Edge Cases

- **Double-hook on duration**: Both `_compute_duration` and `_set_duration` call `_create_or_update_analytic_entry`. If a timer starts and then duration is set explicitly, the method runs twice per transaction. The `_perform_analytic_distribution` method handles updates by replacing existing lines, so duplicate costs are avoided — but there is still redundant computation.
- **Negative cost values**: Costs are stored as negative amounts (debit to expense). The `amount` field of `account.analytic.line` follows standard accounting sign convention: negative = credit to the analytic account (cost), positive = debit (revenue/credit).
- **`sudo()` on line creation**: Analytic lines are created with `sudo()` because the manufacturing user creating the workorder may not have direct write access to `account.analytic.line` records. This is a deliberate privilege elevation scoped to this operation.
- **Company-dependent UoM**: The hour UoM reference (`uom.product_uom_hour`) is resolved at call time. If the UoM is archived or deleted, the analytic line creation fails with a `ValidationError` from the foreign key constraint.
- **Multi-company**: The `company_id` is propagated from the workorder to the analytic line. If the analytic account belongs to a different company than the workorder, the line creation may fail depending on analytic account's company restrictions.
- **Empty distribution**: If `analytic_distribution` is empty/falsy, the condition `if self.workcenter_id.analytic_distribution or ...` evaluates to False and no lines are created. This means workcenters without analytic distributions do not generate any analytic lines.

---

### A. `mrp.workorder._cal_cost(date=False)` — Cost Foundation

**File:** `mrp/models/mrp_workorder.py` (base `mrp` module)

This method is not defined in `mrp_account` — it is the foundational cost computation method defined in the base `mrp` module and inherited by all `mrp.workorder` records. Both `_cal_price()` in `mrp.production` and `_post_labour()` in `mrp_account` delegate to this method.

```python
def _cal_cost(self, date=False):
    """Returns total cost of time spent on workorder.

    :param datetime date: Only calculate for time_ids that ended before this date
    """
    total = 0
    for workorder in self:
        if workorder._should_estimate_cost():
            duration = workorder.duration_expected / 60
        else:
            intervals = Intervals([
                [t.date_start, t.date_end, t]
                for t in workorder.time_ids if t.date_end and (not date or t.date_end < date)
            ])
            duration = sum_intervals(intervals)
        total += duration * (workorder.costs_hour or workorder.workcenter_id.costs_hour)
    return total
```

**Two execution paths:**
- **Estimated cost** (`_should_estimate_cost() == True`): Uses `duration_expected` (planned time from BoM operation) multiplied by the hourly rate. Triggered when no actual time has been logged yet.
- **Actual cost** (default): Uses `Intervals` to sum the actual logged time from `time_ids` (productivity records). If `date` is passed (used by the WIP wizard), filters intervals to only include time blocks that ended before that date.

**Key behavior:** The workorder's own `costs_hour` field takes precedence over `workcenter_id.costs_hour`. If neither is set, the rate is 0, resulting in zero cost (which silently passes without error).

**WIP wizard vs `_post_labour`:** The WIP wizard passes `date` to `_cal_cost(date)` to compute overhead value at a specific past point in time. `_post_labour()` calls `_cal_cost()` without a date, capturing all actual logged time when the MO is marked done.

---

### 9. `mrp.production` — Costing and Labour Posting

**File:** `mrp_account/models/mrp_production.py`

The central model for manufacturing order accounting. Extends `mrp.production` with WIP tracking, extra costs, and labour journal entry posting.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `extra_cost` | Float | Additional unit cost (per finished product unit) added to the total production cost. Not related to components or workcentre time. `copy=False`. Propagated to backorder MOs via `_get_backorder_mo_vals()`. |
| `show_valuation` | Boolean (computed) | True if any finished move is done. Used to conditionally show the valuation button. |
| `wip_move_ids` | Many2many (`account.move`) | Journal entries posted as WIP accounting for this MO. Link via `wip_move_production_rel` (composite PK: `move_id` + `production_id`). `copy=False`. |
| `wip_move_count` | Integer (computed) | Count of WIP journal entries. |

#### Field: `extra_cost`

Added to the finished product's price unit in `_cal_price()`. This allows manual cost adjustments (e.g., labour overhead, setup costs not captured by workcenters) without modifying the BoM. It is copied to backorder MOs via `_get_backorder_mo_vals()`.

The `copy=False` attribute means the extra cost is NOT copied when the MO is duplicated. This is intentional — a duplicate MO should not automatically inherit the extra cost, as the duplication may be for a different production scenario.

#### Method: `write(vals)` (Override)

When the production name changes, updates the `ref` and `name` fields on all related analytic lines:

```python
def write(self, vals):
    res = super().write(vals)
    for production in self:
        if vals.get('name'):
            production.move_raw_ids.analytic_account_line_ids.ref = production.display_name
            for workorder in production.workorder_ids:
                workorder.mo_analytic_account_line_ids.ref = production.display_name
                workorder.mo_analytic_account_line_ids.name = _("[WC] %s", workorder.display_name)
    return res
```

Ensures analytic lines remain traceable to the MO even after renaming. The `analytic_account_line_ids` on `move_raw_ids` comes from `stock_account` module's analytic mixin integration. The name update for workorder analytic lines prepends `[WC]` to maintain the naming convention.

#### Method: `_cal_price(consumed_moves)` (L3 Core)

Calculates and sets the finished product's `price_unit` based on all cost components:

```python
def _cal_price(self, consumed_moves):
    super()._cal_price(consumed_moves)
    work_center_cost = 0
    finished_move = self.move_finished_ids.filtered(
        lambda x: x.product_id == self.product_id
        and x.state not in ('done', 'cancel')
        and x.quantity > 0
    )
    if finished_move:
        if finished_move.product_id.cost_method not in ('fifo', 'average'):
            finished_move.price_unit = finished_move.product_id.standard_price
            return True
        finished_move.ensure_one()
        for work_order in self.workorder_ids:
            work_center_cost += work_order._cal_cost()
        quantity = finished_move.product_uom._compute_quantity(
            finished_move.quantity, finished_move.product_id.uom_id
        )
        extra_cost = self.extra_cost * quantity
        total_cost = sum(move.value for move in consumed_moves) + work_center_cost + extra_cost
        byproduct_moves = self.move_byproduct_ids.filtered(
            lambda m: m.state not in ('done', 'cancel') and m.quantity > 0
        )
        byproduct_cost_share = 0
        for byproduct in byproduct_moves:
            if byproduct.cost_share == 0:
                continue
            byproduct_cost_share += byproduct.cost_share
            if byproduct.product_id.cost_method in ('fifo', 'average'):
                byproduct.price_unit = (
                    total_cost * byproduct.cost_share / 100
                    / byproduct.product_uom._compute_quantity(byproduct.quantity, byproduct.product_id.uom_id)
                )
        finished_move.price_unit = (
            total_cost * float_round(1 - byproduct_cost_share / 100, precision_rounding=0.0001)
            / quantity
        )
    return True
```

**Cost components:**
1. **Component value**: `sum(move.value for move in consumed_moves)` — from stock valuation layer (includes landed costs, etc.).
2. **Workcentre cost**: `sum(work_order._cal_cost() for work_order in self.workorder_ids)` — actual or expected time x cost rate.
3. **Extra cost**: `self.extra_cost * quantity` — manual additional cost.

**Byproduct handling:** For each byproduct with non-zero `cost_share`, the price unit is set proportionally before the finished product absorbs the remainder. The finished product's cost share is `1 - sum(cost_share) / 100`.

**Special cases:**
- If the finished product uses `standard_price` (non-FIFO/non-average cost method), `_cal_price` short-circuits and sets `price_unit = standard_price`. This is because standard price products do not use transaction-based valuation.
- If no finished move exists or quantity is zero, the method returns `True` without setting price.
- The `float_round(precision_rounding=0.0001)` prevents floating-point edge cases in percentage calculations.
- Byproduct `cost_share` exceeding 100% is allowed by the code but would result in a negative finished product price — no validation prevents this.

#### Method: `_post_labour()` (L3 Core)

Creates journal entries for workcentre labour costs when an MO is marked done:

```python
def _post_labour(self):
    for mo in self:
        production_location = self.product_id.with_company(self.company_id).property_stock_production
        if mo...product_id.valuation != 'real_time' or not production_location.valuation_account_id:
            continue
        product_accounts = mo.product_id.product_tmpl_id.get_product_accounts()
        labour_amounts = defaultdict(float)  # account -> amount
        workorders = defaultdict(self.env['mrp.workorder'].browse)  # account -> workorders
        for wo in mo.workorder_ids:
            account = wo.workcenter_id.expense_account_id or product_accounts['expense']
            labour_amounts[account] += wo.company_id.currency_id.round(wo._cal_cost())
            workorders[account] |= wo
        workcenter_cost = sum(labour_amounts.values())
        if mo.company_id.currency_id.is_zero(workcenter_cost):
            continue
        desc = _('%s - Labour', mo.name)
        account = production_location.valuation_account_id
        labour_amounts[account] -= workcenter_cost  # balancing credit
        account_move = self.env['account.move'].sudo().create({
            'journal_id': product_accounts['stock_journal'].id,
            'date': fields.Date.context_today(self),
            'ref': desc,
            'move_type': 'entry',
            'line_ids': [(0, 0, {
                'name': desc,
                'ref': desc,
                'balance': -amt,
                'account_id': acc.id,
            }) for acc, amt in labour_amounts.items()]
        })
        account_move._post()
        for line in account_move.line_ids[:-1]:
            workorders[line.account_id].time_ids.write({'account_move_line_id': line.id})
```

**Key characteristics:**
- Only runs for products with `valuation = 'real_time'` (automated valuation).
- Uses `defaultdict(float)` to aggregate costs per expense account.
- The balancing line (valuation account credit) is created by subtracting `workcenter_cost` from the valuation account entry, ensuring the journal entry is balanced.
- Links each journal entry line to the corresponding workorder's time records via `account_move_line_id`.
- The `[:-1]` slice skips the last line (the valuation account debit). Since `labour_amounts` is a `defaultdict(float)`, accessing an uninitialized key returns 0, so the last iteration produces a zero-amount line which is then sliced off.
- Uses `sudo()` for move creation to bypass access restrictions on `account.move` for manufacturing users.

**Journal entry structure (N+1 lines):**
- One debit line per unique expense account (workorder labour costs).
- One credit line for the production valuation account (balancing line).
- Reference: `{MO_NAME} - Labour`

#### Method: `_post_inventory(cancel_backorder=False)` (Override)

```python
def _post_inventory(self, cancel_backorder=False):
    res = super()._post_inventory(cancel_backorder=cancel_backorder)
    self.filtered(lambda mo: mo.state == 'done')._post_labour()
    return res
```

Hooks into the parent's `_post_inventory` to run `_post_labour()` after inventory is posted and only for MOs in `done` state. The filtering `mo.state == 'done'` ensures labour is only posted once — when the MO reaches done status, not on intermediate inventory postings.

#### L3 — Performance Implications

- `_cal_price` iterates over all workorders and calls `_cal_cost()` on each. `_cal_cost()` in turn iterates over time intervals. For MOs with many workorders and long time logs, this can be expensive. The method is called during `button_mark_done()` and when component quantities change.
- `_post_labour` creates one journal move per MO (not per workorder), aggregating costs by expense account. This is efficient but means all workorders sharing an expense account are lumped together — individual traceability is maintained via `account_move_line_id` on the productivity records.
- The `labour_amounts` defaultdict iterates twice: once in `sum(labour_amounts.values())` and again in the comprehension. For a large number of expense accounts, this is a minor inefficiency.

#### L3 — Failure Modes

- If `production_location.valuation_account_id` is not set on a product with `valuation = 'real_time'`, `_post_labour` silently skips posting. No error is raised. This can result in labour costs not being accounted for, which may be discovered only during financial audits.
- Currency rounding via `wo.company_id.currency_id.round()` prevents floating-point precision issues, but rounding errors accumulate when many small workorders post to the same account. The last cent rounding difference lands on the balancing line.
- If the expense account is not reconcilable, the resulting journal entry lines may not be reconcilable, causing issues in follow-up payments or vendor bills.
- The `product_accounts['expense']` fallback assumes the product's expense account is set. If `product_tmpl_id.get_product_accounts()` returns an empty dict or missing 'expense' key, the method would raise an `IndexError`.

---

### 10. `product.template` — Production Account

**File:** `mrp_account/models/product.py`

Extends `product.template` to expose the production (stock valuation) account and add BoM cost computation actions.

#### Method: `_get_product_accounts()` (Override)

Adds the `production` key to the product accounts dictionary:

```python
def _get_product_accounts(self):
    accounts = super()._get_product_accounts()
    if self.categ_id:
        production_account = self.categ_id.property_stock_account_production_cost_id
    else:
        ProductCategory = self.env['product.category']
        production_account = (
            self.valuation == 'real_time'
            and ProductCategory._fields['property_stock_account_production_cost_id']
                .get_company_dependent_fallback(ProductCategory)
            or self.env['account.account']
        )
    accounts['production'] = production_account
    return accounts
```

The production account is used as a valuation counterpart when manufacturing consumes components and produces finished goods. If the category has no production account set, it falls back to the company-level default from the chart of accounts template. If the product has no category or `valuation != 'real_time'`, an empty recordset is returned.

---

### 11. `product.product` — BoM Cost Computation

**File:** `mrp_account/models/product.py`

Implements BoM-based cost computation for products. This is the core of the "cost from BoM" feature.

#### Method: `button_bom_cost()`

Sets price from BoM for a single product variant. Calls `_set_price_from_bom()`:

```python
def button_bom_cost(self):
    self.ensure_one()
    self._set_price_from_bom()
```

#### Method: `action_bom_cost()`

Sets price from BoM for multiple products. Finds all relevant BoMs, then calls `_set_price_from_bom()` for each:

```python
def action_bom_cost(self):
    boms_to_recompute = self.env['mrp.bom'].search([
        '|',
        ('product_id', 'in', self.ids),
        '&', ('product_id', '=', False), ('product_tmpl_id', 'in', self.mapped('product_tmpl_id').ids)
    ])
    for product in self:
        product._set_price_from_bom(boms_to_recompute)
```

The BoM search finds:
1. Product-specific BoMs for each product variant.
2. Template-level BoMs (product_id = False) for templates in the selection.

This allows computing BoM costs for all variants of a template in a single action.

#### Method: `_set_price_from_bom(boms_to_recompute=False)`

Finds the BoM for the product and computes the cost:

```python
def _set_price_from_bom(self, boms_to_recompute=False):
    self.ensure_one()
    bom = self.env['mrp.bom']._bom_find(self)[self]
    if bom:
        self.standard_price = self._compute_bom_price(bom, boms_to_recompute=boms_to_recompute)
    else:
        bom = self.env['mrp.bom'].search([
            ('byproduct_ids.product_id', '=', self.id)
        ], order='sequence, product_id, id', limit=1)
        if bom:
            price = self._compute_bom_price(bom, boms_to_recompute=boms_to_recompute, byproduct_bom=True)
            if price:
                self.standard_price = price
```

If no direct BoM is found, searches for the product as a byproduct of another BoM. The `byproduct_bom=True` flag changes the cost formula to compute the per-unit cost of the byproduct.

#### Method: `_compute_bom_price(bom, boms_to_recompute=False, byproduct_bom=False)` (L3 Core)

Recursively computes the total BoM cost:

```python
def _compute_bom_price(self, bom, boms_to_recompute=False, byproduct_bom=False):
    self.ensure_one()
    if not bom:
        return 0
    if not boms_to_recompute:
        boms_to_recompute = []
    total = 0

    # 1. Workcentre operation costs
    for opt in bom.operation_ids:
        if opt._skip_operation_line(self):
            continue
        total += opt.cost  # from mrp.models.mrp_bom

    # 2. Component costs (recursive for sub-Boms)
    for line in bom.bom_line_ids:
        if line._skip_bom_line(self):
            continue
        if line.child_bom_id and line.child_bom_id in boms_to_recompute:
            child_total = line.product_id._compute_bom_price(
                line.child_bom_id, boms_to_recompute=boms_to_recompute
            )
            total += line.product_id.uom_id._compute_price(
                child_total, line.product_uom_id
            ) * line.product_qty
        else:
            total += line.product_id.uom_id._compute_price(
                line.product_id.standard_price, line.product_uom_id
            ) * line.product_qty

    # 3. Byproduct cost deduction (finished product mode)
    if byproduct_bom:
        byproduct_lines = bom.byproduct_ids.filtered(
            lambda b: b.product_id == self and b.cost_share != 0
        )
        product_uom_qty = sum(
            line.product_uom_id._compute_quantity(line.product_qty, self.uom_id, round=False)
            for line in byproduct_lines
        )
        byproduct_cost_share = sum(byproduct_lines.mapped('cost_share'))
        if byproduct_cost_share and product_uom_qty:
            return total * byproduct_cost_share / 100 / product_uom_qty
    else:
        byproduct_cost_share = sum(bom.byproduct_ids.mapped('cost_share'))
        if byproduct_cost_share:
            total *= float_round(1 - byproduct_cost_share / 100, precision_rounding=0.0001)
        return bom.product_uom_id._compute_price(total / bom.product_qty, self.uom_id)
    return 0.0
```

**Recursive component handling:** If a BoM line has a `child_bom_id` and that sub-BoM is in the `boms_to_recompute` list, the cost is computed recursively. This allows updating costs of multi-level BoMs in a single action. Components without a sub-BoM in the recompute list use their current `standard_price`.

**Byproduct modes:**
- **Finished product mode** (`byproduct_bom=False`): Deducts the total byproduct cost share from the finished product's cost, then divides by the BoM quantity.
- **Byproduct mode** (`byproduct_bom=True`): Computes the per-unit cost of a specific byproduct by applying its cost share proportion to the total BoM cost, then dividing by the byproduct's quantity.

**UoM conversion:** Applied at each level — component UoM to the line's UoM, then BoM's UoM to the product's UoM. `round=False` preserves fractional costs through conversions.

**Skips:** `_skip_bom_line` and `_skip_operation_line` evaluate whether a line should be included based on the product, quantity, and other conditions. These come from the base `mrp` module.

---

### 12. `product.category` — Production Account Property

**File:** `mrp_account/models/product.py`

Extends `product.category` with the production valuation account.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `property_stock_account_production_cost_id` | Many2one (`account.account`) | Company-dependent property field (`company_dependent=True`). Used as the valuation counterpart for manufacturing operations. `ondelete='restrict'` prevents accidental deletion while MOs reference it. `check_company=True`. |

This account is debited when components are consumed (component value leaves inventory) and credited when finished products are received into stock. The name `production_cost` reflects the Odoo convention that production-related accounts track the cost of goods manufactured. The `property_stock_account_production_cost_id` also serves as the WIP overhead account fallback in the WIP wizard (`_get_overhead_account()`) when the company has no dedicated `account_production_wip_overhead_account_id`.

---

### 13. `stock.move` — Production Valuation

**File:** `mrp_account/models/stock_move.py`

Extends `stock.move` for production-specific valuation and kit pricing.

#### Method: `_get_value_from_production(quantity, at_date=None)`

Called when a stock move is valued from its production order (rather than from standard receipt/delivery valuation). Returns a value dictionary:

```python
def _get_value_from_production(self, quantity, at_date=None):
    self.ensure_one()
    if not self.production_id:
        return super()._get_value_from_production(quantity, at_date)
    value = quantity * self.price_unit
    return {
        'value': value,
        'quantity': quantity,
        'description': self.env._(
            '%(value)s for %(quantity)s %(unit)s from %(production)s',
            value=self.company_currency_id.format(value),
            quantity=quantity,
            unit=self.product_id.uom_id.name,
            production=self.production_id.display_name,
        ),
    }
```

For moves originating from a production (`self.production_id`), it uses `price_unit` directly — which has been set by `_cal_price` during MO completion. Falls back to the parent implementation for non-production moves.

#### Method: `_get_all_related_sm(product)`

Extends the parent's related moves collection to include phantom (kit) BoM component moves:

```python
def _get_all_related_sm(self, product):
    moves = super()._get_all_related_sm(product)
    return moves | self.filtered(
        lambda m:
        m.bom_line_id.bom_id.type == 'phantom' and
        m.bom_line_id.bom_id == moves.bom_line_id.bom_id
    )
```

Adds moves for components of phantom kits associated with the same parent BoM line. The `moves.bom_line_id.bom_id` access assumes all moves in `moves` share the same BoM — if they don't, this could produce incorrect results.

#### Method: `_get_kit_price_unit(product, kit_bom, valuated_quantity)` (L3 Core)

Overrides kit (phantom BoM) price unit computation for production moves:

```python
def _get_kit_price_unit(self, product, kit_bom, valuated_quantity):
    total_price_unit = 0
    component_qty_per_kit = defaultdict(float)
    for line in exploded_lines:
        component_qty_per_kit[line[0].product_id] += line[1]['qty']
    for component, valuated_moves in self.grouped('product_id').items():
        price_unit = super(StockMove, valuated_moves)._get_price_unit()
        qty_per_kit = component_qty_per_kit[component] / kit_bom.product_qty
        total_price_unit += price_unit * qty_per_kit
    return total_price_unit / valuated_quantity if not product.uom_id.is_zero(valuated_quantity) else 0
```

The factor `qty_per_kit / valuated_quantity` distributes the component cost proportionally across the kit's build quantity. Without this override, the base `stock_account` module would use a simple component average that does not account for kit structure.

---

## Wizard: `mrp.account.wip.accounting`

**File:** `mrp_account/wizard/mrp_wip_accounting.py`
**Model:** `mrp.account.wip.accounting` (TransientModel)

Posts a Work-in-Progress journal entry for manufacturing orders that are in progress, capturing the value of consumed components and workorder overhead at a specific point in time.

### Wizard Fields

| Field | Type | Description |
|-------|------|-------------|
| `date` | Date | Effective date of the WIP journal entry. Default: current datetime. |
| `reversal_date` | Date | Date for the automatic reversal entry. Computed as `date + 1 day`, editable. |
| `journal_id` | Many2one (`account.journal`) | Journal for the WIP entry. Required. Defaults from `property_stock_journal` on product category. |
| `reference` | Char | Memo/ref on the journal entry. Defaults to MO names or "Manual Entry". |
| `mo_ids` | Many2many (`mrp.production`) | MOs to include. Pre-filtered to `state in ['progress', 'to_close', 'confirmed']`. |
| `line_ids` | One2many (`mrp.account.wip.accounting.line`) | Computed WIP journal entry lines. |

### Line Model: `mrp.account.wip.accounting.line`

| Field | Type | Description |
|-------|------|-------------|
| `account_id` | Many2one (`account.account`) | Target account. |
| `label` | Char | Description for the line. |
| `debit` | Monetary | Debit amount. Mutually exclusive with credit. |
| `credit` | Monetary | Credit amount. Mutually exclusive with debit. |
| `currency_id` | Many2one (`res.currency`) | Company currency. |

**Constraint:** `CHECK (debit = 0 OR credit = 0)` — a line cannot be both debit and credit simultaneously. Implemented as a SQL-level constraint for database enforcement.

**Compute methods:** `_compute_debit` and `_compute_credit` enforce mutual exclusivity at the ORM level — setting one automatically zeros out the other.

### Wizard Methods

**`default_get(fields)`**

Filters active MOs. Draft, cancelled, and done MOs are excluded from the selection:

```python
productions = productions.filtered(lambda mo: mo.state in ['progress', 'to_close', 'confirmed'])
```

If no applicable MOs exist, the wizard still opens — the `reference` defaults to "Manual Entry" and `_get_line_vals` generates balanced zero-amount entries.

**`_get_overhead_account()`**

Resolves the overhead account in priority order:
1. `self.env.company.account_production_wip_overhead_account_id` — company-specific overhead account.
2. Falls back to `property_stock_account_production_cost_id` on the product category.

If neither is set, returns `False`, which causes the wizard to fail with a `ValidationError` when trying to create the journal entry line with a null `account_id`.

**`_get_line_vals(productions=False, date=False)`**

Computes WIP values for the selected MOs at a specific date:

```python
compo_value = sum(
    ml.quantity_product_uom * (
        ml.product_id.lot_valuated and ml.lot_id
        and ml.lot_id.standard_price
        or ml.product_id.standard_price
    )
    for ml in productions.move_raw_ids.move_line_ids
    .filtered(lambda ml: ml.picked and ml.quantity and ml.date <= date)
)
overhead_value = productions.workorder_ids._cal_cost(date)
```

**Component value:** Sum of picked move lines with `date <= WIP date`. Uses lot-specific valuation if the product uses lot-level valuation (`lot_valuated`). Non-picked lines and zero-quantity lines are excluded.

**Overhead value:** Sum of workorder costs (actual or expected time x rate) up to the WIP date, using `_cal_cost(date)` which filters time intervals.

**Journal entry lines generated (3 lines per WIP posting):**
1. **Credit: Stock Valuation** (component value) — removes component value from inventory, recognizes it as WIP.
2. **Credit: WIP Overhead** (overhead value) — captures workcentre costs as WIP overhead.
3. **Debit: WIP Account** (`account_production_wip_account_id` on company) — the WIP asset account.

The WIP account is the company's dedicated manufacturing WIP account. Its debit balance represents the total work-in-progress value.

**`confirm()`**

Posts the WIP entry and automatically posts its reversal:

```python
move = self.env['account.move'].sudo().create({...})
move._post()
move._reverse_moves(default_values_list=[{
    'ref': _("Reversal of: %s", self.reference),
    'wip_production_ids': self.mo_ids.ids,
    'date': self.reversal_date,
}])._post()
```

The reversal clears the WIP and restores the balance. The `wip_production_ids` on the reversal entry allows traceability from both entries back to the MO.

### L3 — Wizard Edge Cases

- **No applicable MOs**: Wizard opens with empty `mo_ids`. `_get_line_vals` is called with empty productions — both values compute to zero, generating balanced zero-amount entries. This is intentional (creates a traceable "Manual Entry" journal entry pair).
- **WIP date in the past**: Component value is computed only for move lines with `date <= wizard.date`. Overhead uses `workorder_ids._cal_cost(date)` which filters time intervals by the given date.
- **Reversal date validation**: `reversal_date <= date` raises a `UserError` — reversal must be after the original entry.
- **Balancing validation**: `compare_amounts(sum(credit), sum(debit)) != 0` raises error if debit/credit totals don't match.
- **Multi-company**: The journal, accounts, and MOs all belong to the same company. Mixing companies in a single wizard session would cause errors.
- **WIP date and production state**: The wizard allows posting WIP for `confirmed` MOs (before any work starts). In this case, both component value and overhead value may be zero, producing a zero-entry (still useful for audit trail).

---

## Reports

### MO Overview Report Extension

**File:** `mrp_account/report/mrp_report_mo_overview.py`

**Model:** `report.mrp.report_mo_overview` (inherited)

#### Method: `_get_unit_cost(move)`

For finished moves in `done` state, uses `move._get_price_unit()` instead of the parent's method to get the actual transaction price (which includes workcentre and extra costs set during MO completion):

```python
def _get_unit_cost(self, move):
    if move.state == 'done':
        price_unit = move._get_price_unit()
        return move.product_id.uom_id._compute_price(price_unit, move.product_uom)
    return super()._get_unit_cost(move)
```

For non-done moves, falls back to the parent's estimated cost. The UoM conversion ensures the reported unit is in the move's product UoM, not the product's default UoM.

### Stock Valuation Report Extension

**File:** `mrp_account/report/stock_valuation_report.py`

**Model:** `stock_account.stock.valuation.report` (inherited)

#### Method: `_get_report_data(date, product_category, warehouse)` (Extended)

Adds a `cost_of_production` section to the stock valuation report:

```python
production_locations_valuation_vals = self.env.company._get_location_valuation_vals(
    location_domain=[('usage', '=', 'production')]
)
# Adds 'cost_of_production' to report_data with total debit from production locations
```

The section shows the accumulated debit balance from production location valuations — representing the value of finished goods that have been manufactured but not yet consumed or delivered.

#### Method: `_must_include_cost_of_production()`

Checks if any production location has a valuation account configured:

```python
def _must_include_cost_of_production(self):
    return bool(self.env['stock.location'].search_count([
        ('usage', '=', 'production'),
        ('valuation_account_id', '!=', False),
    ], limit=1))
```

If true, the Cost of Production section is included in the report. This avoids showing an empty section when production locations are not configured for valuation.

---

## Security

### Access Rights

`security/ir.model.access.csv` grants standard CRUD access to the wizard models (`mrp.account.wip.accounting`, `mrp.account.wip.accounting.line`) for all authenticated users.

### View-Level Restrictions

The WIP journal entry button on `mrp.production` requires `account.group_account_user`:
```xml
<button name="action_view_move_wip" groups="account.group_account_user" ...>
```

The `show_valuation` field is marked `invisible` for non-stock-manager users in the view.

### Record Rules

No custom `ir.rule` records are defined in this module. Security relies on:
- The base `account.analytic.account` record rules for analytic distribution.
- The `wip_production_ids` Many2many on `account.move` inherits access from `account.move`.
- The wizard action `action_wip_accounting` restricts access to `account.group_account_user`.

### `sudo()` Usage

Both the wizard's `confirm()` method and `_post_labour()` in `mrp.production` use `sudo()` for `account.move` creation. This is necessary because manufacturing users (who confirm and complete MOs) may not have direct access to accounting journal entries. The privilege is scoped to the single operation.

Analytic line creation in `_create_or_update_analytic_entry_for_record` also uses `sudo()`, following the same pattern.

---

## Test Suite

**Base class:** `TestBomPriceCommon` (from `stock_account` via `TestStockValuationCommon`) provides the full BoM/product/stock valuation infrastructure used across all tests.

**Key fixtures (common setup):**
- `dining_table` (product, std price 1000) with BoM `bom_1` (normal type): 1 table head + 5 screws + 4 legs + 1 glass
- `table_head` with phantom BoM `bom_2`: 12 plywood sheets + 60 bolts + 12 colour + 57 corner slides (per dozen)
- `bom_1` has 3 operations (Cutting/Drilling/Fitting) on a workcenter with `costs_hour=100`
- `bom_1` has 2 byproduct lines for scrap wood (8 units at 1% share, 1 dozen at 12% share = 75% total cost share)
- `account_production` set on production stock locations

### `test_00_production_order_with_accounting`

Confirms the full cost equation: finished move `value = component_costs + workcentre_costs + extra_cost`. Sets `extra_cost=20`, produces qty=1, expects `move_value = 738.75` (718.75 components + 20 extra). Verifies `_cal_price()` absorbs workcentre cost and extra cost into the finished product's valuation layer.

### `test_02_labor_cost_posting_is_not_rounded_incorrectly`

Sets `workcenter.costs_hour = 0.01` and produces qty=1. The workorder duration is 2 seconds. Expected cost: `(2/3600) * 0.01 = 0.00000556`. This test validates that `_post_labour` uses `currency_id.round(wo._cal_cost())` for precise rounding at the company currency level, preventing sub-cent accumulation errors.

### `test_unbuild_account_00`

Creates and completes an MO, then unbuilds it. Validates that the unbuild creates reversal journal entries: finished product move debits the production account (restoring WIP) and credits stock valuation; component moves do the reverse. The `UB/` prefix in move names is used to locate unbuild-related journal entry lines.

### `test_fifo_fifo_1` (valuation layers)

Creates two inbound moves for glass at different prices (10 and 20). Creates MO for qty=2. Produces 1 unit (creates backorder). Validates that:
- Glass total value drops to 20 after first partial production (FIFO: cheapest consumed first)
- After completing backorder: glass total value is 0, finished product value is `2 * PRICE + 10 + 20`

### `test_mrp_user_without_account_permissions_can_create_bom`

Creates an MO as a user with only `mrp.group_mrp_user` (no accounting groups). Calls `button_mark_done()`. Confirms that manufacturing users can complete MOs without explicit accounting permissions — the `sudo()` in `_post_labour` handles the privilege elevation for journal entry creation.

### `test_mo_overview_comp_different_uom`

Sets a component's UoM to a different unit than its product's default UoM (screw uom = pack_6, BoM line uom = unit). Validates that `report.mrp.report_mo_overview` correctly applies UoM conversions when computing BoM price, so the reported `mo_cost` reflects the actual consumed quantities regardless of UoM representation.

---

## L4: Performance, Historical Changes, and Security

### Performance Considerations

| Operation | Impact | Mitigation |
|-----------|--------|------------|
| `_cal_cost()` per workorder | Called per workorder in `_cal_price()` and `_post_labour()`. Iterates over time intervals via `Intervals`. | For MOs with many WOs, cumulative cost is non-trivial but generally fast (<100ms). The estimated vs. actual path branch avoids interval computation when WO is not yet started. |
| `_compute_workorder_count` | Union of two large recordset queries. Could be slow for accounts linked to thousands of workorders. | No pagination or limit. Consider adding a `limit` or cached counter in large deployments. |
| `button_bom_cost` on many products | Recursive BoM traversal. Each component's `standard_price` is a DB read. | Batching in `action_bom_cost` still issues O(products) queries. Prefetching components in a single pass would be more efficient. |
| WIP wizard `_get_line_vals` | Loops over all `move_line_ids` filtered by `date`. For large production runs, this scans many lines. | Filter by `picked=True` and `quantity > 0` reduces scope. Consider adding a company/domain filter. |
| Analytic line creation in `_create_or_update_analytic_entry` | Creates lines on every duration change. High-frequency timer updates (every few seconds) generate many small analytic lines. | Lines are appended (not replaced on every call), which can lead to proliferation of tiny analytic entries. Consider batching into larger time blocks (e.g., daily summaries). |
| `_compute_costs_hour_account_ids` | Parses JSON and browses accounts for every workcenter on every load. With `store=True`, only recomputes on distribution change. | The `.exists()` call after browse adds a WHERE clause that filters deleted records. The JSON key comprehension extracts both account and plan IDs as integers — plan IDs will fail `.exists()` harmlessly but add mild overhead. |
| `_cal_cost()` on large workorders | Uses `Intervals` to sum actual logged time. For workorders with thousands of time intervals, this iterates all intervals. | `_should_estimate_cost()` short-circuits to expected duration when no time is logged, avoiding interval computation for unstarted WOs. |

### Odoo 18 to Odoo 19 Changes

1. **Analytic Distribution JSON**: The `analytic_distribution` field on `mrp.workcenter` (from `analytic.mixin`) changed from the old `analytic_account_ids` one2many pattern to a JSON field in Odoo 16. The `_perform_analytic_distribution` method handles splitting across accounts natively. In Odoo 19, this is fully mature.

2. **WIP Accounting Wizard Redesign**: The wizard posts a WIP entry AND its reversal simultaneously, using `account_production_wip_account_id` and `account_production_wip_overhead_account_id` on the company. The reversal clears the WIP balance when the production is completed. This replaces older approaches that manually cleared WIP or used less structured accounting.

3. **Labour Journal Entry via `_post_labour`**: Replaced older patterns of posting labour costs. The new approach aggregates by expense account (workcenter's `expense_account_id`) and links journal entry lines back to `mrp.workcenter.productivity` records via `account_move_line_id`.

4. **`_post_labour` gated by real-time valuation**: In Odoo 19, `_post_labour` only runs when `product_id.valuation == 'real_time'` AND `production_location.valuation_account_id` is set. If the production location lacks a valuation account, the method silently skips — this prevents errors for non-valuation-tracked products but can silently omit labour costs.

5. **`extra_cost` on Backorders**: The `_get_backorder_mo_vals()` method includes `extra_cost` when creating backorders, ensuring the extra unit cost is preserved across partial production.

6. **Kit Price Unit Override**: The `_get_kit_price_unit` override in `stock.move` distributes component cost proportionally per kit quantity using the explosion factor `qty_per_kit / valuated_quantity`, rather than simple component averaging.

7. **`_configure_journals` post-init hook**: Added in Odoo 19 to handle late installation of `mrp_account` on top of an existing chart of accounts. Iterates companies in `parent_path` order (root companies first) to propagate the production account property from template data without triggering foreign key constraint errors.

### Historical Context

- **Pre-Odoo 13**: MRP accounting was more fragmented. Cost calculation happened in multiple places with less integration to analytic accounting.
- **Odoo 13-15**: Introduction of `analytic.mixin` unified how models expose analytic distribution.
- **Odoo 16**: JSON-based `analytic_distribution` replaced the old `analytic_account_ids` one2many pattern across all models.
- **Odoo 17**: WIP accounting was enhanced with more granular tracking and the wizard redesign began.
- **Odoo 18**: Refinements to labour cost posting and byproduct cost sharing.
- **Odoo 19**: The current architecture with separate WIP posting wizard, `_post_labour` on completion, analytic line generation on workorder duration changes, and BoM cost computation button represents the mature state of manufacturing accounting.

### Security Notes

1. **`sudo()` usage**: The wizard and `_post_labour` use `sudo()` for `account.move` creation. This is necessary because manufacturing users (who confirm and complete MOs) may not have direct access to accounting journal entries. The privilege is scoped to the single operation, and `sudo()` is used only on the specific create call, not on the broader record context.

2. **Analytic line creation with `sudo()`**: `_create_or_update_analytic_entry_for_record` creates analytic lines using `sudo()`. This follows the same pattern — manufacturing users need to record time without needing analytic accounting permissions.

3. **No SQL injection risk**: All dynamic data flows through ORM methods (`search`, `browse`, `read`, `create`, `write`). The `_get_line_vals` method builds values programmatically using field access, not raw SQL concatenation. The `Command.create()` Odoo ORM construct is used for all line creation.

4. **Multi-company concerns**: The `_compute_workorder_count` union `account.workcenter_ids.order_ids | account.production_ids.workorder_ids` does NOT filter by company — it relies on base `account.analytic.account` record rules to restrict visible records. In strict multi-company deployments where a user has access to multiple companies, all workorders across those companies may be aggregated.

5. **WIP reversal and `sudo()`**: The reversal in the wizard's `confirm()` method uses `sudo()` implicitly through `_reverse_moves()`. The reversed entry also gets `wip_production_ids` set, enabling traceability from both the original and reversed entries back to the MO.

6. **Invalid `analytic_distribution` percentages**: The `analytic_distribution` JSON percentages are not validated to sum to 100. An invalid distribution (e.g., summing to 150%) would allocate more than 100% of costs across accounts, potentially causing accounting imbalances.

7. **Cascading delete of productivity records**: `mrp.workcenter.productivity` records are deleted when their parent workorder is unlinked (via base `mrp` cascade). The `account_move_line_id` field on those records then references a non-existent journal entry line — an orphan reference that is not explicitly cleaned up.

8. **Access rights on WIP stat button**: The `action_view_move_wip` button requires `account.group_account_user`. The `show_valuation` field is `invisible` for non-stock-manager users in the view. The WIP wizard action itself is accessible to `account.group_account_manager` only.

---

## Configuration Checklist

To enable manufacturing accounting:

1. **Install** `mrp_account` (auto-installed with `mrp` + `stock_account`). On existing databases, the `_configure_journals` post-init hook propagates `property_stock_account_production_cost_id` from the chart template.
2. **Configure Production Account** on product categories: `property_stock_account_production_cost_id`. This account is the valuation counterpart for component consumption and finished goods receipt. Required for WIP wizard and `_post_labour`.
3. **Configure WIP Account** on company: `account_production_wip_account_id` (the debit target in WIP postings). Required for the WIP wizard.
4. **Configure WIP Overhead Account** on company: `account_production_wip_overhead_account_id`. Optional; falls back to `property_stock_account_production_cost_id` on the product category if not set.
5. **Set Expense Account** on workcenters (or rely on product's expense account via `product_tmpl_id.get_product_accounts()['expense']`). Used by `_post_labour` as the debit target for labour costs.
6. **Set Analytic Distribution** on workcenters (optional — enables analytic line tracking per workcentre). Without it, no `wc_analytic_account_line_ids` entries are created.
7. **Assign Analytic Plans** with `business_domain = 'manufacturing_order'` applicability for mandatory analytic distribution on MOs. Note: BoM and workcenter creation are not blocked by mandatory analytic applicability (test: `test_mandatory_analytic_plan_bom`).
8. **For real-time valuation**: ensure the production location (`stock.location` with `usage = 'production'`) has a `valuation_account_id` set. Required for `_post_labour` to run; if missing, labour costs are silently skipped.

---

## See Also

- [Modules/MRP](MRP.md) — Base manufacturing module (workorders, MOs, BoMs)
- [Modules/stock_account](stock_account.md) — Stock valuation accounting integration
- [Modules/Account](Account.md) — General accounting (journal entries, accounts)
- [Modules/Analytic](analytic.md) — Analytic accounting (distribution, applicability)
- [Core/API](API.md) — ORM decorators used in this module (`@api.depends`, `@api.constrains`)
- [Core/Fields](Fields.md) — Field types: `Json` for analytic distribution, `Many2many` for relations
- [Patterns/Workflow Patterns](Workflow Patterns.md) — MO state machine (`confirmed` -> `progress` -> `done`)
- [Patterns/Security Patterns](Security Patterns.md) — ACL and record rules in multi-company environments

---

*Documented: 2026-04-11*
*Module Version: Odoo 19 (LTS)*
