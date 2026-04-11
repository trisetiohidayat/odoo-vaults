---
Module: project_todo
Version: 18.0.0
Type: addon
Tags: #odoo18 #project_todo #project #todo
---

## Overview

**Module:** `project_todo`
**Depends:** `project` (auto_install: True, application: True)
**Location:** `~/odoo/odoo18/odoo/addons/project_todo/`
**License:** LGPL-3
**Sequence:** 260
**Purpose:** Adds To-Do app behavior to project tasks. Private tasks (no project) are treated as personal to-dos. Includes onboarding experience, systray activity splitting, and a mail activity-to-todo wizard.

---

## Models

### `project.task` (models/project_task.py, 1–72)

Inherits: `project.task`

| Method | Decorator | Line | Description |
|---|---|---|---|
| `create(vals_list)` | `@api.model_create_multi` | 11 | Auto-generates name from first line of HTML-stripped description (markdown stripped, max 100 chars) if no `name`, `project_id`, or `parent_id` provided; falls back to `"Untitled to-do"`. |
| `_ensure_onboarding_todo()` | private | 24 | Checks `group_onboarding_todo` group; if user not in group, calls `_generate_onboarding_todo` and adds user to group. |
| `_generate_onboarding_todo(user)` | private | 30 | Creates a welcome to-do using QWeb template `project_todo.todo_user_onboarding` rendered server-side with user's name and lang. |
| `action_convert_to_task()` | action | 48 | Sets `company_id` from `project_id.company_id`; opens task form in edit mode. |
| `get_todo_views_id()` | `@api.model` | 58 | Returns To-Do app's view IDs as list of `(view_id, view_type)`: kanban, list, form, activity. Used for systray and navigation. |

### `res.users` (models/res_users.py, 1–78)

Inherits: `res.users`

`_get_activity_groups()` (line 13)
: Overrides parent. Removes the unified `project.task` activity group and replaces it with two separate groups based on raw SQL grouping by `BOOL(t.project_id)`:
- `is_task=False` → "To-Do" (private tasks), module icon `project_todo`
- `is_task=True` → "Task" (project tasks), module icon `project`
Each group gets `total_count`, `today_count`, `overdue_count`, `planned_count`, and a domain based on `res_ids`.

---

## Wizard

### `mail.activity.todo.create` (wizard/mail_activity_todo_create.py, 1–38)

Transient model. Creates both a `project.task` (to-do) and a `mail.activity` in one action from the mail activity panel.

| Field | Type | Line | Description |
|---|---|---|---|
| `summary` | Char | 9 | To-do title. |
| `date_deadline` | Date | 10 | Due date; required; defaults to today. |
| `user_id` | Many2one (`res.users`) | 11 | Assigned to; required; defaults to current user; readonly. |
| `note` | Html | 12 | Description/notes; sanitized for style only. |

`create_todo_activity()` (line 14)
: Creates a `project.task` with `name=summary`, `description=note`, `date_deadline`, `user_ids`. Then creates a `mail.activity` linked to that task with same summary, deadline, and user. Returns a client notification action.

---

## Views

**XML:** `views/project_task_views.xml`, `views/project_todo_menus.xml`, `wizard/mail_activity_todo_create.xml`

**Static assets:**
- `web.assets_backend`: SCSS (`scss/todo.scss`), Vue components (`components/**/*`), view files (`views/**/*`), web assets (`web/**/*`)
- `web.assets_tests`: tour tests
- `web.assets_unit_tests`: unit tests

---

## Security

`security/ir.model.access.csv` — ACL for `mail.activity.todo.create` wizard.
`security/project_todo_security.xml` — record rules for private tasks.

**Data:** `data/todo_template.xml` — onboarding QWeb template.

---

## Critical Notes

- Private tasks (no `project_id`) are To-Dos; tasks with `project_id` are regular Project tasks.
- Systray splits between To-Do and Project based on raw SQL `BOOL(t.project_id)`.
- `_ensure_onboarding_todo` triggers on first access per user — only generates once per user.
- Onboarding todo rendered server-side using QWeb — body is HTML injected into task description.
- `action_convert_to_task` bridges private to-dos to project tasks by setting company and opening the form.
- v17→v18: No breaking changes.