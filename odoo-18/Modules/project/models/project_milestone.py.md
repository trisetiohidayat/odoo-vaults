# Project Milestone - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/project/models/project_milestone.py`
**Lines:** ~130

---

## Model Overview

`project.milestone` tracks key deliverables or goals within a project. Milestones group related tasks and can be marked as reached based on task completion.

---

## Fields

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Required; milestone name |
| `project_id` | Many2one | `project.project`; parent project; `ondelete='cascade'` |
| `deadline` | Date | Target date; `tracking=True` (tracks changes) |
| `is_reached` | Boolean | Whether the milestone has been achieved |
| `reached_date` | Date | Date when `is_reached` was set; computed |
| `task_ids` | One2many | `project.task`; tasks in this milestone |

### Computed Fields
| Field | Type | Notes |
|---|---|---|
| `is_deadline_exceeded` | Boolean | `deadline < today` and not `is_reached` |
| `is_deadline_future` | Boolean | `deadline > today` |
| `task_count` | Integer | Total tasks in this milestone |
| `done_task_count` | Integer | Tasks in closed states |
| `can_be_marked_as_done` | Boolean | All tasks are done and at least one is closed |

---

## Key Methods

### `_compute_reached_date()`
**Trigger:** `is_reached`
**Logic:** `reached_date = today if is_reached else False`

### `_compute_is_deadline_exceeded()`
**Trigger:** `is_reached`, `deadline`
**Logic:** `is_deadline_exceeded = not is_reached and deadline and deadline < today`

### `_compute_task_count()`
Uses `read_group` with `state:array_agg` to get both count and state list in a single query:
```python
all_and_done_task_count_per_milestone = {
    milestone.id: (count, sum(state in CLOSED_STATES for state in state_list))
    for milestone, count, state_list in self.env['project.task']._read_group(...)
}
```

### `_compute_can_be_marked_as_done()`
**Logic:**
- If unreached and all tasks are in `CLOSED_STATES` and at least one is in `'1_done'`: `can_be_marked_as_done = True`.
- If `is_reached=True`: `can_be_marked_as_done = False`.
- Empty milestone (no tasks): `can_be_marked_as_done = False`.

**Special case for unsaved records:** If `self._ids` is empty (new record), loops over records individually (needed for new milestone creation validation).

### `toggle_is_reached(is_reached)`
Toggles the `is_reached` state.
**Logic:** Writes `is_reached` field, returns milestone data via `_get_data()`.

### `action_view_tasks()`
Returns an action to open tasks filtered to this milestone.
- If `task_count == 1`: opens the single task in form view.
- Otherwise: opens list view.

### `_get_fields_to_export()`
Returns `['id', 'name', 'deadline', 'is_reached', 'reached_date', 'is_deadline_exceeded', 'is_deadline_future', 'can_be_marked_as_done']` for JSON export.

### `_compute_display_name()`
Appends deadline to display name when `display_milestone_deadline` context is set:
`"{name} - {formatted_deadline}"`

### `copy(default=None)`
**Special behavior:** Handles `milestone_mapping` context for project duplication.
**Logic:**
```python
if old_milestone.project_id.allow_milestones:
    milestone_mapping[old_milestone.id] = new_milestone.id
```

---

## Edge Cases & Failure Modes

1. **Milestone with no tasks:** `can_be_marked_as_done=False`. An empty milestone cannot be marked as reached.
2. **All tasks cancelled (`'1_canceled'`):** `can_be_marked_as_done=False` because `'1_canceled'` is in `CLOSED_STATES` but not `'1_done'`. The milestone requires at least one task to be successfully completed.
3. **`is_reached=True` with deadline in the past:** Allowed. The milestone was reached even if the deadline was missed.
4. **Cascading task moves:** When a task's `project_id` changes, its `milestone_id` is recalculated via `_compute_milestone_id()` on `project.task`. If the task moves to a different project, its milestone is cleared.
5. **Milestone deletion:** `project_id` has `ondelete='cascade'`. Deleting the project deletes all milestones. Deleting a milestone does NOT delete tasks — it clears their `milestone_id`.
6. **Deadline tracking:** `tracking=True` on `deadline` means changes to the deadline are logged in the milestone's chatter.
7. **Project without milestones enabled:** If `project_id.allow_milestones=False`, tasks can still have `milestone_id` set (the field is not conditionally displayed). However, milestone-related computed fields (`task_count`, etc.) may return stale data.
8. **Deadline in the past on creation:** `is_deadline_exceeded=True` immediately on creation if `deadline` is in the past and `is_reached=False`.
9. **`milestone_mapping` context for copy:** Used during project duplication. When copying tasks, the old milestone IDs are mapped to new ones so that tasks reference the new project's milestones.
10. **`reached_date` staleness:** If `is_reached` is toggled from True to False and back to True, `reached_date` is updated to the latest toggle time, not preserved from the original reach time.
