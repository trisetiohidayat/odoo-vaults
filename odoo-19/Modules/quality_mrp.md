---
tags:
  - odoo
  - odoo19
  - modules
  - mrp
  - quality
  - quality_control
  - enterprise
---

# quality_mrp

> Integrates Quality Control into Manufacturing: attaches quality checks and alerts to manufacturing orders and their work orders, enforcing that all quality gates pass before a production order can be marked done.

## Quick Facts

| Property | Value |
|----------|-------|
| **Module ID** | `quality_mrp` |
| **Type** | **Enterprise Edition (EE)** — not available in Community |
| **Location** | `enterprise/<vendor>/quality_mrp/` |
| **Odoo Version** | 19+ |
| **License** | OEEL-1 (Odoo Enterprise Edition License) |
| **Category** | Manufacturing / Quality |
| **Depends** | `quality_control`, `mrp` |
| **Auto-install** | True |
| **ERP Usage** | Quality checks on MO work orders, component consumption, finished goods |

---

## Purpose

`quality_mrp` integrates the Quality Control module (`quality_control`) into the Manufacturing module (`mrp`). Its primary roles are:

1. **Attach quality checks to MOs**: When an MO is confirmed or its moves are confirmed, automatically generate quality checks (inspection points) based on active quality control points configured for the production.
2. **Attach alerts to MOs**: Allow quality alert creation directly from a manufacturing order.
3. **Enforce checks before completion**: Block MO completion (`button_mark_done`) until all quality checks are passed.
4. **Work order checks**: Trigger quality checks at the work order (operation) level, not just at receipt/delivery.

Unlike `quality_control_stock` (which works at the stock.move level for incoming/outgoing shipments), `quality_mrp` operates at the manufacturing-specific layers: MO, work order, and component consumption.

---

## Dependencies

```python
'depends': ['quality_control', 'mrp']
```

| Dependency | Role |
|------------|------|
| `quality_control` | Base quality module: `quality.point`, `quality.check`, `quality.alert`, check teams, worksheets |
| `mrp` | Manufacturing: `mrp.production`, `mrp.workorder`, `stock.move` |

The module also indirectly benefits from `quality_control_stock` (which is typically a dependency of `quality_control`) for the underlying `stock.move` quality check hooks.

---

## Inheritance Chain

```
mrp.production        (from mrp)
    └── MrpProduction  (extends mrp.production)     ← check_ids, alert_ids, block on done

quality.point         (from quality_control)
    └── QualityPoint   (extends quality.point)      ← _get_domain_for_production()

quality.check         (from quality_control)
    └── QualityCheck   (extends quality.check)      ← production_id, lot/qty compute overrides

quality.alert         (from quality_control)
    └── QualityAlert   (extends quality.alert)      ← production_id field

stock.move            (from stock)
    └── StockMove      (extends stock.move)         ← _action_confirm hook, _create_quality_checks_for_mo

stock.move.line       (from stock)
    └── StockMoveLine  (extends stock.move.line)    ← lot propagation, check value injection
```

---

## Models

### `mrp.production` — Extended

**File:** `models/mrp_production.py`

#### Fields Added

| Field | Type | Purpose |
|-------|------|---------|
| `check_ids` | `One2many(quality.check, production_id)` | All quality checks linked to this MO. |
| `quality_check_todo` | `Boolean` (computed) | `True` if any check has `quality_state == 'none'` (not yet done). |
| `quality_check_fail` | `Boolean` (computed) | `True` if any check has `quality_state == 'fail'`. |
| `quality_alert_ids` | `One2many(quality.alert, production_id)` | All quality alerts raised from this MO. |
| `quality_alert_count` | `Integer` (computed) | Count of open alerts. |

#### Computed Methods

##### `_compute_check()`

Scans `check_ids`. Sets `quality_check_todo = True` if any check is still `none`; sets `quality_check_fail = True` if any check has failed. Both flags are used by the MO form header to visually indicate QC status.

##### `_compute_quality_alert_count()`

Simply returns `len(production.quality_alert_ids)`.

#### Action Methods

##### `button_mark_done()` — **blocking override**

The most critical method. Before delegating to `super()`, it checks that no quality check on the MO has `quality_state == 'none'`. If any check is still pending, raises `UserError`: "You still need to do the quality checks!" This prevents a production from being completed without all QC gates passed.

```python
def button_mark_done(self):
    for order in self:
        if any(x.quality_state == 'none' for x in order.check_ids):
            raise UserError(_('You still need to do the quality checks!'))
    return super().button_mark_done()
```

##### `button_quality_alert()`

Opens the quality alert creation wizard with `production_id`, `product_id`, and `product_tmpl_id` pre-filled from the MO.

##### `open_quality_alert_mo()`

Opens a filtered list of quality alerts linked to this MO. If exactly one alert exists, opens its form directly.

##### `check_quality()`

Opens the quality check wizard for all pending checks (`quality_state == 'none'`) on the MO. If there are pending checks, returns `checks.action_open_quality_check_wizard()`.

##### `action_cancel()`

When an MO is cancelled, also removes (via `sudo()`) all pending quality checks (`quality_state == 'none'`) linked to the MO. Passed or failed checks are preserved for audit trail.

```python
def action_cancel(self):
    res = super().action_cancel()
    self.sudo().mapped('check_ids').filtered(
        lambda x: x.quality_state == 'none').unlink()
    return res
```

##### `_action_confirm_mo_backorders()`

After MO confirmation (including backorder creation), triggers `_create_quality_checks_for_mo()` on all moves (raw materials + finished goods). This ensures new quality checks are generated for the backorder MO.

```python
def _action_confirm_mo_backorders(self):
    super()._action_confirm_mo_backorders()
    (self.move_raw_ids | self.move_finished_ids)._create_quality_checks_for_mo()
```

---

### `stock.move` — Extended

**File:** `models/stock_move.py`

This is where automatic check generation hooks into the move lifecycle.

#### Method: `_action_confirm()`

Extends the base confirm hook. After `super()._action_confirm()`, calls `_create_quality_checks_for_mo()` on all confirmed moves.

```python
def _action_confirm(self, merge=True, merge_into=False):
    moves = super()._action_confirm(merge=merge, merge_into=merge_into)
    moves._create_quality_checks_for_mo()
    return moves
```

#### Method: `_search_quality_points(product_id, picking_type_id, measure_on)`

Searches applicable quality points for a given product/picking type combination, then passes through `_get_domain_for_production()` (the hook on `QualityPoint`). This allows quality points to be filtered by production-specific criteria.

#### Method: `_create_quality_checks_for_mo()` — **core generation logic**

This is the main automatic check generation method. It processes all confirmed moves that belong to an MO (`move.production_id`).

**Step 1 — Product-type checks**: For each MO's moves, search quality points with `measure_on = 'product'`. Also search for `measure_on = 'move_line'` points (since move lines for the manufactured product are created too late in the flow, these are handled specially here, excluding by-products).

**Step 2 — Operation-type checks**: For each MO, search quality points with `measure_on = 'operation'` (these are triggered at the work order level, not per move). If `check_execute_now()` returns `True` for an operation point, create a check immediately.

**Step 3 — Create checks**: Collect all check values and call `sudo().create()` to create the `quality.check` records linked to the MO.

```python
def _create_quality_checks_for_mo(self):
    mo_moves = defaultdict(lambda: self.env['stock.move'])
    check_vals_list = []

    for move in self:
        if move.production_id and not move.scrapped:
            mo_moves[move.production_id] |= move

    # QC of product type + move_line type
    for production, moves in mo_moves.items():
        quality_points = self._search_quality_points(...)
        quality_points_lot_type = self._search_quality_points(production.product_id, ..., 'move_line')
        quality_points = quality_points | quality_points_lot_type
        if not quality_points:
            continue
        mo_check_vals_list = quality_points._get_checks_values(...)
        for check_value in mo_check_vals_list:
            check_value.update({'production_id': production.id})
        check_vals_list += mo_check_vals_list

    # QC of operation type
    for production, moves in mo_moves.items():
        quality_points_operation = self._search_quality_points(..., 'operation')
        for point in quality_points_operation:
            if point.check_execute_now():
                check_vals_list.append({
                    'point_id': point.id, 'team_id': point.team_id.id,
                    'measure_on': 'operation', 'production_id': production.id,
                })

    self.env['quality.check'].sudo().create(check_vals_list)
```

---

### `stock.move.line` — Extended

**File:** `models/stock_move_line.py`

#### Method: `write()`

When a `lot_id` is written to a move line that has associated quality checks, propagates the lot to those checks of type `register_consumed_materials` or `register_byproducts`. This ensures that when a user assigns a lot during component consumption, the QC record automatically captures it.

```python
def write(self, vals):
    res = super().write(vals)
    if vals.get('lot_id') and self.check_ids:
        self.check_ids.filtered(
            lambda qc: qc.test_type in ('register_consumed_materials', 'register_byproducts')
        ).lot_id = vals['lot_id']
    return res
```

#### Method: `_get_check_values(quality_point)`

Adds `production_id` to the check values dict when a quality check is triggered from a move line. The production ID is sourced from either `move_id.production_id` (finished product move) or `move_id.raw_material_production_id` (component move).

#### Method: `_get_quality_points_all_products(quality_points_by_product_picking_type)`

Returns an empty set when the move line is a raw material consumption (`raw_material_production_id` is set), preventing duplicate check generation for component moves that would otherwise be caught by the `quality_control_stock` logic.

#### Method: `_create_quality_check_at_write()`

Returns `False` (skip creation) when the move line is linked to an MO (either as finished product or raw material), since these are handled by `_create_quality_checks_for_mo()` on `stock.move` instead.

#### Method: `_filter_move_lines_applicable_for_quality_check()`

Includes move lines that are raw material consumption moves (`ok_lines = sml.move_id.raw_material_production_id`), plus done lines that represent the finished product, in the applicable set for quality checks.

---

### `quality.point` — Extended

**File:** `models/quality.py`

#### Method: `_get_domain_for_production(quality_points_domain)`

A thin hook that returns the domain unchanged. Exists to allow sub-modules (e.g., `quality_mrp_workorder`) to add production-specific filtering to quality point domains. By default, no additional filtering is applied here.

---

### `quality.check` — Extended

**File:** `models/quality.py`

#### Fields Added

| Field | Type | Purpose |
|-------|------|---------|
| `production_id` | `Many2one(mrp.production)` | Links the check to the source MO. `check_company=True`. |

#### Method: `_compute_qty_line()`

Overrides the base method. For checks linked to a production (`production_id` is set), uses the MO's `qty_producing` as the check quantity instead of the move line quantity. For checks without a production, delegates to `super()`.

```python
def _compute_qty_line(self):
    record_without_production = self.env['quality.check']
    for qc in self:
        if qc.production_id:
            qc.qty_line = qc.production_id.qty_producing
        else:
            record_without_production |= qc
    return super(QualityCheck, record_without_production)._compute_qty_line()
```

#### Method: `_compute_lot_line_id()`

Overrides the base method. For checks of type `register_consumed_materials` or `register_byproducts`, skips the special MO-specific logic. For other checks where the check's product matches the MO's finished product and the MO has a lot being produced, sets `lot_line_id` and `lot_id` from the MO's `lot_producing_id`.

---

### `quality.alert` — Extended

**File:** `models/quality.py`

#### Fields Added

| Field | Type | Purpose |
|-------|------|---------|
| `production_id` | `Many2one(mrp.production)` | Links the alert to the source MO. `check_company=True`. |

---

## Business Flow

```
1. MO Confirmed
   → move_raw_ids + move_finished_ids created
   → stock.move._action_confirm() fires
   → _create_quality_checks_for_mo() generates quality.check records
     per quality.point configured for the product/operation

2. During Production
   → Operator works on work orders
   → Operator consumes components (stock.move.line records created)
   → Lot assignment on move line propagates to QC check via write()
   → Operator can open pending checks: mrp_production.check_quality()
   → Operator passes/fails each check

3. Before MO Completion
   → button_mark_done() checks: any check.state == 'none'?
   → If YES: raises UserError — completion blocked
   → If NO: MO completes

4. Alert Creation
   → button_quality_alert() creates quality.alert linked to MO
   → alert visible in MO form header (quality_alert_count)
```

---

## Key Design Decisions

### Why `auto_install: True`?

The module is marked `auto_install: True` because when `quality_control` and `mrp` are both present in the system, the bridge should activate transparently. Quality checks on manufacturing should not require a separate manual installation step.

### Blocking vs. Non-blocking Checks

Only `button_mark_done()` is blocked by pending checks. An MO can progress through `confirmed` → `progress` → `done` in terms of raw state transitions, but the `done` button itself is gated. This is the same pattern used in quality-controlled stock picks.

### Sudo() for Check Creation

`quality.check` records are created with `sudo()` because the user performing the production operation may not have direct quality team access. The check records are properly security-grouped through `quality.point.team_id` and `quality.alert.team_id`.

### Component Move Lines vs. Quality Control Stock

`stock.move.line` has special logic to avoid double-generating checks: when a move line is a raw material consumption (linked to `raw_material_production_id`), `_get_quality_points_all_products()` returns empty (skip) and `_create_quality_check_at_write()` returns `False` (skip). This prevents the base `quality_control_stock` logic from firing on top of the MO-specific logic in `quality_mrp`.

### Preservation of Check Audit Trail

When an MO is cancelled (`action_cancel()`), only pending checks (`quality_state == 'none'`) are deleted. Passed and failed checks are preserved, maintaining a complete quality audit trail even for cancelled production orders.

---

## Views

| File | Contents |
|------|----------|
| `views/quality_views.xml` | Quality point, check, and alert views adjusted for MRP context |
| `views/mrp_production_views.xml` | Quality smart buttons and status indicators on MO form |
| `report/worksheet_custom_report_templates.xml` | Worksheet report templates for MRP quality checks |

---

## Security

| File | Contents |
|------|----------|
| `security/quality_mrp.xml` | Record rules restricting quality checks/alerts to the MO's company |

The module uses the `quality_control` security model: quality checks belong to a `quality.team`, and access is controlled through team membership. The `production_id` field carries `check_company=True` to enforce multi-company restrictions.

---

## See Also

- [Modules/quality](quality.md) — base quality module (quality.point, quality.check, quality.alert)
- [Modules/quality_mrp](quality_mrp.md) — quality checks on stock moves (incoming/outgoing)
- [Modules/quality](quality.md) — quality management overview
- [Modules/mrp](MRP.md) — manufacturing core (`mrp.production`, `mrp.workorder`)
- [Modules/purchase_mrp](purchase_mrp.md) — purchase-MO bridge (Community Edition)
- [Core/API](API.md) — `@api.depends`, `@api.onchange` patterns used in computed fields
