# Project Project - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/project/models/project_project.py`
**Lines:** ~1125
**Inherits:** `portal.mixin`, `mail.alias.mixin`, `rating.parent.mixin`, `mail.thread`, `mail.activity.mixin`, `mail.tracking.duration.mixin`, `analytic.plan.fields.mixin`

---

## Model Overview

`project.project` represents a project container. It manages tasks, milestones, collaborators, privacy visibility, rating settings, and followers. It integrates with the analytic accounting system for time and cost tracking.

---

## Fields

### Identity & Classification
| Field | Type | Notes |
|---|---|---|
| `name` | Char | Required; project name |
| `active` | Boolean | Archive/unarchive |
| `description` | Html | Project description |
| `sequence` | Integer | Kanban ordering |
| `company_id` | Many2one | `res.company`; multi-company isolation |
| `user_id` | Many2one | `res.users`; project manager |

### Privacy & Access
| Field | Type | Notes |
|---|---|---|
| `privacy_visibility` | Selection | `'followers'`, `'employees'`, `'portal'`; controls record visibility |
| `visibility` | Selection | `'public'`, `'privacy_field_employees'`, `'privacy_field_followers'`; portal visibility |
| `access_token` | Char | Portal access token |
| `favorite_user_ids` | Many2many | `res.users`; users who favorited this project |
| `is_favorite` | Boolean | Current user has favorited |
| `favorite_count` | Integer | Number of favorited users |

### Tasks & Structure
| Field | Type | Notes |
|---|---|---|
| `task_ids` | One2many | `project.task`; tasks in this project |
| `task_count` | Integer | Total task count (computed via `_compute_task_count`) |
| `task_count_per_stage` | Integer | Per-stage task counts via `read_group` |
| `open_task_count` | Integer | Non-done task count |
| `closed_task_count` | Integer | Done task count |
| `type_ids` | Many2many | `project.task.type`; stages available in Kanban |
| `stage_id` | Many2one | `project.project.stage`; current project stage |

### Milestones
| Field | Type | Notes |
|---|---|---|
| `milestone_ids` | One2many | `project.milestone`; project milestones |
| `milestone_count` | Integer | Number of milestones |
| `milestone_reached_count` | Integer | Number of reached milestones |
| `milestone_deadline` | Date | Nearest milestone deadline |

### Collaboration
| Field | Type | Notes |
|---|---|---|
| `collaborator_ids` | One2many | `project.collaborator`; portal collaborators |
| `collaborator_count` | Integer | Number of collaborators |

### Rating
| Field | Type | Notes |
|---|---|---|
| `rating_active` | Boolean | Enable customer ratings |
| `rating_status` | Selection | `'running'`, `'pending'`, `'stage_default'` |
| `rating_status_period` | Selection | `'daily'`, `'weekly'`, `'bimonthly'`, `'monthly'`, `'quarterly'` |
| `parent_id` | Many2one | `project.project`; parent project for sub-projects |
| `child_ids` | One2many | `project.project`; sub-projects |

### Accounting
| Field | Type | Notes |
|---|---|---|
| `account_id` | Many2one | `account.analytic.account`; linked analytic account |
| `alias_id` | Many2one | `mail.alias`; inbound email alias |
| `alias_name` | Char | Alias email prefix |
| `alias_defaults` | Text | Default values for email-created tasks |

### Tracking
| Field | Type | Notes |
|---|---|---|
| `last_task_id` | Many2one | `project.task`; most recently modified task |
| `last_update` | Datetime | Most recent task update time |
| `date` | Date | Date from last update |
| `label_tasks` | Char | Task label (e.g., "Task", "Deliverable") |

---

## Computed Fields

### `_compute_task_count()`
**Logic:** Uses `__compute_task_count()` helper to count tasks via `read_group`.
**Counts:** All tasks matching the project (includes subtasks, since subtasks inherit `project_id`).

### `_compute_collaborator_count()`
**Logic:** `len(collaborator_ids)`.

### `_compute_milestone_*`
- `_compute_milestone_count()`: counts all milestones.
- `_compute_milestone_reached_count()`: counts `is_reached=True`.
- `_compute_milestone_deadline()`: minimum `deadline` of unreached milestones.

### `_compute_last_update()`
**Logic:** `last_update = max(task.date_last_stage_update, task.date_last_status_update)`.

---

## Key Methods

### `map_tasks(src_tasks)`
Copies tasks from one project to another during project duplication.
**Logic:**
1. For each task in `src_tasks`:
   a. Create a copy with `project_id` set to `self`.
   b. Collect old→new task ID mappings.
   c. For each subtask: update `parent_id` to the new parent task.
2. Returns list of new task records.

**Used by:** `copy()` to copy all tasks when duplicating a project.

### `copy(default=None)`
**Special behavior:**
- Clears `favorite_user_ids` (no favorites on copy).
- Copies tasks via `map_tasks()`.
- Generates new analytic account if one was set.
- Clears `alias_id` (new alias for new project).
- Sets new `access_token` for portal access.

### `_change_privacy_visibility()`
Handles visibility changes that affect follower access.
**Logic:**
- When `privacy_visibility` changes, resyncs followers based on the new visibility rules.

### `_add_collaborators(partner_ids)`
Adds portal collaborators.
**Logic:**
1. Creates `project.collaborator` records.
2. Calls `_add_followers()` to subscribe them to the project.

### `_add_followers(partner_ids, force=True)`
Subscribes partners as followers.
**Logic:**
1. If `force=True`: unsubscribes existing followers not in the list.
2. Subscribes all partners in `partner_ids`.
3. For internal users (non-share): subscribes them and sends email.
4. For portal users: subscribes without email.

### `_compute_access_url()`
Sets `/my/projects/{id}` as the portal access URL.

### `action_project_sharing_start()`
Opens the project sharing portal for a project.

### `action_view_tasks()`
Opens task list view filtered to this project.

### `action_view_milestones()`
Opens milestone list view for this project.

### `toggle_favorite()`
Toggles current user's favorite status.

### `_update_working_users()`
Called by tasks to register working time. Updates the project's last activity tracking.

### `_track_template(changes)`
Sends email notification on stage change if `stage_id.mail_template_id` is set.

---

## Stage Management

- `project_project_stage`: Project lifecycle stages (e.g., Planning, In Progress, Closed).
- `stage_id` on the project model is a single-stage indicator, not a pipeline (unlike `crm.lead`).
- `project.task.type` is the task-level stage (Kanban pipeline), which is separate.

---

## Cross-Model Relationships

### With `project.task`
- Project contains tasks.
- Task `project_id` is the foreign key.
- `last_task_id`, `last_update` track the most recent task activity.

### With `project.collaborator`
- Portal collaborators can access tasks shared with them.
- Collaborator creation triggers `_add_collaborators()` → `_add_followers()`.

### With `project.milestone`
- Project has milestones.
- Milestones group related tasks.

### With `account.analytic.account`
- Analytic account for financial tracking.
- On `unlink()`: deletes the analytic account if it has no lines.

### With `mail.alias`
- Project-level email alias for creating tasks from email.

---

## Privacy Visibility

| Value | Behavior |
|---|---|
| `followers` | Only project followers can access |
| `employees` | All internal users can access |
| `portal` | Portal users added as collaborators can access |

When `privacy_visibility = 'portal'`:
- The project becomes accessible via Project Sharing.
- `project.collaborator` records define which partners can access.
- Collaborator access can be `limited` (tasks shared individually) or full.

---

## Edge Cases & Failure Modes

1. **Project deletion with tasks:** Standard `unlink()` will raise a `ForeignKey` constraint error if any `project.task` references the project.
2. **Copying with subtasks:** `map_tasks()` copies subtasks independently. If the parent task's `project_id` changes but the subtask is in a different project (cross-project subtasks), the subtask's `parent_id` is preserved but its `project_id` is updated — potentially creating a subtask in a different project.
3. **Analytic account with lines:** On project unlink, if `account_id` has analytic lines, the account is NOT deleted (the unlink method checks `line_ids` and skips deletion if lines exist).
4. **`privacy_visibility` change to `portal`:** Does not automatically add existing followers as collaborators. They must be manually added.
5. **`stage_id` vs `type_ids`:** `stage_id` is the current project stage (one value). `type_ids` is the set of available task stages. These are separate concepts — `type_ids` drives the Kanban pipeline, `stage_id` is a project lifecycle marker.
6. **Favorite count:** Stored as an integer; increments/decrements via `toggle_favorite()` using ORM writes. Race conditions possible if multiple users toggle simultaneously.
7. **Collaborator and multi-company:** Portal collaborators may have access to companies the project doesn't belong to. Access is filtered by the collaborator's company.
8. **`_change_privacy_visibility` with existing portal access:** If visibility is changed from `portal` to `followers`, existing collaborators retain their records but lose effective access.
9. **`last_task_id` staleness:** `last_task_id` is recomputed on every task write via `_compute_last_update`. However, if a task is unlinked, `last_task_id` may point to a deleted record. No automatic cleanup mechanism is visible.
10. **Project sharing with limited access:** When `collaborator.limited_access=True`, tasks are shared selectively. The access rules for limited sharing are enforced via `ir.rule` on `project.task`.
