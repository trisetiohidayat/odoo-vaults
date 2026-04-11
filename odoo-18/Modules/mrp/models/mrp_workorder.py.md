# MRP Workorder - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/mrp/models/mrp_workorder.py`
**Lines:** ~923

---

## Model Overview

`mrp.workorder` represents a single operation step in a manufacturing order, tied to a workcenter. It handles timing, resource scheduling, quality checks, and blocking dependencies between operations.

---

## Fields

| Field | Type | Notes |
|---|---|---|
| `production_id` | Many2one | `mrp.production`; parent manufacturing order |
| `workcenter_id` | Many2one | `mrp.workcenter`; assigned workcenter |
| `operation_id` | Many2one | `mrp.routing.workcenter`; routing operation reference |
| `name` | Char | Operation name (from operation_id or manual) |
| `state` | Selection | `'pending'`, `'waiting'`, `'ready'`, `'progress'`, `'done'`, `'cancel'` |
| `company_id` | Many2one | `res.company` |
| `product_id` | Many2one | `product.product`; derived from production_id |
| `product_tracking` | Char | `'serial'`/`'lot'`/`'none'`; from product_id |
| `production_bom_id` | Many2one | `mrp.bom`; derived from production_id.bom_id |
| `operation_note` | Text | Instructions from routing |
| `planned_hours` | Float | Planned duration in hours |
| `duration` | Float | Actual duration (seconds) |
| `duration_unit` | Float | Duration per unit |
| `duration_percent` | Integer | Efficiency percentage (0-100) |
| `qty_producing` | Float | Quantity currently being produced at this step |
| `qty_produced` | Float | Total quantity already completed |
| `cycle_count` | Float | Number of production cycles |
| `number_of_cycles` | Float | Computed: qty_produced / workcenter capacity |
| `qty_rejected` | Float | Rejected units |

### Timing
| Field | Type | Notes |
|---|---|---|
| `date_start` | Datetime | Actual/planned start |
| `date_finished` | Datetime | Actual/planned end |
| `date_planned_start` | Datetime | Scheduled start |
| `date_planned_finished` | Datetime | Scheduled end |

### Dependencies
| Field | Type | Notes |
|---|---|---|
| `blocked_by_workorder_ids` | Many2many | `mrp.workorder`; operations that must complete first |
| `needed_by_workorder_ids` | Many2many | `mrp.workorder`; operations that depend on this one |
| `allow_workorder_dependencies` | Boolean | Enable dependency checking |

### Resource Tracking
| Field | Type | Notes |
|---|---|---|
| `working_user_ids` | Many2many | `res.users`; currently working users |
| `last_worker_id` | Many2one | `res.users`; last user who worked on this |

### Quality
| Field | Type | Notes |
|---|---|---|
| `quality_check_ids` | One2many | `mrp.workorder.line`; quality checks |
| `quality_alert_ids` | One2many | `quality.alert`; raised alerts |
| `is_produced` | Boolean | Whether the WO has been produced |

---

## State Machine

```
pending -> waiting -> ready -> progress -> done
    \                                  \
     \-> cancel                        \-> cancel
```

- **`pending`**: Not yet ready; waiting for production to start.
- **`waiting`**: Dependencies (blocked_by) not yet completed.
- **`ready`**: Dependencies satisfied; ready to start.
- **`progress`**: Actively being worked on.
- **`done`**: Operation completed.
- **`cancel`**: Cancelled.

---

## Key Methods

### `_compute_state()`
**Depends on:** `production_id.state`, `blocked_by_workorder_ids.state`, `production_availability`
**Logic:**
1. If production is cancelled: state = `'cancel'`
2. If production not started: state = `'pending'`
3. If production is draft/confirmed: state = `'pending'`
4. If production is progress/done:
   a. If all `blocked_by` workorders are `'done'`: state = `'ready'`
   b. If any `blocked_by` workorders are not `'done'`: state = `'waiting'`
   c. If production_availability is not `'assigned'`: still `'waiting'`
   d. If `date_planned_start` is in the past and no date_start set: state = `'ready'`

**Critical behavior:** This is a **compute method, not stored**. It is recalculated when dependencies change, but it can be out of sync if called in a context where dependencies haven't been updated yet.

### `_compute_duration()`
Calculates the actual duration from productivity lines.
**Logic:**
1. Sums duration from `production_ids` (workcenter productivity lines linked to this WO).
2. Adds workcenter's `time_start` and `time_stop`.
3. Returns total in the workcenter's `time_uom_id` units.

### `_compute_duration_expected()`
**Logic:**
1. Gets `duration` from `operation_id` or `workcenter_id` (computed cycle time).
2. Computes `cycle_count = qty_producing / workcenter.default_capacity` (capacity in units per cycle).
3. `total_time = (duration × cycle_count × workcenter.time_efficiency / 100) + time_start + time_stop`
4. Returns expected duration in seconds.

### `_set_dates(date_start, date_finished)`
Sets scheduling dates and creates resource calendar leaves.
**Logic:**
1. Writes `date_start` and `date_finished` on the workorder.
2. If `date_start` is in the past, skips resource leave creation.
3. Creates a `resource.calendar.leaves` record for the booked time slot.

**Failure modes:**
- If the workcenter's calendar has a conflict (overlapping leaves), `_get_first_available_slot()` handles retries.
- If no calendar is defined on the workcenter, no leaves are created.

### `_calculate_date_finished()`
Computes expected finish date based on `_get_duration_expected()` and `date_planned_start`.

### `button_start()`
Transitions WO to `'progress'` state.
**Logic:**
1. Sets `date_start` to now if not set.
2. Sets `state = 'progress'`.
3. Creates a productivity line with `user_id` and start time.

### `button_finish()`
Transitions WO to `'done'` state.
**Logic:**
1. Sets `date_finished` to now.
2. Writes total `duration` from productivity lines.
3. Sets `state = 'done'`.
4. Triggers `production_id.action_update_visible_move()`.

### `action_propose_repair()`
Creates a quality alert from the workorder.

### `unlink()`
**Special behavior:** Before deletion:
1. Unlinks all related `mrp.workorder.link` records.
2. Writes `workorder_id=False` on related `mrp.production.step` records.

### `add_check()`
Creates a new quality check record from the WO's quality controls.

### `_compute_working_users()`
Returns the set of users currently working on this WO based on active productivity lines.

---

## Dependency Chain

- **`blocked_by_workorder_ids`**: Operations that must complete before this one can start.
- **`needed_by_workorder_ids`**: Operations that depend on this one.
- Dependencies are mirrored: if WO A blocks WO B, then B is in A's `needed_by` and A is in B's `blocked_by`.

**Cycle detection:** The routing model has `_check_no_cyclic_dependencies()` on `mrp.routing.workcenter` to prevent circular dependencies at the routing level. At the workorder level, `_compute_state()` handles it by not allowing `'ready'` state if a cycle exists (though cycles at this level would be a data integrity issue).

---

## Cross-Model Relationships

### With `mrp.production`
- `production_id` links to parent MO.
- MO state change cascades to WO states.

### With `mrp.workcenter`
- `workcenter_id` defines capacity, efficiency, and scheduling.
- `_get_first_available_slot()` on the workcenter finds scheduling slots.

### With `mrp.routing.workcenter`
- `operation_id` provides `time_cycle`, `workcenter_id`, `sequence`, and blocking dependencies.

### With `mrp.workcenter.productivity`
- Productivity lines track actual work time per user per WO.

---

## Edge Cases & Failure Modes

1. **`blocked_by` with cross-production dependencies:** The dependency logic only checks same-production workorders. Cross-MO dependencies are not modeled at the WO level.
2. **Date scheduling with no calendar:** If `workcenter_id.resource_calendar_id` is not set, `_set_dates()` skips calendar leave creation and `_get_first_available_slot()` returns immediately with the requested date.
3. **Multiple concurrent `button_start()` calls:** The second call will create a duplicate productivity line (since the WO is already in `'progress'` state but nothing prevents starting again).
4. **`qty_producing` changes mid-WO:** If qty_producing is changed after work has started, duration expectations are not automatically recalculated. The WO must be manually re-planned.
5. **WO cancellation:** Does not cascade cancel to dependent WOs. The dependent WOs remain in `'waiting'` state indefinitely if the blocking WO was cancelled.
6. **`date_planned_start` in the past on first WO:** `_compute_state()` forces `'ready'` state if the first planned start date is in the past, regardless of whether the production has been started.
7. **Resource calendar conflicts:** `_get_first_available_slot()` uses 50 iterations with 14-day chunks to find a free slot. If no free slot is found within 700 days, scheduling fails.
8. **Productivity lines and user tracking:** Productivity lines are created per `button_start()` / `button_finish()` cycle. If a user starts a WO, switches to another, then finishes the WO, the duration is attributed to the WO but the `last_worker_id` may reflect the last closer rather than the actual primary worker.
9. **WO with no workcenter:** If `workcenter_id` is not set, `_get_duration_expected()` returns 0, and `_compute_state()` defaults to `'pending'`.
10. **`unlink()` re-raises standard exception:** If the WO has associated stock moves (from quality checks that created moves), unlinking may fail due to foreign key constraints.
