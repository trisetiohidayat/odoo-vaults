# Project Task Type - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/project/models/project_task_type.py`
**Lines:** ~185

---

## Model Overview

`project.task.type` represents a Kanban stage for tasks. It can be shared across multiple projects (if `project_ids` is empty) or assigned to specific projects. Personal stages are assigned to a specific user (`user_id`) and are only visible to that user.

---

## Fields

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Stage name; required |
| `sequence` | Integer | Sort order |
| `active` | Boolean | Archive/unarchive |
| `project_ids` | Many2many | `project.project`; shared stages across projects |
| `mail_template_id` | Many2one | `mail.template`; email sent on task entry |
| `fold` | Boolean | Folded (collapsed) in Kanban view |
| `rating_template_id` | Many2one | `mail.template`; rating request on task entry |
| `auto_validation_state` | Boolean | Auto-set task state based on rating |
| `disabled_rating_warning` | Text | Warning message for disabled ratings on some projects |
| `user_id` | Many2one | `res.users`; personal stage owner (mutually exclusive with `project_ids`) |

---

## Key Methods

### `_get_default_project_ids()`
**Purpose:** Returns `[context.get('default_project_id')]` as default for `project_ids`.
**Edge case:** If no `default_project_id` in context, returns `None` (shared stage).

### `_default_user_id()`
**Logic:** If `default_project_id` is not in context, returns `self.env.uid` (personal stage for current user). If `default_project_id` is set, returns `False` (shared stage).

**This is the mechanism distinguishing personal stages from shared stages.**

### `_unlink_if_remaining_personal_stages()`
**Purpose:** Prevent deletion of a user's last personal stage.
**Trigger:** `@api.ondelete(at_uninstall=False)`
**Logic:**
1. Filter to stages with `user_id` set (personal stages).
2. For each user with stages being deleted: check if they will still have at least one remaining personal stage.
3. If no remaining stages for a user: raise `UserError`.
4. Moves tasks in deleted personal stages to a replacement stage (closest sequence below, or above if none exists).
5. Updates `project.task.stage.personal` records to point to replacement stage.

**Critical constraint:** An internal (non-share) user must always have at least one personal stage.

### `_check_personal_stage_not_linked_to_projects()`
**Constraint:** `@api.constrains('user_id', 'project_ids')`
**Validation:** Raises `UserError` if both `user_id` and `project_ids` are set simultaneously.
**Rationale:** Personal stages are private to a user and cannot be shared across projects.

### `write(vals)`
**Special behavior:** If `active` is set to `False`:
- Searches for all tasks in this stage.
- Sets `active=False` on those tasks (archive them).
- Then calls `super().write(vals)`.

### `toggle_active()`
**Override:** After calling `super()`, checks if there are any inactive tasks in now-active stages.
**If found:** Opens a wizard (`project.task.type.delete.wizard`) asking whether to unarchive tasks.

### `_compute_disabled_rating_warning()`
**Trigger:** `project_ids`, `project_ids.rating_active`
**Logic:** For each stage, find projects where `rating_active=False`. Join their names into a newline-separated warning text.

### `_compute_user_id()`
**Trigger:** `project_ids`
**Logic:** If `project_ids` is set on a stage, clear its `user_id` (shared stages cannot have a user owner).

---

## Personal vs Shared Stages

| Aspect | Personal Stage | Shared Stage |
|---|---|---|
| `user_id` | Set | `False` |
| `project_ids` | `False` | Set or empty (all projects) |
| Visibility | Only the owning user | All project team members |
| Creation | Automatic via `_ensure_personal_stages()` | Manual |
| Deletion | Blocked if last stage for user | Allowed |

---

## Edge Cases & Failure Modes

1. **Setting `project_ids` on a personal stage:** `_compute_user_id()` automatically clears `user_id` when `project_ids` is set. This means the stage transforms from personal to shared.
2. **Personal stage deletion with tasks:** `_unlink_if_remaining_personal_stages()` moves tasks to a replacement stage before deletion. If the replacement stage also belongs to a different user, the tasks become orphaned or reassigned.
3. **Sequence collision:** Multiple stages can have the same `sequence`. Ordering is undefined in this case; `id` is the tiebreaker (`_order = 'sequence, id'`).
4. **Setting `mail_template_id` on a shared stage:** The template is applied to all tasks entering this stage across all projects that use it.
5. **`auto_validation_state` and rating:** When a task enters a stage with `auto_validation_state=True` and a rating is received, the task's `state` is automatically set based on the rating value. This does not check if the project's `rating_active` is True.
6. **Stage without projects (`project_ids=False`):** Available to all projects. A new project will use this stage in its Kanban view.
7. **Unarchive wizard:** The `toggle_active()` wizard (`project.task.type.delete.wizard`) only appears if there are inactive tasks in the stage being unarchived. It does not appear for new stages.
8. **Cascading task archive on stage archive:** When a stage is deactivated, all tasks in it are archived. This is irreversible without the unarchive wizard.
9. **User with no personal stages:** When a user creates their first private task and no personal stage exists, `_ensure_personal_stages()` auto-creates default stages.
10. **Shared stage and personal stage with same name:** They are distinct records. A user can have a personal stage named "In Progress" and also use a shared stage named "In Progress" — no conflict.
