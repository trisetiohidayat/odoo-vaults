# Project Task - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/project/models/project_task.py`
**Lines:** ~2071
**Inherits:** `portal.mixin`, `mail.thread.cc`, `mail.activity.mixin`, `rating.mixin`, `mail.tracking.duration.mixin`, `html.field.history.mixin`

---

## Model Overview

`project.task` is the central task model. It supports subtasks, task dependencies, multiple assignees, milestones, recurrence, time tracking, and project sharing with portal users. It is the most complex model in the project module.

---

## Constants

```python
CLOSED_STATES = {'1_done': 'Done', '1_canceled': 'Cancelled'}

PROJECT_TASK_READABLE_FIELDS = {
    'id', 'name', 'company_id', 'project_id', 'partner_id',
    'stage_id', 'state', 'priority', 'assignee_id',
    'date_assign', 'date_deadline', 'date_end', 'date_last_stage_update',
    'kanban_state', 'project_privacy_visibility',
    # ... more fields for portal access
}

PROJECT_TASK_WRITABLE_FIELDS = {
    'assignee_id', 'date_deadline', 'display_in_project',
    'project_id', 'kanban_state', 'partner_id', 'stage_id', 'state',
    # ... portal-writable fields
}
```

---

## Fields

### Identity & Classification
| Field | Type | Notes |
|---|---|---|
| `id` | Integer | Record ID |
| `name` | Char | Task name |
| `active` | Boolean | Archive/unarchive |
| `company_id` | Many2one | `res.company` |
| `description` | Html | Task description with history tracking |

### Project & Structure
| Field | Type | Notes |
|---|---|---|
| `project_id` | Many2one | `project.project`; parent project |
| `parent_id` | Many2one | `project.task`; parent task (for subtasks) |
| `child_ids` | One2many | `project.task`; subtasks |
| `display_in_project` | Boolean | Show in parent project view even if subtask |
| `subtask_count` | Integer | Count of subtasks |
| `closed_subtask_count` | Integer | Count of closed subtasks |
| `subtask_completion_percentage` | Float | Computed: closed/total subtasks |

### Stage & State
| Field | Type | Notes |
|---|---|---|
| `stage_id` | Many2one | `project.task.type`; Kanban stage |
| `state` | Selection | `'01_in_progress'`, `'02_changes_requested'`, `'03_approved'`, `'1_done'`, `'1_canceled'`, `'04_waiting_normal'` |
| `kanban_state` | Selection | `'normal'`, `'blocked'`, `'done'` |
| `closed` | Boolean | Computed: is task in a closed state |

### Assignees
| Field | Type | Notes |
|---|---|---|
| `user_ids` | Many2many | `res.users`; multiple assignees (replaced `user_id` in Odoo 16+) |
| `assignee_id` | Many2one | Primary assignee (first of `user_ids`) |
| `date_assign` | Datetime | When first assigned |
| `working_users_close_to` | Many2many | Users approaching deadline |

### Personal Stages (User-specific)
| Field | Type | Notes |
|---|---|---|
| `personal_stage_type_ids` | Many2many | `project.task.type`; personal stages for this user |
| `personal_stage_type_id` | Many2one | Current personal stage (one of above) |
| `personal_stage_standalone_ids` | Many2many | `project.task.type`; standalone personal stages |

### Dependencies
| Field | Type | Notes |
|---|---|---|
| `depend_on_ids` | Many2many | `project.task`; tasks this task depends on |
| `dependent_ids` | Many2many | `project.task`; tasks that depend on this |
| `allow_task_dependencies` | Boolean | Enable dependency feature |
| `depend_on_count` | Integer | Count of blocking dependencies |
| `dependent_count` | Integer | Count of dependent tasks |

### Dates & Scheduling
| Field | Type | Notes |
|---|---|---|
| `date_deadline` | Date | Due date |
| `date_end` | Datetime | Actual end time |
| `date_last_stage_update` | Datetime | Last stage change time |
| `create_date` | Datetime | Creation time |
| `date_assign` | Datetime | When assigned |
| `planned_hours` | Float | Estimated time |
| `allocated_hours` | Float | Allocated time |
| `effective_hours` | Float | Time spent |
| `remaining_hours` | Float | Remaining = allocated - effective |

### Priority & Rating
| Field | Type | Notes |
|---|---|---|
| `priority` | Selection | `'0'` (normal), `'1'` (high) |
| `rating_ids` | One2many | `rating.rating`; ratings |
| `rating_active` | Boolean | Enable ratings |
| `rating_count` | Integer | Number of ratings |

### Recurrence
| Field | Type | Notes |
|---|---|---|
| `recurring_task` | Boolean | Is part of a recurrence |
| `recurrence_id` | Many2one | `project.task.recurrence`; parent recurrence |

### Tags & Milestone
| Field | Type | Notes |
|---|---|---|
| `tag_ids` | Many2many | `project.tags` |
| `milestone_id` | Many2one | `project.milestone` |
| `has_late_and_unreached_milestone` | Boolean | Computed; deadline exceeded, milestone not reached |

### Tracking
| Field | Type | Notes |
|---|---|---|
| `displayed_image_id` | Many2one | `ir.attachment`; Kanban cover image |
| `portal_access` | Selection | `'none'`, `'read'`, `'edit'` |
| `current_my_account_id` | Many2one | `project.timesheet`; active timesheet entry |

---

## State Machine

```
Normal Kanban Flow:
01_in_progress → 02_changes_requested → 03_approved → 1_done
     ↑                                    ↓
     ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ←

04_waiting_normal: Blocked by dependencies

1_canceled: Can be reached from any state

Blocked Kanban State:
kanban_state = 'blocked' (red): Dependencies not satisfied
kanban_state = 'normal' (grey): Normal state
kanban_state = 'done' (green): Done in Kanban view
```

### `_compute_state()`
**Logic:**
1. If `allow_task_dependencies=True` and `depend_on_ids` exist and not all are in `CLOSED_STATES`: state = `'04_waiting_normal'`.
2. Else: derive state from `stage_id` and `kanban_state`.
   - `kanban_state='blocked'` → `'02_changes_requested'`
   - `kanban_state='done'` → `'1_done'`
   - Default → `'01_in_progress'`

**Critical:** When dependencies become satisfied (all `depend_on_ids` reach closed states), the task automatically transitions out of `'04_waiting_normal'`.

### `kanban_state` values:
- `normal`: Default Kanban state
- `blocked`: Red Kanban; customer has requested changes
- `done`: Green Kanban; approved by customer

### `rating_apply(rate, ...)`
**Special behavior:** When `stage_id.auto_validation_state=True`:
- Rating >= `RATING_LIMIT_SATISFIED` (3/5) → state = `'03_approved'`
- Rating < `RATING_LIMIT_SATISFIED` → state = `'02_changes_requested'`

---

## Subtask Management

### `_get_subtask_ids_per_task_id()`
Uses a recursive CTE (`WITH RECURSIVE`) to find all subtasks recursively:
```sql
WITH RECURSIVE task_tree AS (
    SELECT id, id as supertask_id FROM project_task WHERE id IN (parent_ids)
    UNION ALL
    SELECT t.id, tree.supertask_id
    FROM project_task t
    JOIN task_tree tree ON tree.id = t.parent_id
    WHERE t.parent_id IS NOT NULL
)
SELECT supertask_id, ARRAY_AGG(id) FROM task_tree WHERE id != supertask_id GROUP BY supertask_id
```
**Performance:** O(depth) for deep hierarchies. `active_test` respects the context.

### `_get_all_subtasks()`
Returns union of all subtask IDs for all tasks in the recordset.

### `_get_subtasks_recursively()`
Recursive Python implementation for non-batched calls.

---

## Dependency Chain

- `depend_on_ids`: Tasks that must be completed before this task.
- `dependent_ids`: Tasks that depend on this task (inverse).
- When a dependency reaches a `CLOSED_STATES`, the dependent task checks if all dependencies are satisfied and may transition out of `'04_waiting_normal'`.

**Constraint:** `@api.constrains('depend_on_ids', 'dependent_ids')` — prevents self-reference and validates no circular dependencies (indirect).

---

## Key Methods

### `write(vals)`
**Handles:**
- `user_ids` change: triggers `date_assign` update, subscribes new users, triggers activity creation.
- `stage_id` change: updates `date_last_stage_update`, triggers mail template.
- `parent_id` change: recomputes `milestone_id` (inherits parent's milestone if same project).
- `project_id` change: cascades to subtasks, recalculates milestones, triggers follower sync.
- `recurring_task=True`: creates recurrence record.

**Cascading behaviors:**
- Moving a parent task to a different project: prompts whether to move subtasks too.
- Archiving: child tasks are also archived (filtered by `display_in_project`).

### `copy(default=None)`
**Special behavior:**
- Clears `recurrence_id` (task is not part of a recurrence on copy).
- Handles dependency mapping via `_create_task_mapping()` for cross-project copy.
- Clears `date_assign`, `date_end`.
- Handles subtask copying: subtasks are copied independently.

### `action_dependent_tasks()`
Returns action window filtered to `depend_on_ids` = self.

### `action_recurring_tasks()`
Returns action window filtered to `recurrence_id` = self.

### `action_convert_to_subtask()`
Wizard to convert a task into a subtask of another task (must have a project).

### `_track_template(changes)`
Sends email notification on stage change if `stage_id.mail_template_id` is set.

### `_creation_message()`
Returns project-aware creation notification message.

### `email_split(msg)`
Splits email addresses from message, filtering out project alias addresses.

### `message_new(msg, custom_values)`
Processes inbound emails to create tasks.
- Auto-creates partner from `email_from` if not found.
- Sets `name` from subject.
- Subscribes email senders as followers.

---

## Portal Access Control

### `PROJECT_TASK_READABLE_FIELDS` / `PROJECT_TASK_WRITABLE_FIELDS`
Define the field whitelist for portal users.
**Logic:** `_ensure_fields_are_accessible()` checks if the current field is in the writable set; raises `AccessError` if not.

### `_portal_get_parent_hash_token()`
Provides a hash token for portal users to access parent tasks in project sharing.

---

## Rating Integration

- Inherits `rating.mixin`.
- `_rating_get_operator()`: overridden to use `user_ids` (multiple assignees) instead of single `user_id`.
- `_send_task_rating_mail()`: sends rating request email when task reaches a stage with `rating_template_id`.
- `auto_validation_state` on stage: automatically sets `state` based on rating value.

---

## Edge Cases & Failure Modes

1. **Subtask project mismatch:** A subtask can have a different `project_id` than its parent. In this case, the subtask's `display_in_project` determines where it appears. Cross-project subtasks can exist.
2. **Dependency cycle detection:** The `constrains` decorator only checks direct `depend_on_ids` cycles. Indirect cycles (A→B→C→A) are caught by the same mechanism because each individual write checks the full `depend_on_ids` + `dependent_ids` chain.
3. **`'04_waiting_normal'` state and Kanban:** When a task in `'04_waiting_normal'` has its last dependency closed, `_compute_state()` recalculates. However, if the user has manually set the state, the compute will overwrite the manual state — this could be seen as unexpected behavior.
4. **Personal stages:** When a user creates a private task (no `project_id`), a personal stage is auto-created via `_ensure_personal_stages()`. If all personal stages are deleted, the user cannot create private tasks.
5. **Multiple assignees (`user_ids`):** `date_assign` is set only when the first user is assigned. When additional users are added, `date_assign` is not updated. The first assignee determines `assignee_id`.
6. **Milestone and project change:** When `project_id` changes, `_compute_milestone_id()` clears the `milestone_id` if the milestone's project differs. The task's milestone is NOT automatically migrated.
7. **Recurrence and subtasks:** A recurring parent task does NOT automatically create recurring subtasks. Subtasks are part of the recurrence only if they are included in the copy.
8. **`active_test` in subtask query:** `_get_subtask_ids_per_task_id()` respects `active_test` context. When `active_test=False`, inactive subtasks are included in the count and deletion.
9. **Portal rating visibility:** `_mail_get_message_subtypes()` hides the rating subtype if `project_id.rating_active=False`. Rating emails are suppressed in this case.
10. **Project deletion with tasks:** Standard `unlink()` raises `ForeignKey` constraint error if any task references the project.
11. **Task with no project (private task):** Private tasks have `project_id=False`. They are associated with the user's personal stages. Portal users cannot create private tasks.
12. **`_compute_partner_id()` subtask propagation:** When a task has no `partner_id`, it inherits from the parent task or project. If both parent and project change, the partner may be cleared if neither provides one.
13. **Timesheet integration:** `current_my_account_id` tracks the active timesheet entry. This is a thin field that external timesheet modules populate.
14. **Archive cascade:** When a task is archived, `child_ids` filtered by `display_in_project` are also archived. Subtasks with `display_in_project=False` are not affected.
15. **`kanban_state` vs `state`:** These are parallel state systems. `kanban_state` is a simplified 3-state view, while `state` is a more detailed 6-state system. When `state` changes to `'1_done'`, `kanban_state` is implicitly `done`.
