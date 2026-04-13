---
type: module
module: project_todo
tags: [odoo, odoo19, project, todo, task, productivity]
created: 2026-04-06
---

# To-Do

## Overview

| Property | Value |
|----------|-------|
| Category | Productivity/To-Do |
| Depends | project |
| Author | Odoo S.A. |
| License | LGPL-3 |
| Application | True |
| Sequence | 260 |

## Description

Extends project tasks with **to-do list** functionality. Provides a lightweight, focused task management app with its own Kanban board, list, form, calendar, and activity views separate from the full Project app. Allows quick task creation from descriptions and easy conversion to formal project tasks.

## Key Models

### `project.task` (Inherited)

**Key Methods:**

- `create(vals_list)` — Auto-generates `name` from the first line of `description` if not provided and no project/parent is set. Replaces `*` characters, truncates to 100 chars. Falls back to `'Untitled to-do'` if description is also absent.
- `action_convert_to_task()` — Opens the current to-do in task view mode. Sets `company_id` from the task's project.
- `get_todo_views_id()` — Returns IDs of the 5 main To-Do views (kanban, list, form, calendar, activity) for the To-Do app launcher.

**Auto-name Generation on Create:**

```
If name is empty AND no project_id AND no parent_id:
  - If description exists: name = first line of description (strip *, truncate 100)
  - Else: name = 'Untitled to-do'
```

## Views

| View | XML ID | Purpose |
|------|--------|---------|
| Kanban | `project_todo.project_task_view_todo_kanban` | To-Do board |
| List | `project_todo.project_task_view_todo_tree` | Table view |
| Form | `project_todo.project_task_view_todo_form` | Edit to-do |
| Calendar | `project_todo.project_todo_calendar` | Schedule view |
| Activity | `project_todo.project_todo_activity` | Activity stream |

## Hooks

| Hook | Purpose |
|------|---------|
| Post-init `_todo_post_init` | Registers To-Do app views in the IR model |

## Key Features

- Separate To-Do app with focused Kanban board
- Quick task creation from description content
- "Convert to Task" action
- Activity tracking integration
- Mail activity creation wizard (`mail.activity.todo.create`)
- Privacy and security rules via `project_todo_security.xml`

## Related

[Project.md](odoo-18/Modules/project.md), [Calendar.md](odoo-18/Modules/calendar.md)