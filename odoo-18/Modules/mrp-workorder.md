---
Module: mrp
Version: Odoo 18
Type: Core
Tags: #mrp #workorder #workcenter #manufacturing #production #routing #time-tracking
Related: [[Modules/MRP]], [[Modules/Stock]]
---

# mrp — Manufacturing Work Orders

> **Odoo path:** `addons/mrp/models/mrp_workorder.py`, `mrp_workcenter.py`, `mrp_routing.py`
> **Depends:** `mrp`, `resource`
> **License:** LGPL-3

## Overview

The MRP work order system is the core Odoo manufacturing execution layer. Work orders (`mrp.workorder`) are individual operation steps defined on a BoM's routing (via `mrp.routing.workcenter`) and scheduled onto work centers (`mrp.workcenter`). Time tracking is recorded via `mrp.workcenter.productivity` logs. Work order state machine has 5 states with dependency-based sequencing, and work centers have capacity planning via resource calendars.

**Note:** In Odoo 18, `mrp_workorder` is not a separate addon — it is the `mrp_workorder.py` model inside the `mrp` module.

---

## Model: `mrp.workorder`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Work order name (from operation_id or auto-generated) |
| `sequence` | Integer | Order within MO; default from `operation_id.sequence` or 100 |
| `barcode` | Char | Computed: `"{production_id.name}/{id}"`; used for barcode scanning |
| `workcenter_id` | Many2one `mrp.workcenter` | Required; target work center; expandable via group |
| `working_state` | Selection | Related from `workcenter_id.working_state`; `'normal'/'blocked'/'done'` |
| `product_id` | Many2one `product.product` | Related from `production_id.product_id`; stored |
| `product_tracking` | Selection | Related from `product_id.tracking` |
| `product_uom_id` | Many2one `uom.uom` | Required; the unit for qty fields |
| `production_id` | Many2one `mrp.production` | Required; parent MO; indexed btree; readonly |
| `production_availability` | Selection | Related from `production_id.reservation_state`; `'assigned'/'waiting'/'confirmed'` |
| `production_state` | Selection | Related from `production_id.state` |
| `production_bom_id` | Many2one `mrp.bom` | Related from `production_id.bom_id` |
| `qty_production` | Float | Original MO quantity; related from `production_id.product_qty` |
| `company_id` | Many2one `res.company` | Related from `production_id.company_id` |
| `qty_producing` | Float | Current quantity being produced; computed from MO's qty_producing; inverse writes MO |
| `qty_remaining` | Float | Quantity still to produce; computed: `max(qty_production - qty_reported - qty_produced, 0)` |
| `qty_produced` | Float | Total units completed by this work order; default 0.0; readonly |
| `is_produced` | Boolean | True when `qty_produced >= qty_production` |
| `state` | Selection | Computed (stored): `pending/waiting/ready/progress/done/cancel`; readonly; indexed |
| `leave_id` | Many2one `resource.calendar.leaves` | Links WO to workcenter calendar slot; created when WO is planned |
| `date_start` | Datetime | Computed from `leave_id.date_from`; inverse creates/updates `leave_id` |
| `date_finished` | Datetime | Computed from `leave_id.date_to`; inverse creates/updates `leave_id` |
| `duration_expected` | Float | Expected duration in minutes; computed from operation/workcenter; writable |
| `duration` | Float | Actual duration from time_ids; computed+inverse; copy=False |
| `duration_unit` | Float | Average duration per unit; computed: `duration / max(qty_produced, 1)` |
| `duration_percent` | Integer | Deviation %: `100 * (duration_expected - duration) / duration_expected`; aggregated avg |
| `progress` | Float | % done: `duration * 100 / duration_expected`; 100% if done |
| `operation_id` | Many2one `mrp.routing.workcenter` | Routing operation definition; nullable (WO can be ad-hoc) |
| `has_worksheet` | Boolean | True if `operation_id.worksheet` is set (PDF/binary or Google Slide URL) |
| `worksheet` | Binary | Related from `operation_id.worksheet` |
| `worksheet_type` | Selection | Related: `'pdf'/'google_slide'/'text'` |
| `worksheet_google_slide` | Char | Related Google Slide URL |
| `operation_note` | Html | Related from `operation_id.note` |
| `move_raw_ids` | One2many `stock.move` | Raw material moves for this WO; domain: `raw_material_production_id!=False, production_id=False` |
| `move_finished_ids` | One2many `stock.move` | Finished product moves; domain: `raw_material_production_id=False, production_id!=False` |
| `move_line_ids` | One2many `stock.move.line` | Move lines to track lot numbers at this WO |
| `finished_lot_id` | Many2one `stock.lot` | Lot/serial for finished product; domain on product_id and company; writes to production_id |
| `time_ids` | One2many `mrp.workcenter.productivity` | Time tracking logs for this WO; copy=False |
| `is_user_working` | Boolean | True if current user has open time_id with `loss_type in (productive, performance)` |
| `working_user_ids` | One2many `res.users` | All users currently working on this WO (open time_ids) |
| `last_working_user_id` | One2many `res.users` | Last user who worked on this WO (sorted by `date_end` or `date_start`) |
| `costs_hour` | Float | Hourly cost captured at WO completion; stored snapshot of workcenter rate; aggregated avg |
| `scrap_ids` | One2many `stock.scrap` | Scrap records for this WO |
| `scrap_count` | Integer | Count of scrap moves |
| `production_date` | Datetime | `date_start` or fallback to `production_id.date_start`; used in workcenter load reporting |
| `json_popover` | Char | JSON for UI popover warnings (conflict, scheduling issues) |
| `show_json_popover` | Boolean | Whether popover should display |
| `consumption` | Selection | Related: `'flexible'/'strict'/'prevent'` from MO |
| `qty_reported_from_previous_wo` | Float | Carried-over quantity from prior WO in backorder chain |
| `is_planned` | Boolean | Related from MO |
| `allow_workorder_dependencies` | Boolean | Related from MO |
| `blocked_by_workorder_ids` | Many2many `mrp.workorder` | Self-referential: workorders that must complete before this one starts; `column1=workorder_id, column2=blocked_by_id` |
| `needed_by_workorder_ids` | Many2many `mrp.workorder` | Inverse of blocked_by: workorders this one blocks |

### Work Order States

| State | Label | Condition |
|-------|-------|-----------|
| `pending` | Waiting for another WO | Components assigned AND (blocked_by WOs not all done OR blocked_by WOs still pending) |
| `waiting` | Waiting for components | Components not assigned AND (blocked_by all done OR no blocked_by) |
| `ready` | Ready | Components assigned AND all blocked_by WOs done/cancel |
| `progress` | In Progress | Timer started via `button_start()` |
| `done` | Finished | `button_finish()` or `button_done()` called |
| `cancel` | Cancelled | `action_cancel()` called |

### State Computation (`_compute_state`)

```
if state not in (pending, waiting, ready): keep current
if production_availability == 'assigned':
    if all(blocked_by WOs are done/cancel): state = 'ready'
    else: state = 'pending'
else (waiting for components):
    if no blocked_by or all blocked_by done/cancel: state = 'waiting'
    else: state = 'pending'
```

### Key Methods

| Method | Description |
|--------|-------------|
| `button_start(raise_on_invalid_state=False)` | Start WO: validate workcenter not blocked; set `qty_producing`; create `mrp.workcenter.productivity` timer if `_should_start_timer()`; transition to `progress`; create `leave_id` if missing |
| `button_finish()` | Finish WO: auto-set move quantities from `unit_factor`; call `end_all()`; set `qty_produced`; set `state='done'`; capture `costs_hour`; handle `date_start` edge case |
| `button_done()` | Validate MO not already done/cancel; call `end_all()`; set `state='done'`, `date_finished`, `costs_hour` |
| `button_pending()` | Call `end_previous()` (closes current user's open timer) |
| `button_unblock()` | Unblock the workcenter via `workcenter_id.unblock()` |
| `action_cancel()` | Unlink `leave_id`, call `end_all()`, set `state='cancel'` |
| `action_replan()` | Call `production_id._plan_workorders(replan=True)` for all linked MOs |
| `action_mark_as_done()` | Call `button_finish()`; if `duration==0`, set `duration=duration_expected` and `duration_percent=100` |
| `end_previous(doall=False)` | Close open timers; if `doall=True`, close all; else close only current user's open timer |
| `end_all()` | Call `end_previous(doall=True)` — close all open timers |
| `_plan_workorder(replan=False)` | Schedule WO on workcenter calendar; respects blocked_by dependencies (recursively plans predecessors); searches workcenter + alternatives for first available slot |
| `_action_confirm()` | Called on creation of WO for confirmed/in-progress MOs; calls `production_id._link_workorders_and_moves()` |
| `button_scrap()` | Opens scrap wizard with WO context and product filter |
| `_update_finished_move()` | Syncs finished move line with lot_id and qty_producing; creates or updates move lines for tracked products |
| `_get_conflicted_workorder_ids()` | SQL query finds WOs overlapping in time at same workcenter; used for popover warnings |

### Planning Algorithm (`_plan_workorder`)

1. Start from `max(production_id.date_start, now)`
2. For each `blocked_by_workorder_ids`: recursively plan those first; push start date to after all of them finish
3. Check state: skip if not in `pending/waiting/ready`
4. If `leave_id` exists and not `replan`: return
5. Search `workcenter_id` + `alternative_workcenter_ids` for earliest available slot using `_get_first_available_slot(duration)`
6. Pick the workcenter that finishes earliest (best fit)
7. Create `resource.calendar.leaves` entry on that workcenter's calendar
8. Write `leave_id`, `workcenter_id`, `duration_expected` to WO

### Time Tracking Methods

| Method | Description |
|--------|-------------|
| `_compute_duration()` | `duration = sum(time_ids.duration)`, `duration_unit = duration/max(qty_produced,1)`, `duration_percent = 100*(expected-actual)/expected` |
| `_set_duration(duration)` | When duration is manually changed: if increasing, create new `mrp.workcenter.productivity` (possibly split into productive + performance); if decreasing, remove/split time_ids from oldest to newest |
| `_prepare_timeline_vals(duration, date_start, date_end=False)` | Creates productivity log dict; uses `'productive'` loss type if duration <= expected, else `'performance'` |
| `_should_start_timer()` | Returns `True`; hook for extensions to add conditions |
| `get_working_duration()` | Duration from open (no `date_end`) timers: `(now - time.date_start).total_seconds() / 60` |
| `get_duration()` | `sum(time_ids.duration) + get_working_duration()` |

### Duration Calculation (`_get_duration_expected`)

Formula (without operation_id):
```
working_time = (duration_expected - workcenter.time_start - workcenter.time_stop) * time_efficiency / 100
qty_ratio = qty_producing / qty_production (if qty_producing differs from qty_production)
return workcenter._get_expected_duration(product) + working_time * qty_ratio * ratio * 100 / time_efficiency
```

Formula (with operation_id):
```
cycle_number = ceil(qty_production / capacity)
return workcenter._get_expected_duration(product) + cycle_number * operation_id.time_cycle * 100 / time_efficiency
```

### Constraints

| Constraint | Description |
|------------|-------------|
| `_check_no_cyclic_dependencies` | Raises `ValidationError` if `blocked_by_workorder_ids` creates a cycle |
| Cannot change `workcenter_id` when state is `progress/done/cancel` |
| Cannot change `production_id` to a different MO |
| `date_finished` must be after `date_start` |

---

## Model: `mrp.workcenter`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Related from `resource_id.name`; stored; mutable |
| `time_efficiency` | Float | Related from `resource_id.time_efficiency`; default 100% |
| `active` | Boolean | Related from `resource_id.active` |
| `code` | Char | Optional code |
| `note` | Html | Description |
| `default_capacity` | Float | Pieces produced in parallel (1.0 = one at a time); must be > 0 |
| `sequence` | Integer | Display order |
| `color` | Integer | Kanban color |
| `currency_id` | Many2one `res.currency` | Related from company |
| `costs_hour` | Float | Hourly processing cost; tracked |
| `time_start` | Float | Setup time in minutes |
| `time_stop` | Float | Cleanup time in minutes |
| `routing_line_ids` | One2many `mrp.routing.workcenter` | Operations that use this workcenter |
| `has_routing_lines` | Boolean | True if any routing lines exist |
| `order_ids` | One2many `mrp.workorder` | All work orders |
| `workorder_count` | Integer | Total non-done/cancel WOs |
| `workorder_ready_count` | Integer | WOs in `ready` state |
| `workorder_progress_count` | Integer | WOs in `progress` state |
| `workorder_pending_count` | Integer | WOs in `pending` state |
| `workorder_late_count` | Integer | WOs in pending/waiting/ready with `date_start < now` |
| `time_ids` | One2many `mrp.workcenter.productivity` | Time logs |
| `working_state` | Selection | `'normal'/'blocked'/'done'`; computed from open productivity logs |
| `blocked_time` | Float | Hours blocked in last month (non-productive time logs) |
| `productive_time` | Float | Hours productive in last month |
| `oee` | Float | Overall Equipment Effectiveness: `productive_time * 100 / (productive_time + blocked_time)` |
| `oee_target` | Float | Target OEE %; default 90 |
| `performance` | Integer | % of expected vs actual duration for last month WOs |
| `workcenter_load` | Float | Total expected duration for open WOs in minutes |
| `alternative_workcenter_ids` | Many2many `mrp.workcenter` | Other workcenters that can substitute this one (no self-reference) |
| `tag_ids` | Many2many `mrp.workcenter.tag` | Tags for filtering |
| `capacity_ids` | One2many `mrp.workcenter.capacity` | Product-specific capacity overrides |
| `kanban_dashboard_graph` | Text | JSON for dashboard chart |
| `resource_calendar_id` | Many2one `resource.calendar` | Work hours; check_company |

### Working State Computation

- `working_state = 'normal'`: No open productivity log found
- `working_state = 'done'`: Open log found with `loss_type in ('productive', 'performance')`
- `working_state = 'blocked'`: Open log found with other loss types

### Key Methods

| Method | Description |
|--------|-------------|
| `unblock()` | Write `date_end=now` on all open productivity logs; requires `working_state=='blocked'` |
| `_get_unavailability_intervals(start, end)` | Returns unavailability from resource calendar and leave intervals |
| `_get_first_available_slot(start_datetime, duration, forward=True, ...)` | Finds earliest calendar slot for `duration` minutes; searches up to 700 days; skips conflicting WO intervals; returns `(start_datetime, end_datetime)` or `(False, 'error message')` |
| `_get_capacity(product)` | Returns `capacity_ids` specific capacity or `default_capacity` |
| `_get_expected_duration(product_id)` | Returns product-specific `time_start + time_stop` or generic `time_start + time_stop` |
| `_compute_kanban_dashboard_graph()` | Pre-computes load data for 5 weeks (past + future) for kanban view |

### Constraint

`_check_capacity`: `default_capacity > 0`

---

## Model: `mrp.routing.workcenter`

> Also known as: **Work Order Operation** or **Routing Line**

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Operation name; required |
| `active` | Boolean | Archivable |
| `workcenter_id` | Many2one `mrp.workcenter` | Required; check_company |
| `sequence` | Integer | Display order within BOM; default 100 |
| `bom_id` | Many2one `mrp.bom` | Required; cascade delete; check_company; indexed |
| `company_id` | Many2one `res.company` | Related from `bom_id` |
| `worksheet_type` | Selection | `'pdf'/'google_slide'/'text'`; default `'text'` |
| `note` | Html | Description/worksheet instructions |
| `worksheet` | Binary | PDF worksheet attachment |
| `worksheet_google_slide` | Char | Google Slide embed URL |
| `time_mode` | Selection | `'auto'` (compute from past WOs) or `'manual'` (use time_cycle_manual); default `'manual'` |
| `time_mode_batch` | Integer | Number of past WOs to average for auto time; default 10 |
| `time_computed_on` | Char | `'Computed on last N work orders'` or False if manual |
| `time_cycle_manual` | Float | Manual duration in minutes; default 60 |
| `time_cycle` | Float | Computed or manual cycle duration in minutes |
| `workorder_count` | Integer | Count of done WOs for this operation |
| `workorder_ids` | One2many `mrp.workorder` | All WOs created from this operation |
| `possible_bom_product_template_attribute_value_ids` | Many2many | Related from `bom_id` |
| `bom_product_template_attribute_value_ids` | Many2many | Variants required to apply this operation |
| `allow_operation_dependencies` | Boolean | Related from `bom_id` |
| `blocked_by_operation_ids` | Many2many `mrp.routing.workcenter` | Operations that must complete before this one |
| `needed_by_operation_ids` | Many2many `mrp.routing.workcenter` | Operations blocked by this one |

### Time Cycle Computation (`_compute_time_cycle`)

- If `time_mode == 'manual'`: `time_cycle = time_cycle_manual`
- If `time_mode == 'auto'`:
  1. Query last `time_mode_batch` done WOs for this operation (ordered by `date_finished desc`)
  2. For each WO, get `duration` from productivity logs and `qty_produced`; adjust for capacity
  3. `cycle_number = ceil(qty_produced / capacity)` (capacity=1 if unknown)
  4. `time_cycle = total_duration / cycle_number`
  5. Fall back to `time_cycle_manual` if no data

### Key Methods

| Method | Description |
|--------|-------------|
| `_skip_operation_line(product)` | Returns True if operation should be skipped: archived OR product variant mismatch |
| `_get_duration_expected(product, quantity, unit, workcenter)` | Computes expected time: `workcenter_expected + cycle_number * time_cycle * 100 / efficiency` |
| `_compute_operation_cost(op_duration=None)` | Returns `(duration/60) * costs_hour` |
| `_check_no_cyclic_dependencies()` | Prevents cyclic `blocked_by_operation_ids` |

### BoM Line Integration

When archiving a routing workcenter, `bom_line_ids` with `operation_id == self` have their `operation_id` set to `False`. Same for `byproduct_ids`.

---

## Model: `mrp.workcenter.productivity` — Time Tracking Log

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `production_id` | Many2one `mrp.production` | Related from `workorder_id.production_id` |
| `workcenter_id` | Many2one `mrp.workcenter` | Required; indexed |
| `company_id` | Many2one `res.company` | Required; default from WO or WC or env.company |
| `workorder_id` | Many2one `mrp.workorder` | Nullable; indexed |
| `user_id` | Many2one `res.users` | Default: current user |
| `loss_id` | Many2one `mrp.workcenter.productivity.loss` | Required; `ondelete='restrict'` |
| `loss_type` | Selection | Related: `'availability'/'performance'/'quality'/'productive'` |
| `description` | Text | Free-text note |
| `date_start` | Datetime | Required; default: `now` |
| `date_end` | Datetime | Nullable; set when WO stops |
| `duration` | Float | Computed from date_end - date_start; respects workcenter calendar for non-productive losses |

### Loss Types (via `mrp.workcenter.productivity.loss.type`)

| Type | Label | Used For |
|------|-------|----------|
| `availability` | Availability | Planned/unplanned downtime, machine breakdown |
| `performance` | Performance | Slower than expected speed |
| `quality` | Quality | Defects, rework |
| `productive` | Productive | Good production time |

### `_close()` — Auto-Split Performance Losses

When a timer is closed:
1. Write `date_end = now`
2. If `wo.duration > wo.duration_expected`: excess time is a performance loss
   - Compute `productive_date_end = date_end - (duration - duration_expected)`
   - If `productive_date_end <= date_start`: entire timer becomes performance loss
   - Otherwise: split into productive (date_start to productive_date_end) + performance (productive_date_end to date_end)

### `_loss_type_change()` Onchange

When duration is changed (via onchange): if `workorder_id.duration > workorder_id.duration_expected`, switch loss to performance type; otherwise productive.

---

## Model: `mrp.workcenter.productivity.loss`

Predefined loss reasons with sequence, manual flag, and category.

### Model: `mrp.workcenter.productivity.loss.type`

Categories: `availability`, `performance`, `quality`, `productive`. `display_name` is title-cased from `loss_type`.

---

## Model: `mrp.workcenter.capacity`

Product-specific capacity overrides for a workcenter.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `workcenter_id` | Many2one `mrp.workcenter` | Required |
| `product_id` | Many2one `product.product` | Required |
| `product_uom_id` | Many2one `uom.uom` | Related from `product_id.uom_id` |
| `capacity` | Float | Default 1.0; pieces in parallel for this product; must be > 0 |
| `time_start` | Float | Product-specific setup time; defaults from `workcenter_id.time_start` |
| `time_stop` | Float | Product-specific cleanup time; defaults from `workcenter_id.time_stop` |

### Constraint

`UNIQUE(workcenter_id, product_id)`

---

## Scheduling and Sequencing

### WO-to-Operation Linking

When a WO is created or an MO is confirmed, `production_id._link_workorders_and_moves()` connects WOs to the raw/finished moves they consume/produce. This uses `workorder_id` on `stock.move` records.

### Operation Dependencies (BoM-level)

On `mrp.routing.workcenter`:
- `blocked_by_operation_ids`: other operations in the same BoM that must finish first
- Self-referential Many2many with `mrp_routing_workcenter_dependencies_rel` table

### WO Dependencies (MO-level)

On `mrp.workorder`:
- `blocked_by_workorder_ids`: other WOs in the same MO that must finish first
- `needed_by_workorder_ids`: inverse
- Self-referential via `mrp_workorder_dependencies_rel`
- Only active when `production_id.allow_workorder_dependencies` is True
- Cannot create cycles (constraint)

### Work Center Capacity Planning

- Each workcenter has a `resource_calendar_id` defining working hours
- `_get_first_available_slot()` returns the earliest contiguous slot of required duration
- WOs are planned onto the resource calendar via `leave_id` (`resource.calendar.leaves`)
- Conflicting WOs (same time, same workcenter) are detected via SQL in `_get_conflicted_workorder_ids()`

---

## L4: Work Order Integration with MRP Scheduling

### MO Confirmation Triggers WO Creation

When `mrp.production.action_confirm()` is called:
1. `workorder_ids` are created from BoM routing operations
2. For each routing workcenter with `blocked_by_operation_ids`, WOs get `blocked_by_workorder_ids` set accordingly
3. If `production_id.is_planned` is true, `_plan_workorders()` is called immediately

### Planning Cascade

- MO's `date_start` → first WO's `date_start`
- Each WO's `date_finished` → next WO's `date_start` (if blocked_by)
- Last WO's `date_finished` → MO's `date_finished`
- When WO's `date_start` is updated (first WO), MO's `date_start` is updated
- When WO's `date_finished` is updated (last WO), MO's `date_finished` is updated

### Alternative Workcenters in Scheduling

During `_plan_workorder()`:
1. Collect `workcenter_id` + all `alternative_workcenter_ids`
2. For each, compute earliest available slot via `_get_first_available_slot()`
3. Select the slot with the earliest `date_finished`
4. If the chosen workcenter differs from `self.workcenter_id`, write new `workcenter_id` and recompute `duration_expected`

### Cost Calculation

Work order cost is captured per WO via `costs_hour` (snapshot at finish time):
- Expected cost: `(duration_expected / 60) * (costs_hour or workcenter_id.costs_hour)`
- Actual cost: `(get_duration() / 60) * (costs_hour or workcenter_id.costs_hour)`

---

## L4: Quality Checks at Work Orders

Quality checks are not in the core `mrp` module. They live in `quality` (`quality.point`, `quality.check`) and are integrated via the `mrp_workorder` → `quality` module relationship:

1. `quality.point` records can have `operation_id` (routing workcenter) or `workcenter_id` set
2. `stock.picking.type` can be linked to quality checklists for in-process QC
3. WO completion triggers quality check creation (via `mrp.action_finished` / `button_finish`)
4. The `quality` module provides a `mrp.workorder` kanban with quality status

The WO's `move_line_ids` field holds the lines where QC should record lot numbers. Serial-number tracking (`product_tracking == 'serial'`) forces lot selection at WO start.

---

## File Map

| File | Models |
|------|--------|
| `mrp/models/mrp_workorder.py` | `mrp.workorder` |
| `mrp/models/mrp_workcenter.py` | `mrp.workcenter`, `mrp.workcenter.tag`, `mrp.workcenter.productivity.loss.type`, `mrp.workcenter.productivity.loss`, `mrp.workcenter.productivity`, `mrp.workcenter.capacity` |
| `mrp/models/mrp_routing.py` | `mrp.routing.workcenter` |