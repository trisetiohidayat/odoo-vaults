# `mrp.workorder` — Work Order Model

**Source file:** `~/odoo/odoo19/odoo/addons/mrp/models/mrp_workorder.py`
**Model:** `mrp.workorder`
**Description:** Work Order (individual operation within a Manufacturing Order)
**Odoo Version:** 19
**Module:** `mrp` (Manufacturing)
**Tags:** #odoo #odoo19 #mrp #workorder #production #scheduling

---

## Overview

The `mrp.workorder` model represents a single operation or step within a Manufacturing Order (`mrp.production`). It is the fundamental execution unit of production planning and tracking. A manufacturing order may contain zero or more work orders — one per routing operation — that can execute sequentially (via `blocked_by_workorder_ids`) or in parallel on different work centers.

The model governs the full lifecycle: planning in the work center calendar, starting and pausing via productivity time tracking, recording quantities and lots, finishing and closing, and canceling. It is the primary interface between the shop floor operator and Odoo's manufacturing, stock, and cost accounting subsystems.

### Module Dependencies

The `mrp` module depends on `product`, `stock`, and `resource`. The work order specifically touches:
- **`stock`**: Component/consumption moves (`move_raw_ids`), finished product moves (`move_finished_ids`), move lines for lot scanning (`move_line_ids`), scrap records (`scrap_ids`)
- **`resource`**: Calendar-based scheduling via `leave_id` (`resource.calendar.leaves`), time tracking via `mrp.workcenter.productivity`
- **`mrp` (internal)**: Production (`production_id`), routing operations (`operation_id`), work centers (`workcenter_id`)
- **`stock_account`** (optional): Valuation entries generated when moves are confirmed

---

## L1: Complete Field Reference

### Model Definition

```python
class MrpWorkorder(models.Model):
    _name = 'mrp.workorder'
    _description = 'Work Order'
    _order = 'sequence, leave_id, date_start, id'
```

The `_order` matters for list/gantt display: sequence first (routing order), then calendar slot (`leave_id`), then planned start (`date_start`), then creation `id` as tiebreaker.

---

### Identity Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | `Char` (required) | Mirrors `operation_id.name`. Set by `_onchange_operation_id` on WO creation. Can be edited manually. |
| `sequence` | `Integer` (default=`_default_sequence`) | `_default_sequence` returns `self.operation_id.sequence or 100`. Used by `_order` and the gantt view. |
| `barcode` | `Char` (computed, stored) | `compute='_compute_barcode'` → `f"{production_id.name}/{id}"`. Format: `MO/00042/15`. Used for barcode scanning on the shop floor. |
| `display_name` | `Char` (computed) | Format: `"{production_id.name} - {name}"`. With `prefix_product` context: `"{product_id.name} - {production_id.name} - {name}"`. |

---

### Production Linkage

| Field | Type | Notes |
|-------|------|-------|
| `production_id` | `Many2one(mrp.production)` | Required, readonly after creation, `check_company=True`, `index='btree'`. The parent manufacturing order. Cannot be changed after creation (enforced in `write()`). |
| `production_availability` | `Selection` (related, stored) | Mirrors `production_id.reservation_state`. Used in views and domains — not in Python logic. |
| `production_state` | `Selection` (related) | Mirrors `production_id.state`. Technical, views only. |
| `production_bom_id` | `Many2one(mrp.bom)` (related) | `production_id.bom_id`. Source of truth for the BOM revision that generated this WO. |
| `production_date` | `Datetime` (computed, stored) | `compute='_compute_production_date'` → `date_start or production_id.date_start`. Reflects the earliest planned date associated with this operation. |
| `is_planned` | `Boolean` (related) | `production_id.is_planned`. True when any WO in the MO has a calendar slot. |
| `allow_workorder_dependencies` | `Boolean` (related) | `production_id.allow_workorder_dependencies`. Gates the `blocked_by_workorder_ids` domain. |

---

### Product and Quantity

| Field | Type | Notes |
|-------|------|-------|
| `product_id` | `Many2one` (related) | `production_id.product_id` |
| `product_tracking` | `Selection` (related) | `product_id.tracking` — `none`, `lot`, or `serial` |
| `product_uom_id` | `Many2one` (related) | `production_id.product_uom_id` |
| `product_variant_attributes` | `Many2many` (related) | `product_id.product_template_attribute_value_ids` |
| `qty_production` | `Float` (related, readonly) | `production_id.product_qty`. The original production quantity — does not change even when partial orders are produced. |
| `qty_producing` | `Float` (computed/inverse, digits='Product Unit') | The quantity currently being produced. `compute='_compute_qty_producing'` reads from `production_id.qty_producing`. Inverse `_set_qty_producing` writes back to the production and calls `production_id._set_qty_producing(False)`. |
| `qty_remaining` | `Float` (computed, stored, digits='Product Unit') | `compute='_compute_qty_remaining'` → `max(product_uom_id.round(qty_production - qty_reported_from_previous_wo - qty_produced), 0)`. How much remains to be produced by this WO. |
| `qty_produced` | `Float` (default=0.0, stored, copy=False) | Total quantity finished by this work order across all production sessions. Cannot be negative or changed after `done`/`cancel`. |
| `qty_ready` | `Float` (computed, stored) | `compute='_compute_qty_ready'`. Quantity available for this WO to process, determined by predecessor WOs' `qty_produced`. Drives the `blocked` ↔ `ready` state transition. |
| `qty_reported_from_previous_wo` | `Float` (stored, copy=False) | Carried quantity from backorder chain awaiting allocation. Set during backorder creation. |
| `is_produced` | `Boolean` (computed) | `True` when `product_uom_id.compare(qty_produced, qty_production) >= 0`. Used to determine if the MO can be marked done. |

---

### Work Center and Operation

| Field | Type | Notes |
|-------|------|-------|
| `workcenter_id` | `Many2one(mrp.workcenter)` | Required, `index=True`, `check_company=True`. `group_expand='_read_group_workcenter_id'` — allows grouping by work center in list views. |
| `working_state` | `Selection` (related) | `workcenter_id.working_state`. Read-only in views; reflects whether the work center is `available`, `blocked`, or `running`. |
| `operation_id` | `Many2one(mrp.routing.workcenter)` | The routing operation definition. `index='btree_not_null'` (partial index for performance). `check_company=True`. **Warning**: If the BOM is revised, this may reference an operation from an older BOM revision. |

---

### State Machine

| Field | Type | Notes |
|-------|------|-------|
| `state` | `Selection` (computed stored, index) | Options: `blocked` / `ready` / `progress` / `done` / `cancel`. Default `ready`. Copy disabled. `index=True` for fast filtering in gantt/kanban. |

**State transitions:**

```
blocked ──(qty_ready > 0)──> ready
ready ──(button_start)──> progress
progress ──(button_pending)──> ready
progress ──(button_finish)──> done
progress ──(button_pending + reschedule)──> ready
ready/progress ──(action_cancel)──> cancel
ready/progress ──(action_mark_as_done)──> done
```

The `_compute_state` method (triggered by `@api.depends('qty_ready')`) only transitions between `blocked` and `ready` when the current state is one of those two. States `progress`, `done`, and `cancel` are set explicitly by button/action methods and are not auto-transitions.

---

### Scheduling via Calendar (`leave_id`)

| Field | Type | Notes |
|-------|------|-------|
| `leave_id` | `Many2one(resource.calendar.leaves)` | Planned time slot. `check_company=True`, `copy=False`. Created by `_plan_workorder()` or `button_start()`. Unlinking this leave effectively "unplans" the WO. |
| `date_start` | `Datetime` (computed/inverse, stored) | Planned or actual start. Computed from `leave_id.date_from`. Inverse `_set_dates` writes back to `leave_id`. `copy=False`. |
| `date_finished` | `Datetime` (computed/inverse, stored) | Planned or actual end. Computed from `leave_id.date_to`. Inverse `_set_dates` writes back. `copy=False`. |

> **Design Rationale (from code comment):** `date_start` and `date_finished` are not simple related fields — they use explicit compute+inverse. This is because when a WO is dragged in the gantt view, a single `write()` arrives with both fields. The ORM would normally fire the inverse separately for each, causing two `write()` calls on `leave_id`, which would trigger `resource.calendar.leaves`'s `check_dates()` constraint twice with intermediate invalid states. The explicit compute+inverse pair ensures both dates are updated in one coordinated operation.

---

### Duration and Time Tracking

| Field | Type | Notes |
|-------|------|-------|
| `duration_expected` | `Float` (computed, stored, digits=(16,2)) | Planned duration in minutes. `compute='_compute_duration_expected'`, `readonly=False`, `store=True`. Recomputes when `qty_producing` changes (if state is not `done`/`cancel`). |
| `duration` | `Float` (computed/inverse, stored, copy=False) | Real duration in minutes. `compute='_compute_duration'`, `inverse='_set_duration'`. Sum of all `time_ids.duration` plus open-session duration. |
| `duration_unit` | `Float` (computed, stored, aggregator="avg") | `round(duration / max(qty_produced, 1), 2)` — minutes per unit. The aggregator enables Odoo's group-by kanban to show average unit cycle time per WO group. |
| `duration_percent` | `Integer` (computed, stored, aggregator="avg") | `100 * (duration_expected - duration) / duration_expected`. Clamped to `[-2147483648, 2147483647]` to avoid overflow in PostgreSQL integer aggregation. |
| `progress` | `Float` (computed) | `100.0` if `done`; else `duration * 100 / duration_expected`. |
| `time_ids` | `One2many(mrp.workcenter.productivity)` | Time tracking sessions. `copy=False`. Each record is a work session (start-pause-stop). |
| `costs_hour` | `Float` (default=0.0, aggregator="avg") | Frozen hourly cost captured at `button_finish()` time. Preserves costing consistency even if the work center's rate changes later. Falls back to `workcenter_id.costs_hour` when zero. |
| `cost_mode` | `Selection` | `actual` (default) or `estimated`. Controls whether `_cal_cost()` uses real tracked time or expected duration. Set once at MO confirmation via `_set_cost_mode()`. |

---

### Employee and User Tracking

| Field | Type | Notes |
|-------|------|-------|
| `is_user_working` | `Boolean` (computed) | True if the current user has an open productivity line (`date_end=False`) with `loss_type` in (`productive`, `performance`). Used to drive button visibility in the UI (shows "Pause" instead of "Start"). |
| `working_user_ids` | `One2many(res.users)` (computed) | All users with currently open time sessions on this WO. Built from `time_ids.filtered(lambda t: not t.date_end).user_id`. |
| `last_working_user_id` | `Many2one(res.users)` (computed) | The user most recently working on this WO. Falls back to the last closed session's user if no open sessions exist. |

---

### Stock Move Integration

| Field | Type | Notes |
|-------|------|-------|
| `move_raw_ids` | `One2many(stock.move)` | Component moves. Domain: `raw_material_production_id != False AND production_id = False`. Linked at MO confirmation via `_link_workorders_and_moves()`. |
| `move_finished_ids` | `One2many(stock.move)` | Finished product moves. Domain: `raw_material_production_id = False AND production_id != False`. |
| `move_line_ids` | `One2many(stock.move.line)` | Move lines requiring lot/serial scan at this work order. Typically auto-generated during MO reservation. |
| `finished_lot_ids` | `Many2many(stock.lot)` | Lots produced. Related to `production_id.lot_producing_ids`. Domain: `product_id` and `company_id` match. `readonly=False`. |

---

### Scrap Management

| Field | Type | Notes |
|-------|------|-------|
| `scrap_ids` | `One2many(stock.scrap)` | Scrap records linked to this WO. Set by `button_scrap()` wizard context. |
| `scrap_count` | `Integer` (computed) | `compute='_compute_scrap_move_count'`. Uses `_read_group` aggregation for efficiency. |

---

### Work Order Dependencies

| Field | Type | Notes |
|-------|------|-------|
| `blocked_by_workorder_ids` | `Many2many(mrp.workorder)` | WOs that must complete before this one is `ready`. Via table `mrp_workorder_dependencies_rel`, columns `workorder_id`/`blocked_by_id`. Domain restricts to same MO and `allow_workorder_dependencies=True`. |
| `needed_by_workorder_ids` | `Many2many(mrp.workorder)` | Inverse of `blocked_by`. WOs blocked by this one. |

---

### UI and Informational

| Field | Type | Notes |
|-------|------|-------|
| `consumption` | `Selection` (related) | `production_id.consumption` — `flexible` or `strict` (Odoo 19 uses `flexible`/`warning`/`strict`). Controls material consumption validation. |
| `company_id` | `Many2one` (related) | `production_id.company_id`. All critical fields use `check_company=True`. |
| `json_popover` | `Char` (computed) | JSON blob for the web client popover: conflicts, predecessor status, overdue warnings. Rendered via `mrp.workorderPopover` QWeb template. |
| `show_json_popover` | `Boolean` (computed) | Whether the popover should display. True only when `color_icon` is set (i.e., there is a non-primary status to report). |

---

## L2: Field Types, Defaults, Constraints — Why Each Field Exists

### Duration Computation Deep Dive

**`_get_duration_expected()`** is the core duration calculation. It handles two fundamentally different cases:

**Case 1 — No `operation_id` (default cycle time from work center):**
```
setup, cleanup = from workcenter._get_capacity() (overridden by workcenter costs)
duration_expected_working = max(0, (self.duration_expected - setup - cleanup) * time_efficiency / 100)
qty_ratio = qty_producing / qty_production  (proportional scaling)
return setup + cleanup + duration_expected_working * qty_ratio * ratio * 100 / time_efficiency
```
The `ratio` parameter (default 1) is used when syncing WO duration back to the routing operation (`_get_operation_values`). The efficiency factor scales working time but not setup/cleanup.

**Case 2 — With `operation_id` (BOM routing operation):**
```
cycle_number = ceil(qty_production / capacity)
time_cycle = operation_id.time_cycle  (minutes per cycle)
return setup + cleanup + cycle_number * time_cycle * 100 / time_efficiency
```
Capacity is the number of units per cycle from `workcenter_id._get_capacity()`. The cycle is always rounded up with `float_round(..., rounding_method='UP')`.

**Alternative work center planning** (`alternative_workcenter=True` path): The method recomputes capacity using the alternative workcenter's parameters, but uses the current WO's `duration_expected` as the baseline working time. This allows a fair comparison of expected end dates when choosing among alternative work centers.

### `_compute_qty_ready` Logic

This is the critical field for the `blocked`/`ready` state machine:

```python
def _compute_qty_ready(self):
    if self.state in ('cancel', 'done'):
        qty_ready = 0
    elif no blocked_by WOs OR all blocked_by are cancelled:
        qty_ready = qty_remaining
    else:
        # qty available is constrained by ALL predecessors
        qty_ready = qty_remaining + qty_produced
        for wo in blocked_by_workorder_ids:
            if wo.state != 'cancel':
                qty_ready = min(qty_ready,
                    wo.qty_produced + wo.qty_reported_from_previous_wo)
        qty_ready -= qty_produced + qty_reported_from_previous_wo
```

The `qty_reported_from_previous_wo` term is critical in backorder scenarios: it represents quantity already produced in a previous production run but not yet assigned to a specific WO.

### `_set_duration` Inverse — Timeline Reconciliation

When a user manually edits `duration` on a work order form, the inverse setter reconciles the change against the `time_ids` (productivity lines):

- **Increasing duration**: Creates a new productivity line. If the new duration exceeds `duration_expected`, the excess is split into a `performance` loss line (reduced speed) rather than `productive`.
- **Decreasing duration**: Removes or truncates existing productivity lines, processing them oldest-first.
- **Triggering state change**: If the WO was not `progress`/`done`/`cancel` and the duration increased from zero, it auto-transitions to `progress`.

This mechanism allows supervisors to correct time records without deleting individual timeline entries.

### `costs_hour` — Frozen Cost Pattern

At `button_finish()`, the code captures:
```python
'costs_hour': workorder.workcenter_id.costs_hour
```
This freezes the work center's hourly rate at the moment the WO finishes. If the work center's rate is updated retroactively (e.g., union wage increase), already-closed WOs retain their historical rate. The `costs_hour` field defaults to `0.0` on creation and is only populated at finish time, falling back to `workcenter_id.costs_hour` in `_cal_cost()`.

---

## L3: Cross-Model Relationships, Override Patterns, Workflow Triggers, Failure Modes

### `_action_confirm` — Delegated to Production

```python
def _action_confirm(self):
    for production in self.mapped("production_id"):
        production._link_workorders_and_moves()
```

This is the critical cross-model linking method, defined in `mrp.production`. It:

1. **Builds the workorder-per-operation map**: `{operation_id: workorder}`
2. **Wires blocking dependencies**: For each routing operation with a `worksheetBlueprintId`, links `blocked_by` to the operation in `worksheetBlueprintId`. Falls back to linking each operation to its immediate predecessor in the routing sequence.
3. **Links stock moves to work orders**: Sets `workorder_id` on `stock.move` records where `operation_id` matches. This is what makes the "Work Orders" tab on the MO form show the correct moves.

**Failure mode**: If WOs are created manually after MO confirmation (bypassing `_action_confirm`), they will not be linked to stock moves. The `move_raw_ids` and `move_finished_ids` will appear empty. The fix is to re-run `_action_confirm()` on the production.

### `_compute_workorder_ids` on `mrp.production` — WO Lifecycle Management

The production model dynamically manages its workorders in `_compute_workorder_ids`:
- Recomputes when `bom_id` changes
- Deletes WOs whose `operation_id` points to a BOM that is no longer relevant (phantom BOMs, old BOM revisions)
- Creates new WOs for new routing operations added to the BOM
- Calls `_resequence_workorders()` if sequences collide

This means that changing a MO's BOM after it is confirmed will automatically add or remove work orders.

### `_plan_workorder` — Recursive Forward Scheduling

The algorithm for scheduling a work order:

```
_plan_workorder(wo, replan=False):
  if wo.leave_id and not replan: return  # already planned

  date_start = max(production_id.date_start, now)
  for each blocked_by WO:
    _plan_workorder(blocked_by, replan)  # RECURSIVE — plan predecessors first
    if blocked_by.date_finished > date_start:
      date_start = blocked_by.date_finished

  if wo.state not in ('blocked', 'ready'): return  # skip in-progress/done/cancel

  workcenters = wo.workcenter_id | wo.workcenter_id.alternative_workcenter_ids
  for each workcenter:
    from_date, to_date = workcenter._get_first_available_slot(date_start, duration_expected)
    if to_date < best_date_finished:
      best_date_finished = to_date
      best_workcenter = workcenter
      best_from_date = from_date

  create resource.calendar.leaves record on best_workcenter
  write {leave_id, workcenter_id (may differ if alternative selected), duration_expected}
```

Key insight: If multiple alternative work centers can handle the operation, `_plan_workorder` picks the one that would finish the WO earliest (not the one that starts earliest). This is a "minimum makespan" heuristic for the single-WO scheduling problem.

### `_resequence_workorders` — Sequence Collision Resolution

Called from `create()` when multiple WOs share the same `sequence` value. It assigns non-overlapping sequences by finding gaps, and handles phantom BOM components separately (phantom WOs get mixed into the sequence among non-phantom WOs at their routing position).

### `unlink` — Seven-Step Safe Deletion

```python
def unlink(self):
    # 1. Detach stock moves (prevent FK violations on workorder_id)
    (move_raw_ids | move_finished_ids).write({'workorder_id': False})

    # 2. Delete the calendar leave
    leave_id.unlink()

    # 3. Capture affected MOs that need re-confirmation
    mo_dirty = production_id.filtered(lambda mo: mo.state in ("confirmed", "progress", "to_close"))

    # 4. Rewire dependency graph: A.blocks = B; deleting A → B.blocks should still include A's predecessors
    for wo in self:
        wo.blocked_by_workorder_ids.needed_by_workorder_ids = wo.needed_by_workorder_ids

    # 5. Close all open time sessions
    self.end_all()

    # 6. Delete WO records
    res = super().unlink()

    # 7. Re-confirm affected MOs to re-derive work order links
    mo_dirty.workorder_ids._action_confirm()
```

### `button_finish` — Auto-Complete Stock Moves

When finishing a WO:
1. All unpicked component moves (`move_raw_ids`) and by-product moves are auto-filled to the expected quantity (`qty_producing * unit_factor`)
2. The `picked` flag is set to `True`, effectively auto-receiving materials
3. All open time sessions are closed
4. `costs_hour` is frozen from the current work center rate
5. `date_finished` is set to now (or backdated if `date_finished` was already in the past)

**Critical**: The auto-fill uses `production_id.qty_producing` (not `qty_production`) as the basis. If the operator changed `qty_producing` before finishing, the auto-fill reflects the partial quantity.

### `write()` — Extensive Side Effects

The `write()` override handles multiple coordinated updates:

| Triggering field | Side effects |
|-------------------|--------------|
| `qty_produced` | Validates state not `done`/`cancel`, quantity non-negative. Propagates minimum `qty_produced` across all WOs of the same production as `qty_producing`. |
| `workcenter_id` | Updates `leave_id.resource_id` to the new work center's resource. Recomputes `duration_expected` for new work center. If WO was in `progress`, skips recomputation (can't re-plan mid-production). |
| `date_start` (first WO only) | Propagates to `production_id.date_start` via `force_date=True` context |
| `date_finished` (last WO only) | Propagates to `production_id.date_finished` via `force_date=True` context |
| `date_start` + `date_finished` | Auto-recalculates the other via `_calculate_date_finished()` or `_calculate_duration_expected()` unless `bypass_duration_calculation` context is set |

### Quality Integration — Lot/Serial Tracking

The `_onchange_finished_lot_ids()` method calls `production_id._can_produce_serial_numbers()` to validate serial number allocation. This ensures:
- For `tracking='serial'`: Each unit must have exactly one serial number
- For `tracking='lot'`: Lots must match the product and company
- The MO's `lot_producing_ids` and the WO's `finished_lot_ids` are the same recordset (they share the same `Many2many` field)

---

## L4: Performance Implications, Historical Changes, Security, Edge Cases

### Performance Analysis

#### SQL Conflict Detection (`_get_conflicted_workorder_ids`)

```sql
SELECT wo1.id, wo2.id
FROM mrp_workorder wo1, mrp_workorder wo2
WHERE wo1.id IN %s
  AND wo1.state IN ('blocked', 'ready')
  AND wo2.state IN ('blocked', 'ready')
  AND wo1.id != wo2.id
  AND wo1.workcenter_id = wo2.workcenter_id
  AND (DATE_TRUNC('second', wo2.date_start), DATE_TRUNC('second', wo2.date_finished))
      OVERLAPS (DATE_TRUNC('second', wo1.date_start), DATE_TRUNC('second', wo1.date_finished))
```

This uses PostgreSQL's `OVERLAPS` operator for interval intersection. Key performance notes:

- **`DATE_TRUNC('second', ...)`** on both sides: Truncating to seconds before the comparison is necessary because the `leave_id` calendar precision is at second level. Without truncation, microsecond differences would produce false negatives.
- **Batching**: The query uses `tuple(self.ids)` as a single parameterized value, so it fetches all conflicts for a batch of WOs in one query. This is called once in `_compute_json_popover` for the entire batch.
- **`flush_model`**: Called before the raw SQL to ensure all pending writes to the relevant columns (`state`, `date_start`, `date_finished`, `workcenter_id`) are persisted. Without this, the raw SQL could read stale data from the ORM write buffer.
- **Scaling risk**: In a factory with 1000 WOs, the self-join creates a worst-case 1M-row comparison. The `state IN ('blocked', 'ready')` filter and `index='btree'` on `state` and `workcenter_id` help, but on very large deployments this can be a bottleneck. Mitigation: the popover only shows for WOs in `blocked`/`ready` states.

#### Stored Computed Fields with Aggregators

`duration_unit`, `duration_percent`, and `costs_hour` carry `aggregator="avg"`. In Odoo, this means their values are stored in `ir_property` and recalculated via `read_group` when WOs are displayed in kanban group-by views. The aggregator is primarily for the Odoo web client's kanban card grouping feature — it is NOT a database aggregate and does not auto-update on every write. The actual values are computed by the `_compute_*` methods.

#### `qty_ready` Prefetch Optimization

The `_compute_qty_ready` method iterates over `blocked_by_workorder_ids` (a many2many). The ORM's prefetch mechanism ensures that when this is computed on a recordset of N WOs, all blocking WO records are loaded in one batch query, and all `qty_produced` values are prefetched in a second pass. The per-WO Python loop then operates entirely in memory.

#### Calendar Slot Planning Cost

`_get_first_available_slot()` on `resource.calendar` performs a calendar-aware availability search. For work centers with complex shift patterns (multiple shifts, overtime, leave), this involves:
1. Querying `resource.calendar.attendance` for working hours
2. Querying `resource.calendar.leaves` for blocking time
3. Iterating through available slots to find the first gap large enough for `duration_expected`

When alternative work centers are involved, this is called up to `1 + len(alternative_workcenter_ids)` times. For a full MO replan, `_plan_workorders()` calls this for every WO that needs planning.

### Odoo 17 → 18 → 19 Changes

#### Odoo 17 → 18 Key Changes
- Work order dependencies (`blocked_by_workorder_ids`) were significantly enhanced, adding the `qty_ready` based blocking/ready transition and the dependency graph rewiring in `unlink()`
- The `json_popover` feature (conflict detection, predecessor status, overdue warnings) was introduced to give real-time status alerts directly on work orders

#### Odoo 18 → 19 Key Changes
- **`time_ids` separation**: In Odoo 17, time tracking used `resource.calendar.leaves` for both scheduling and time capture. In Odoo 18/19, `mrp.workcenter.productivity` is the dedicated time-tracking model; `resource.calendar.leaves` (`leave_id`) is purely for scheduling. This removes interference between planning slots and actual time capture.
- **Cost mode**: The `cost_mode` field (`actual` vs `estimated`) and associated methods were restructured to support both actual and estimated costing at the work order level.
- **`qty_reported_from_previous_wo`**: Refined to correctly handle backorder chains where partial production quantities need to flow through the WO dependency chain.
- **`display_name` with context prefix**: The `_compute_display_name` method with `prefix_product` context key was introduced for more descriptive naming in multi-product MO scenarios.
- **`working_state` related field**: The `working_state` field was added as a direct related field to `workcenter_id.working_state` for use in view domains and kanban card coloring.

### Security Model

#### Access Control
`mrp.workorder` access is governed by:
- `ir.model.access.csv` entries in the `mrp` module
- Record rules (computed via `_read_group_workcenter_id`'s use of `ir.rule._compute_domain()`)
- The `_read_group_workcenter_id` group expand method uses `sudo()` internally to bypass `ir.model.access` checks (since group expand runs without a specific user context in some scenarios), but applies record rules for security filtering

#### Multi-Company Compliance
`check_company=True` is set on `production_id`, `workcenter_id`, `operation_id`, `leave_id`, and `finished_lot_ids`. The `company_id` is derived from the parent `production_id`, ensuring that:
- WOs always belong to the same company as their parent MO
- Scrap records inherit the MO's company
- Stock moves linked to the WO respect company boundaries

#### SQL Injection Prevention
The raw SQL in `_get_conflicted_workorder_ids` uses parameterized queries (`%s` with `tuple(self.ids)`). The `flush_model` call before the raw SQL ensures that the ORM write buffer is flushed before the raw SELECT reads the table.

#### Cyclic Dependency Prevention
`_check_no_cyclic_dependencies` uses `self._has_cycle('blocked_by_workorder_ids')`, which internally builds the directed graph of WO dependencies and checks for cycles using a depth-first search. A cycle in blocking dependencies would cause infinite recursion in `_compute_qty_ready` and `_plan_workorder`.

### Edge Cases

#### Zero-Duration Work Orders
If `button_finish()` is called on a WO where `duration == 0.0`, `action_mark_as_done()` sets `duration = duration_expected` and `duration_percent = 100`. This handles the case of instantaneous operations (e.g., a quality check that always passes).

#### Bom Revision After MO Creation
`operation_id` may reference a routing operation from a BOM revision that no longer matches `production_id.bom_id`. The code comment explicitly flags this: *"Should be used differently as BoM can change in the meantime."* WOs created under an older BOM revision retain their `operation_id` reference even after the BOM is updated.

#### Unplanning a Single Work Order
Both `_set_dates` and `_onchange_date_finished` raise `UserError` if the user tries to clear `date_finished` while `date_start` is still set. The error message directs users to unplan the entire MO instead. This prevents orphaned `leave_id` records.

#### Splitting MO During Production
When `qty_producing` is changed mid-WO, `duration_expected` is automatically recalculated (`_compute_duration_expected` depends on `qty_producing`). If the WO is already `in progress`, the duration does not auto-update — the operator would need to manually adjust or replan.

#### Phantom BOM Work Orders
`_resequence_workorders()` processes phantom BOM WOs separately, interleaving them with non-phantom WOs at their routing operation position. Phantom WOs represent exploded sub-assemblies and should appear in sequence among real operations.

#### Cross-Company Scrap
`button_scrap()` passes `default_company_id` from the production's company. Scrap records for WOs respect multi-company constraints via the `stock.scrap` model's `company_id` field.

---

## Method Reference

| Method | Signature | Purpose |
|--------|-----------|---------|
| `_default_sequence` | `(self) → int` | Return `operation_id.sequence or 100` |
| `_read_group_workcenter_id` | `(workcenters, domain) → recordset` | Group expand for `workcenter_id` with record-rule filtering |
| `_compute_state` | `(self)` | Auto-transition `blocked` ↔ `ready` based on `qty_ready > 0` |
| `set_state` | `(self, state)` | Generic state transition dispatcher with pre/post hooks |
| `_compute_production_date` | `(self)` | `date_start or production_id.date_start` |
| `_compute_json_popover` | `(self)` | Build popover JSON with conflict/pred/overdue info |
| `_compute_qty_producing` | `(self)` | Read `production_id.qty_producing` |
| `_set_qty_producing` | `(self)` | Inverse: write back to production and call `_set_qty_producing(False)` |
| `_compute_qty_ready` | `(self)` | Compute available quantity constrained by predecessor WOs |
| `_compute_dates` | `(self)` | Read `leave_id.date_from/to` |
| `_set_dates` | `(self)` | Inverse: write to `leave_id` or create it |
| `_check_no_cyclic_dependencies` | `(self)` | `@constrains` on `blocked_by_workorder_ids` |
| `_compute_barcode` | `(self)` | `"{production_id.name}/{id}"` |
| `_compute_display_name` | `(self)` | Formatted name with optional product prefix |
| `unlink` | `(self) → bool` | Safe deletion: detach moves, delete leave, rewire deps, re-confirm MOs |
| `_compute_is_produced` | `(self)` | `qty_produced >= qty_production` |
| `_compute_duration_expected` | `(self)` | Recompute when `qty_producing` changes (if not done/cancel) |
| `_compute_duration` | `(self)` | Sum `time_ids` + open session; compute unit/percent |
| `_set_duration` | `(self)` | Inverse: create/delete/split productivity lines |
| `_compute_progress` | `(self)` | `100 if done else duration/duration_expected` |
| `_compute_working_users` | `(self)` | Track current/last working users |
| `_compute_scrap_move_count` | `(self)` | Count scrap records via `_read_group` |
| `_onchange_operation_id` | `(self)` | Auto-fill `name` and `workcenter_id` from routing operation |
| `_onchange_date_start` | `(self)` | Auto-update `date_finished` via calendar |
| `_onchange_date_finished` | `(self)` | Recompute `duration_expected` from date range |
| `_onchange_finished_lot_ids` | `(self)` | Validate serial number allocation |
| `write` | `(self, vals) → bool` | Override with qty propagation, MO date sync, leave/workcenter updates |
| `create` / `@api.model_create_multi` | `(self, vals_list)` | Create WOs, auto-resequence, auto-confirm if MO is confirmed |
| `_action_confirm` | `(self)` | Delegate to `production_id._link_workorders_and_moves()` |
| `_get_byproduct_move_to_update` | `(self) → recordset` | Filter non-finished by-product moves |
| `_plan_workorder` | `(self, replan=False)` | Forward-schedule using calendar, deps, alternatives |
| `_cal_cost` | `(self, date=False)` | Total operation cost using actual or estimated time |
| `button_start` | `(self, raise_on_invalid_state=False)` | Start WO, create productivity line, create leave if unplanned |
| `button_finish` | `(self)` | Auto-fill moves, close sessions, freeze cost, set done |
| `end_previous` | `(self, doall=False)` | Close open time sessions (current user or all) |
| `end_all` | `(self)` | `end_previous(doall=True)` |
| `button_pending` | `(self)` | Pause: close current user's open sessions |
| `button_unblock` | `(self)` | Unblock the work center (`workcenter_id.unblock()`) |
| `action_cancel` | `(self)` | Unlink leave, end sessions, set cancel |
| `action_replan` | `(self)` | Trigger `production_id._plan_workorders(replan=True)` |
| `button_scrap` | `(self)` | Open `stock.scrap` wizard with WO context |
| `action_see_move_scrap` | `(self)` | Open scrap list filtered to this WO |
| `action_open_wizard` | `(self)` | Open WO form via `mrp.mrp_workorder_mrp_production_form` action |
| `_compute_qty_remaining` | `(self)` | `max(qty_production - qty_reported_from_previous_wo - qty_produced, 0)` |
| `_get_duration_expected` | `(self, alternative_workcenter=False, ratio=1)` | Core duration formula with/without operation_id |
| `_get_conflicted_workorder_ids` | `(self) → defaultdict` | Raw SQL overlap detection using PostgreSQL OVERLAPS |
| `_get_operation_values` | `(self) → dict` | Prepare vals for syncing WO back to routing operation |
| `_prepare_timeline_vals` | `(self, duration, date_start, date_end=False)` | Create `mrp.workcenter.productivity` dict |
| `_should_start_timer` | `(self) → bool` | Hook for auto-start behavior (default `True`) |
| `_should_estimate_cost` | `(self) → bool` | `state in ('progress','done') and duration_expected and cost_mode == 'estimated'` |
| `_update_qty_producing` | `(self, quantity)` | On-the-fly `qty_producing` update |
| `get_working_duration` | `(self) → float` | Duration of open (no `date_end`) productivity lines |
| `get_duration` | `(self) → float` | Sum of all `time_ids.duration` + open session duration |
| `action_mark_as_done` | `(self)` | Mark done with workcenter unblock check; set duration if zero |
| `_compute_expected_operation_cost` | `(self, without_employee_cost=False)` | `(duration_expected / 60) * costs_hour` |
| `_compute_current_operation_cost` | `(self)` | `(get_duration() / 60) * costs_hour` |
| `_get_current_theorical_operation_cost` | `(self, without_employee_cost=False)` | Alias for `_compute_current_operation_cost` |
| `_set_cost_mode` | `(self)` | Set `cost_mode` from `operation_id.cost_mode or 'actual'` |
| `_calculate_date_finished` | `(self, date_start=False, new_workcenter=False)` | Compute end date from start + calendar |
| `_calculate_duration_expected` | `(self, date_start=False, date_finished=False)` | Compute duration from date range and calendar |

---

## Related Wizard Models

### `mrp.production.serial` — Assign Serial Numbers to Production

**File:** `~/odoo/odoo19/odoo/addons/mrp/wizard/mrp_production_serial_numbers.py`

| Field | Type | Notes |
|-------|------|-------|
| `production_id` | `Many2one(mrp.production)` | Parent production |
| `workorder_id` | `Many2one(mrp.workorder)` | Optional — the WO requesting serial numbers |
| `lot_name` | `Char` (computed, store, readonly=False) | First serial number, auto-generated from product's lot sequence |
| `lot_quantity` | `Integer` (computed, store, readonly=False) | Number of serial numbers to generate |
| `serial_numbers` | `Text` (computed, store, readonly=False) | Multi-line list of SNs, deduplicated on change |

**Key methods:**
- `action_generate_serial_numbers()`: Generates a range of serial numbers using `stock.lot.generate_lot_names()`, updates `serial_numbers`, then re-runs the deduplication onchange
- `action_apply()`: Creates or reuses `stock.lot` records, assigns them to `production_id.lot_producing_ids`, updates `production_id.qty_producing` to the count of assigned lots, then calls `set_qty_producing()` on the work order or production

### `mrp.consumption.warning` — Flexible/Strict Consumption Validation

**File:** `~/odoo/odoo19/odoo/addons/mrp/wizard/mrp_consumption_warning.py`

Triggered when a MO is being marked done and material consumption exceeds the BOM-expected amount. The wizard presents a table of lines showing `product_consumed_qty_uom` vs. `product_expected_qty_uom`.

- `action_set_qty()`: Resets all over-consumed moves to the expected quantity and re-triggers MO completion
- `action_cancel()`: Returns to the production form if called from a work order context (`from_workorder` in context)
- `action_confirm()`: Forces MO completion with `skip_consumption=True`

---

## Cross-Module Integration Map

```
mrp.production
  ├─ creates ─→ mrp.workorder (via _compute_workorder_ids)
  ├─ confirms → _link_workorders_and_moves (wires stock.move ↔ workorder)
  ├─ plans ───→ _plan_workorders → _plan_workorder (calendar scheduling)
  ├─ finishes → button_finish on each WO
  ├─ backorder → copies workorders with qty_reported_from_previous_wo
  └─ reserves ─→ generates move_line_ids for lot scanning at each WO

mrp.workorder
  ├─ consumes ─→ stock.move (move_raw_ids, move_finished_ids)
  ├─ tracks ───→ mrp.workcenter.productivity (time_ids)
  ├─ schedules → resource.calendar.leaves (leave_id)
  ├─ scrap ────→ stock.scrap (scrap_ids)
  ├─ produces ─→ stock.lot (finished_lot_ids = production_id.lot_producing_ids)
  ├─ blocks ────→ self (blocked_by_workorder_ids)
  ├─ costs ────→ mrp.workcenter (costs_hour frozen at finish)
  └─ reports ───→ mrp.production (updates qty_produced, duration)

mrp.workcenter
  ├─ hosts ─────→ mrp.workorder (order_ids)
  ├─ capacity ──→ _get_capacity (determines cycle_number in duration formula)
  ├─ calendar ──→ _get_first_available_slot (used in planning)
  ├─ costs ──────→ costs_hour (used in _cal_cost)
  ├─ alternatives → alternative_workcenter_ids (tried in _plan_workorder)
  └─ time efficiency → time_efficiency (applied in duration formula)

stock.move
  ├─ workorder_id ── set by _link_workorders_and_moves
  ├─ unit_factor ──── used by button_finish for auto-fill qty
  └─ picked ───────── set True by button_finish

stock.scrap
  ├─ workorder_id ── set by button_scrap wizard context
  └─ location_id ──── defaults from workorder.production_id.location_src_id

mrp.workcenter.productivity
  ├─ workorder_id ── created by button_start, _set_duration
  ├─ loss_id ──────── productive or performance type
  └─ duration ─────── summed into workorder.duration

stock.lot
  └─ generated by mrp.production.serials wizard action_apply
     └─ assigned to production_id.lot_producing_ids
        └─ displayed in workorder.finished_lot_ids
```

---

## Frontmatter Tags

```yaml
---
tags: [#odoo, #odoo19, #mrp, #workorder, #manufacturing, #scheduling, #time-tracking, #quality-control]
related:
  - Modules/MRP
  - Core/Fields
  - Core/API
  - Patterns/Workflow Patterns
---
```
