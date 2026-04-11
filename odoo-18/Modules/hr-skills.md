---
Module: hr_skills
Version: Odoo 18
Type: Business
Tags: #hr, #skills, #competencies, #resume
---

# hr_skills — Skills & Competencies

Manages employee skills, proficiency levels, and resume/CV data. Extends `hr.employee` with a structured skill taxonomy and automatic skill-change logging.

**Addon path:** `~/odoo/odoo18/odoo/addons/hr_skills/`

---

## Data Model

```
hr.skill.type (skill category)
    ├── hr.skill (individual skill, belongs to one type)
    ├── hr.skill.level (proficiency levels, belongs to one type)
    │       └── level_progress: Integer (0–100%)
    └── hr.employee.skill (employee × skill × level junction)
            └── hr.employee.skill.log (historical snapshots)

hr.employee  ──< hr.resume.line  ──< hr.resume.line.type
hr.employee  ──< hr.employee.skill
hr.employee.public  ──< hr.employee.skill (read-only)
res.users  ──< hr.employee.skill  (via employee_id)
```

---

## `hr.skill.type` — Skill Category

Defines a group of related skills (e.g., "Programming Languages", "Marketing", "IT") and its proficiency levels.

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Required, translatable |
| `active` | Boolean | Soft-delete support |
| `skill_ids` | One2many → `hr.skill` | Reverse of `skill_type_id` |
| `skill_level_ids` | One2many → `hr.skill.level` | Levels defined per type |
| `color` | Integer | Random 1–11 default, for kanban display |

### Key Methods

- `copy_data()`: Appends ` (copy)` to name and resets color to 0.

### L4 Notes

- Skill types are the **top-level taxonomy**. A skill type groups both skills AND levels — levels are type-specific.
- The `color` field is the canonical display color for kanban cards on both `hr.skill.type` and `hr.employee.skill` records (the latter relates it through).
- There is no `hr.applicant.skill` model in the base `hr_skills` module — applicant skills are handled by the separate `hr_recruitment` addon which extends this module.

---

## `hr.skill` — Skill Master Record

A single skill, always belongs to exactly one `hr.skill.type`.

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Required, translatable |
| `sequence` | Integer | Default 10, controls ordering |
| `skill_type_id` | Many2one → `hr.skill.type` | Required, cascade delete |
| `color` | Integer | Related from `skill_type_id.color` |

### Key Methods

- `_compute_display_name()`: When context key `from_skill_dropdown` is set, returns `"{name} ({skill_type_id.name})"` — used in dropdown selectors for readability.

### L4 Notes

- Skills are scoped to a type. You cannot assign a "Python" skill from "Programming Languages" to an employee under a "Marketing" skill type.
- The `skill_type_id` onchange cascades: changing `skill_type_id` on `hr.employee.skill` resets `skill_id` to the first skill in the new type.

---

## `hr.skill.level` — Proficiency Level

Defines one proficiency tier within a skill type. Levels have a `level_progress` percentage (0–100) used for sorting and display.

| Field | Type | Notes |
|-------|------|-------|
| `skill_type_id` | Many2one → `hr.skill.type` | Required, cascade delete |
| `name` | Char | Required |
| `level_progress` | Integer | 0–100%, `CHECK` constraint enforces range |
| `default_level` | Boolean | First True wins; others cleared on write |

### SQL Constraints

```sql
CHECK(level_progress BETWEEN 0 AND 100)
```

### Key Methods

- `_compute_display_name()`: With context `from_skill_level_dropdown`, returns `"{name} ({level_progress}%)"` for clarity in dropdowns.
- `create()` / `write()`: Enforce only one `default_level=True` per skill type — clears other defaults before setting a new one.

### L4 Notes — Level Progression Model

- Levels are **not hardcoded as level_0 through level_5**. The system is flexible — skill types can have any number of levels with arbitrary percentages.
- Demo data ships these levels for "Programming Languages":
  - Beginner (15%), Elementary (25%), Intermediate (50%), Advanced (80%), Expert (100%)
- "Marketing" uses L1–L4 (25/50/75/100%).
- `level_progress` drives:
  1. Sorting (`ORDER BY level_progress DESC`)
  2. Dropdown display name formatting
  3. The `default_level` selection (which level auto-selects when assigning a skill)
  4. History tracking in `hr.employee.skill.log`

---

## `hr.employee.skill` — Employee Skill Junction

Links an employee to a skill and sets their proficiency level. Auto-creates a history log entry on create/write.

| Field | Type | Notes |
|-------|------|-------|
| `employee_id` | Many2one → `hr.employee` | Required, cascade delete |
| `skill_id` | Many2one → `hr.skill` | Compute+store; domain filtered by `skill_type_id` |
| `skill_type_id` | Many2one → `hr.skill.type` | Defaults to first active type; cascade delete |
| `skill_level_id` | Many2one → `hr.skill.level` | Compute+store; domain filtered by `skill_type_id` |
| `level_progress` | Integer | Related from `skill_level_id.level_progress` |
| `color` | Integer | Related from `skill_type_id.color` |

### SQL Constraints

```sql
UNIQUE (employee_id, skill_id)  -- One level per skill per employee
```

### Computed Fields

- `skill_id` (compute, store): When `skill_type_id` changes, auto-assigns the first skill in the type.
- `skill_level_id` (compute, store): When `skill_id` changes, auto-selects the `default_level` if set, otherwise the first level.
- `display_name`: Format `"{skill_id.name}: {skill_level_id.name}"`.

### Validation Constraints

- `_check_skill_type`: Raises `ValidationError` if `skill_id` does not belong to `skill_type_id`.
- `_check_skill_level`: Raises `ValidationError` if `skill_level_id` is not a valid level for `skill_type_id`.

### Key Methods

- `_create_logs()`: Called on `create()` and `write()`. Deduplicates skill history by `(employee_id, department_id, skill_id, date)` — one log entry per skill per department per day. If a log exists for today, updates the level; otherwise creates a new one.
- `create()` / `write()`: Calls `_create_logs()` after persisting.

### L4 Notes

- Department-change trigger: `hr.employee.write()` calls `_create_logs()` when `department_id` changes — this ensures the log records the department at the time of the skill record, not the current one.
- The `active` domain filter `('skill_type_id.active', '=', True)` on the `employee_skill_ids` One2many in `hr.employee` hides skills from inactive types.

---

## `hr.employee.skill.log` — Skill Change History

Append-only audit log of skill level changes per employee per department per day.

| Field | Type | Notes |
|-------|------|-------|
| `employee_id` | Many2one → `hr.employee` | Required, cascade delete |
| `department_id` | Many2one → `hr.department` | Captured at log creation time |
| `skill_id` | Many2one → `hr.skill` | Compute+store |
| `skill_type_id` | Many2one → `hr.skill.type` | Required, cascade delete |
| `skill_level_id` | Many2one → `hr.skill.level` | Compute+store |
| `level_progress` | Integer | Related from `skill_level_id.level_progress`, stored, `aggregator="avg"` |
| `date` | Date | Default: today |

### SQL Constraints

```sql
UNIQUE (employee_id, department_id, skill_id, date)
```

### L4 Notes

- `aggregator="avg"` on `level_progress` means grouped reads return average progress — useful for department-level analytics.
- This model is **append-only** in practice: `_create_logs()` updates existing same-day entries rather than creating duplicates.

---

## `hr.resume.line` — Employee Resume / CV Entry

Models a single line item on an employee's resume/CV (education, experience, certification, etc.).

| Field | Type | Notes |
|-------|------|-------|
| `employee_id` | Many2one → `hr.employee` | Required, cascade delete, indexed |
| `name` | Char | Required, translatable |
| `date_start` | Date | Required |
| `date_end` | Date | Optional; `CHECK` ensures >= `date_start` |
| `description` | Html | Translatable |
| `line_type_id` | Many2one → `hr.resume.line.type` | Category (Experience, Education, etc.) |
| `display_type` | Selection | Currently only `classic`; reserved for future templates |

### SQL Constraints

```sql
CHECK(date_start <= date_end OR date_end IS NULL)
```

### Auto-Creation on Employee Create

`hr.employee.create()` automatically creates a resume line of type `hr_skills.resume_type_experience` using the company name and employee's `job_title`.

---

## `hr.resume.line.type` — Resume Line Category

Simple taxonomy for resume line types.

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Required, translatable |
| `sequence` | Integer | Default 10 |

---

## Inheritance Chain

| Model | Inheritance | Notes |
|-------|-------------|-------|
| `hr.employee` | `_inherit = 'hr.employee'` | Adds `resume_line_ids`, `employee_skill_ids`, `skill_ids` |
| `hr.employee.public` | `_inherit = 'hr.employee.public'` | Read-only access to same fields |
| `res.users` | `_inherit = ['res.users']` | Adds `resume_line_ids`, `employee_skill_ids` via related; adds to `SELF_READABLE_FIELDS` / `SELF_WRITEABLE_FIELDS` |
| `resource.resource` | `_inherit = ['resource.resource']` | Adds `employee_skill_ids` via related |

### L4 Notes on Self-Service

`res.users` exposes `employee_skill_ids` and `resume_line_ids` as `SELF_WRITEABLE_FIELDS`, meaning employees can update their own skills and resume lines through the portal or frontend (subject to ACLs).

---

## Cross-Module Integration

### `hr_recruitment` (Applicant Skills)

The `hr_recruitment` module extends this module with `hr.applicant.skill` — applicant-level skill records analogous to `hr.employee.skill`. This allows comparing an applicant's skills against employee skills.

### `hr_expense` (Expense Skills)

Skills from `hr_skills` can be referenced in expense workflows via the `skill_ids` Many2many on `hr.employee` — expense reports can optionally require a skill assignment for analytic purposes.

### `_load_scenario()` Hook

`hr.employee._load_scenario()` imports demo skill and resume data from `hr_skills_scenario.xml` when loading demo data.

---

## Key Design Patterns

1. **Type-scoped levels**: Levels belong to a skill type, not globally. An "Expert" level in "Programming" is distinct from "Expert" in "Marketing" even though they share a name.
2. **Computed + stored skill/level defaults**: When `skill_type_id` is set, `skill_id` auto-fills from the type's first skill; `skill_level_id` auto-selects the `default_level`.
3. **Automatic history**: Every skill create/write triggers a daily log entry; department changes also trigger re-logging.
4. **Cascade delete**: All junction and child records are cascade-deleted when the parent is deleted.

---

## Related Files

- Model: `~/odoo/odoo18/odoo/addons/hr_skills/models/hr_skill.py`
- Model: `~/odoo/odoo18/odoo/addons/hr_skills/models/hr_skill_level.py`
- Model: `~/odoo/odoo18/odoo/addons/hr_skills/models/hr_skill_type.py`
- Model: `~/odoo/odoo18/odoo/addons/hr_skills/models/hr_employee_skill.py`
- Model: `~/odoo/odoo18/odoo/addons/hr_skills/models/hr_employee_skill_log.py`
- Model: `~/odoo/odoo18/odoo/addons/hr_skills/models/hr_resume_line.py`
- Model: `~/odoo/odoo18/odoo/addons/hr_skills/models/hr_resume_line_type.py`
- Model: `~/odoo/odoo18/odoo/addons/hr_skills/models/hr_employee.py`
- Model: `~/odoo/odoo18/odoo/addons/hr_skills/models/hr_employee_public.py`
- Model: `~/odoo/odoo18/odoo/addons/hr_skills/models/res_users.py`
- Model: `~/odoo/odoo18/odoo/addons/hr_skills/models/resource_resource.py`
- Demo data: `~/odoo/odoo18/odoo/addons/hr_skills/data/hr_skill_demo.xml`
- Demo data: `~/odoo/odoo18/odoo/addons/hr_skills/data/hr_resume_demo.xml`
