# MRP Routing Workcenter - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/mrp/models/mrp_routing.py`
**Lines:** ~195

---

## Model Overview

`mrp.routing.workcenter` defines a single operation step in a manufacturing routing, tied to a specific workcenter. It defines timing, sequence, and blocking/needed-by dependencies between operations.

Also contains `mrp.workcenter.tag` as a sub-model for workcenter categorization.

---

## Fields

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Operation name |
| `workcenter_id` | Many2one | `mrp.workcenter`; assigned workcenter |
| `bom_id` | Many2one | `mrp.bom`; parent BoM |
| `sequence` | Integer | Execution order |
| `time_mode` | Selection | `'auto'` (compute from history), `'manual'` (use manual value) |
| `time_mode_batch` | Integer | Number of past workorders to average (for `auto` mode) |
| `time_cycle_manual` | Float | Manual cycle time (in `time_uom_id` units) |
| `time_cycle` | Float | Computed cycle time |
| `time_efficiency` | Float | Efficiency factor (default 100) |
| `worksheet_type` | Selection | `'pdf'` (worksheet PDF), `'google_slide'` (Google Slides), `False` (none) |
| `worksheet_google_slide` | Char | Google Slides URL |
| `worksheet_page_ids` | One2many | PDF worksheet pages |
| `blocked_by_operation_ids` | Many2many | `mrp.routing.workcenter`; dependencies |
| `needed_by_operation_ids` | Many2many | `mrp.routing.workcenter`; dependents (inverse of blocked_by) |
| `allow_operation_dependencies` | Boolean | Enable dependency checking |
| `company_id` | Many2one | `res.company` |

---

## Key Methods

### `_compute_time_cycle()`
Computes cycle time for `auto` mode.
**Logic:**
1. Search for the last `time_mode_batch` (default 30) done workorders for this operation (same `operation_id`).
2. Average the `duration` of those workorders.
3. Set `time_cycle = average_duration`.
4. If no history: `time_cycle = time_cycle_manual`.
5. If `time_mode = 'manual'`: `time_cycle = time_cycle_manual`.

**Edge case:** If `time_mode_batch` workorders are found but some have `duration=0` (not started), they are still included in the average, which will drag down the average.

### `_get_duration_expected(workcenter_id, quantity, product_capacity)`
**Purpose:** Compute expected duration for a given production quantity.
**Formula:**
```
cycle_number = quantity / product_capacity
total_time = (time_cycle * cycle_number * time_efficiency / 100) + time_start + time_stop
```
Where:
- `time_cycle`: from this routing operation
- `time_efficiency`: from the workcenter
- `time_start`, `time_stop`: from the workcenter

**Failure modes:**
- If `product_capacity = 0`, division by zero occurs. The caller should guard against this.
- `time_efficiency` of 0 means no time is consumed, which is unrealistic.

### `_check_no_cyclic_dependencies()`
**Constraint:** Prevents circular dependencies in the routing operation chain.
**Applies via:** `@api.constrains('blocked_by_operation_ids')`
**Logic:** DFS traversal of `blocked_by_operation_ids` to detect cycles.
**Raises:** `ValidationError` with message listing the cycle.

---

## Edge Cases

1. **Dependency with cross-routing operations:** The constraint only checks within the same `bom_id` (since `blocked_by_operation_ids` references the same model, and routing operations are filtered by `bom_id`). Circular dependencies across different BoMs are not possible by design.
2. **Self-dependency:** Adding an operation as a `blocked_by` of itself will create a cycle and be rejected by the constraint.
3. **Empty workorder history:** If no workorders have been completed for the operation, `_compute_time_cycle()` falls back to the manual value.
4. **Worksheet PDF vs Google Slides:** These are mutually exclusive display modes for the production worksheet. Setting both may result in undefined behavior.
5. **Company-specific routing:** If a routing belongs to one company, its operations cannot be assigned to workcenters from another company. This is enforced by Odoo's multi-company record rules.
