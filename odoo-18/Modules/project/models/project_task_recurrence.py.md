# Project Task Recurrence - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/project/models/project_task_recurrence.py`
**Lines:** ~98

---

## Model Overview

`project.task.recurrence` manages recurring task patterns. It defines the recurrence rule (frequency, interval, end condition) and generates future task occurrences based on this rule.

---

## Fields

| Field | Type | Notes |
|---|---|---|
| `task_ids` | One2many | `project.task`; tasks in this recurrence |
| `repeat_interval` | Integer | Number of units between occurrences (default 1) |
| `repeat_unit` | Selection | `'day'`, `'week'`, `'month'`, `'year'` |
| `repeat_type` | Selection | `'forever'`, `'after'`, `'until'` |
| `repeat_number` | Integer | Number of repetitions (used when `repeat_type='after'`) |
| `repeat_until` | Date | End date (used when `repeat_type='until'`) |
| `mon` | Boolean | Monday (for weekly) |
| `tue` | Boolean | Tuesday |
| `wed` | Boolean | Wednesday |
| `thu` | Boolean | Thursday |
| `fri` | Boolean | Friday |
| `sat` | Boolean | Saturday |
| `sun` | Boolean | Sunday |

---

## Key Methods

### `_create_next_occurrence(task)`
**Purpose:** Generates the next task in the recurrence chain.
**Logic:**
1. Determine base date: `max(task.date_deadline, task.date_end, task.create_date)`.
2. Compute next date using `relativedelta` based on `repeat_unit` and `repeat_interval`.
3. If `repeat_type='after'`: check if `repeat_number` occurrences have been reached.
4. If `repeat_type='until'`: check if `repeat_until` has been reached.
5. Build a copy of `task` via `copy_data()`.
6. Update date fields: `date_deadline`, `date_end`, `create_date`, `date_last_stage_update`, `date_assign`, `date_last_hours_update`.
7. Append " (copy)" to task name.
8. Create the new task with `recurring_task=True`.
9. Return the new task.

**Date field handling:** Only non-False date fields are updated. This ensures that tasks without a deadline don't get a forced deadline.

### `_check_repeat_until_date()`
**Constraint:** `@api.constrains('repeat_until')`
**Validation:** `repeat_until` must be strictly greater than today if `repeat_type='until'`.
**Used by:** `write()` and `create()`.

### `_get_last_task_id_per_recurrence_id()`
Static utility method that returns the last (most recently created) task ID per recurrence ID for the current task set.

---

## Recurrence Rule Semantics

| `repeat_unit` | Effect |
|---|---|
| `day` | Every `repeat_interval` days |
| `week` | Every `repeat_interval` weeks on selected weekdays |
| `month` | Every `repeat_interval` months on the same day number |
| `year` | Every `repeat_interval` years on the same date |

### Weekly with weekdays
When `repeat_unit='week'`:
- `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun` define which days of the week the recurrence applies.
- `relativedelta(weeks=repeat_interval)` + weekday filter is applied.

---

## Edge Cases & Failure Modes

1. **Endless recurrence (`repeat_type='forever'`):** No mechanism in this model automatically terminates the recurrence. External cron jobs or user action must stop it.
2. **`repeat_type='after'` overshoot:** When `repeat_number` is reached, the recurrence should stop. If `_create_next_occurrence()` is called after the last occurrence, it will still create a task. The caller should check `len(recurrence.task_ids) >= repeat_number`.
3. **`repeat_until` in the past:** `_check_repeat_until_date()` rejects it.
4. **Task without dates:** If the base task has no `date_deadline`, `date_end`, or `create_date`, the next occurrence date cannot be computed. The method uses `max()` which would fail if all are `False`. The code only updates non-False fields, so tasks without dates may produce tasks without dates.
5. **Weekly recurrence with no weekdays selected:** No days are selected for weekly recurrence. `relativedelta` would produce the same date (no weekday filtering applied). The task would be created on the same date indefinitely.
6. **Day-of-month overflow:** For monthly recurrence on 31st, if the next month has fewer days (e.g., February), `relativedelta(months=1)` may produce an invalid date. Odoo's `relativedelta` implementation handles this by clamping to the last valid day of the month.
7. **Recurrence and subtasks:** When a recurring task is copied via `_create_next_occurrence()`, its subtasks are also copied (since `copy_data()` copies child tasks). This creates a parallel subtask hierarchy.
8. **Recurrence break:** When a recurring task's recurrence is broken (e.g., via `action_unlink_recurrence()`), the task's `recurring_task` flag is set to `False` and the `recurrence_id` is unlinked. Subsequent tasks in the series are orphaned from the recurrence.
9. **`unlink()` on recurrence:** The `project.task` model has `unlink()` that handles the case where the last task of a recurrence is deleted — it unlinks the `recurrence_id`. This prevents orphaned recurrence records.
10. **Date timezone handling:** Date fields are `Date` or `Datetime`. `relativedelta` operations on dates are straightforward. However, if `date_end` is a `Datetime` and `date_deadline` is a `Date`, mixing them in `max()` may produce unexpected results.
