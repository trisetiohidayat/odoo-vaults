---
Module: project_hr_skills
Version: 18.0.0
Type: addon
Tags: #odoo18 #project_hr_skills #project #skills
---

## Overview

**Module:** `project_hr_skills`
**Depends:** `project`, `hr_skills` (auto_install: True)
**Location:** `~/odoo/odoo18/odoo/addons/project_hr_skills/`
**License:** OEEL-1
**Purpose:** Exposes task assignees' employee skills on the project task form for skill-based task filtering and visibility. Enables searching project tasks by assignee skill.

---

## Models

### `project.task` (models/project_task.py, 1–8)

Inherits: `project.task`

#### Fields

| Field | Type | Description |
|---|---|---|
| `user_skill_ids` | One2many (`hr.employee.skill`, related) | Related to `user_ids.employee_skill_ids` — aggregates skills of all assignees on a task. Read-only computed display field. |

#### Methods

None — single related field only.

---

## Views

**XML:** `views/project_task_views.xml`

---

## Architecture Notes

- The module adds no behavior beyond a single related field.
- Skill management (create/update) happens in `hr.employee.skill` from `hr_skills`.
- Auto-installed when `project` and `hr_skills` are both present.
- v17→v18: No changes.