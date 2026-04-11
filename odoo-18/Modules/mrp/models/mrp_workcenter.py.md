# MRP Workcenter - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/mrp/models/mrp_workcenter.py`
**Lines:** ~607

---

## Model Overview

`mrp.workcenter` defines a manufacturing resource (machine, team, or workstation) with capacity, scheduling, and performance tracking. It manages availability slots, OEE computation, and productivity tracking.

Also contains sub-models: `mrp.workcenter.tag`, `mrp.workcenter.productivity.loss.type`, `mrp.workcenter.productivity.loss`, `mrp.workcenter.productivity`, and `mrp.workcenter.capacity`.

---

## Fields

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Workcenter name |
| `active` | Boolean | Archive/unarchive |
| `company_id` | Many2one | `res.company` |
| `resource_id` | Many2one | `resource.resource`; linked calendar and capacity |
| `code` | Char | Short code |
| `sequence` | Integer | Default sequence |
| `default_capacity` | Float | Units per cycle (production capacity) |
| `time_efficiency` | Float | Efficiency factor (default 100). >100 means faster than rated |
| `costs_hour` | Float | Hourly cost of using this workcenter |
| `costs_hour_percentage` | Float | Percentage of hourly cost |
| `costs_cycle` | Float | Fixed cost per production cycle |
| `costs_journal_id` | Many2one | `account.journal`; cost posting journal |
| `costs_account_id` | Many2one | `account.account`; cost posting account |
| `time_start` | Float | Fixed time before production starts (hours) |
| `time_stop` | Float | Fixed time after production ends (hours) |
| `color` | Integer | Kanban color |
| `description` | Char | Workcenter description |
| `working_state` | Selection | `'available'`, `'blocked'`, `'busy'`; computed |
| `blocked_time` | Float | Time blocked (computed from productivity lines) |
| `productive_time` | Float | Time producing (computed from productivity lines) |
| `oee_target` | Float | OEE target percentage |
| `oee` | Float | Overall Equipment Effectiveness (computed) |
| `performance` | Float | Performance ratio (computed) |
| `alternative_workcenter_ids` | Many2many | `mrp.workcenter`; fallback workcenters |
| `capacity_ids` | One2many | `mrp.workcenter.capacity`; product-specific capacity |
| `tag_ids` | Many2many | `mrp.workcenter.tag`; categorization |
| `note` | Text | Internal notes |

### Productivity Loss Type (`mrp.workcenter.productivity.loss.type`)
| Field | Type | Notes |
|---|---|---|
| `name` | Char | Loss type name |
| `sequence` | Integer | Sort order |
| `category` | Selection | `'availability'`, `'performance'`, `'quality'`; for OEE calculation |

### Productivity Loss (`mrp.workcenter.productivity.loss`)
| Field | Type | Notes |
|---|---|---|
| `name` | Char | Loss reason |
| `loss_type` | Many2one | `mrp.workcenter.productivity.loss.type` |

### Productivity Line (`mrp.workcenter.productivity`)
| Field | Type | Notes |
|---|---|---|
| `workcenter_id` | Many2one | `mrp.workcenter` |
| `user_id` | Many2one | `res.users`; operator |
| `workorder_id` | Many2one | `mrp.workorder`; linked workorder |
| `loss_type` | Many2one | `mrp.workcenter.productivity.loss` |
| `loss_id` | Many2one | Specific loss reason |
| `date_start` | Datetime | Start time |
| `date_end` | Datetime | End time |
| `duration` | Float | Duration in hours (computed from date_start/date_end) |

### Workcenter Capacity (`mrp.workcenter.capacity`)
| Field | Type | Notes |
|---|---|---|
| `workcenter_id` | Many2one | `mrp.workcenter` |
| `product_id` | Many2one | `product.product`; specific product |
| `capacity` | Float | Units per cycle for this product |

---

## Key Methods

### `_compute_working_state()`
Determines if the workcenter is available/blocked/busy.
**Logic:**
1. Look for active (unclosed) `mrp.workcenter.productivity` lines for this workcenter.
2. If any line has `loss_type.category == 'availability'` and `loss_id` is set: `working_state = 'blocked'`.
3. If any line is in progress (no `date_end`): `working_state = 'busy'`.
4. Otherwise: `working_state = 'available'`.

**Edge case:** If there are overlapping productivity lines, the last one by `date_start` takes precedence for the "busy" state.

### `_compute_oee()`
**OEE Formula:** `oee = availability × performance × quality`
- **Availability** = `(productive_time) / (productive_time + blocked_time)`
- **Performance** = `(theoretical_time) / (productive_time)` — capped at `oee_target`
- **Quality** = 1.0 (always 1.0 in this implementation — quality losses not tracked here)

**Displayed as:** Percentage (0-100%).

### `_compute_performance()`
**Formula:** `performance = theoretical_cycle_time / actual_cycle_time × 100`
Where `theoretical_cycle_time` is based on `default_capacity × time_efficiency`.
Capped at `oee_target` (100 by default).

### `_get_first_available_slot(start_date, end_date)`
Finds the first available time slot for scheduling.
**Logic:**
1. Iterates up to 50 times.
2. Each iteration searches for a 14-day chunk (up to 700 days total lookahead).
3. Uses `resource.calendar` to find intervals where:
   a. No overlapping `resource.calendar.leaves` exist.
   b. No active `mrp.workorder` overlaps (from `workorder_ids` with state not in `done/cancel`).
   c. Resource calendar is available.
4. Returns `(available_start, available_end)` or `False` if no slot found.

**Edge cases:**
- If no `resource_id` is linked, returns the requested start date immediately (no capacity check).
- If 50 iterations (700 days) are exhausted, returns `False` — scheduling fails.

### `action_unblock()`
Closes all active `mrp.workcenter.productivity` lines for this workcenter that have `loss_type.category == 'availability'`.
**Used to:** Unblock a workcenter after resolving a breakdown.

---

## Cross-Model Relationships

### With `resource.resource`
- `resource_id` links the workcenter to Odoo's resource scheduling system.
- The resource calendar defines working hours.
- Calendar leaves define breaks, holidays, and bookings.

### With `mrp.workorder`
- Workorders are assigned to workcenters.
- Active workorders block scheduling slots.

### With `mrp.workcenter.capacity`
- Product-specific capacity overrides `default_capacity` for specific products.

---

## Edge Cases & Failure Modes

1. **No `resource_id`:** `_get_first_available_slot()` returns the requested date immediately, bypassing all capacity and calendar checks. This effectively means the workcenter has infinite capacity.
2. **OEE > 100%:** `performance` can exceed 100% if `time_efficiency > 100` and actual production is faster than the theoretical rate. This is displayed but may be misleading.
3. **Quality losses not tracked:** The OEE computation always uses `quality = 1.0`. Actual quality losses from the workcenter are not factored in.
4. **Overlapping productivity lines:** If two operators start productivity tracking simultaneously without ending the first, the workcenter will be double-booked. `_compute_working_state()` will see both as "busy".
5. **Alternative workcenters:** `alternative_workcenter_ids` is defined but the scheduling logic in `_get_first_available_slot()` does NOT automatically fall back to alternatives. It is a data field that external code can use for fallback logic.
6. **Capacity per product:** `capacity_ids` allows overriding `default_capacity` for specific products. The workorder scheduling logic should use this, but if the product-specific capacity is 0, division by zero occurs in duration calculations.
7. **Blocked time from non-availability losses:** Only losses with `loss_type.category == 'availability'` contribute to `blocked_time` in the OEE calculation. Performance losses are excluded.
8. **`costs_hour_percentage`:** The meaning of this field is unclear from the source; it may be used in conjunction with `costs_hour` for a blended cost rate.
