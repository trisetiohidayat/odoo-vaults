---
type: module
module: project_hr_skills
tags: [odoo, odoo19, project, hr, skills]
created: 2026-04-06
updated: 2026-04-11
depth: L4
---

# project_hr_skills — L4 Module Documentation

## Quick Access

| Resource | Type | Description |
|---------|------|-------------|
| [Modules/Project](Modules/Project.md) | Module | `project.task`, `user_ids`, assignee model |
| [Modules/HR](Modules/HR.md) | Module | `hr.employee`, `res.users.employee_id` bridge |
| [Modules/hr_skills](Modules/hr_skills.md) | Module | Full `hr_skills` module — `hr.employee.skill`, `hr.skill`, `hr.skill.type`, `hr.skill.level` |
| [Patterns/Security Patterns](Patterns/Security Patterns.md) | Pattern | ACL inheritance, field groups |
| [Core/Fields](Core/Fields.md) | Core | Field types — One2many, related fields |
| [Core/BaseModel](Core/BaseModel.md) | Core | ORM foundation, `_inherit`, related fields |

---

## Module Overview

| Attribute | Value |
|----------|-------|
| **Name** | Project - Skills |
| **Technical Name** | `project_hr_skills` |
| **Category** | Services/Project |
| **Version** | 1.0 |
| **License** | OEEL-1 (Odoo Enterprise Edition License) |
| **Author** | Odoo S.A. |
| **Auto-install** | `True` |
| **CE/EE** | Enterprise Edition only |

> **Note on License:** `OEEL-1` is the Odoo Enterprise Edition License. This module is not available in Community Edition. It depends on `hr_skills` which is also EE-only.

---

## L1: Core Functionality — HR Skills Linked to Project Tasks

### What the Module Does

`project_hr_skills` bridges the HR Skills repository and Project Task management. It enables project managers to **search and filter project tasks by the skills of their assignees** — for example, "show me all tasks assigned to employees with Python skill" or "find tasks that require Accounting expertise."

The module does this by exposing a derived One2many of assignee employee skills directly on the `project.task` form, making skills accessible from the task search view without requiring custom SQL joins.

### The Data Bridge

The module connects four models through dot-access chains:

```
project.task
  └── user_ids (Many2many → res.users)
        └── employee_id (res.users → hr.employee, via hr module's employee_id field)
              └── employee_skill_ids (hr.employee → hr.employee.skill)
                    └── skill_id (hr.skill — the actual skill name)
```

No new data is stored by `project_hr_skills`. It only makes existing traversals accessible through ORM fields.

### What Is NOT in This Module

- Skill requirements on tasks (no "task requires skill X" concept).
- Skill matching/suggestions (does not suggest which employee to assign based on skills).
- Skill-based task allocation or routing.
- Employee skill management (delegated entirely to `hr_skills`).
- Skill display on project/task form view (only the search filter is added).
- Skill expiry handling (handled by `hr_skills` cron jobs).

---

## L2: Field Types, Defaults, and Constraints

### `user_skill_ids` on `project.task`

**File:** `models/project_task.py`

```python
class ProjectTask(models.Model):
    _inherit = "project.task"

    user_skill_ids = fields.One2many(
        'hr.employee.skill',
        related='user_ids.employee_skill_ids'
    )
```

| Property | Value |
|----------|-------|
| **Type** | `One2many` (related) |
| **Target Model** | `hr.employee.skill` |
| **Inverse Field** | `employee_id` on `hr.employee.skill` |
| **Related Field** | `user_ids.employee_skill_ids` on `res.users` |
| **Store** | No — not stored in DB |
| **Read-only** | Implicitly — related One2many fields are always read-only |
| **Copy** | No explicit `copy` — defaults to `True` but meaningless for related fields |

**Field declaration type:** This is declared as a plain `One2many` with `related=`, which Odoo resolves as a **related field** (not a true computed One2many). The distinction matters:
- `fields.One2many(related='...')` — Odoo treats this as a related field; it is read-only and not stored.
- `fields.Many2many(related='...')` — same pattern for Many2many.
- `fields.Char(compute='_compute_x', store=True)` — true computed, optionally stored.

**Why `One2many` instead of `Many2many`:** The traversal goes through a real One2many (`hr.employee.employee_skill_ids`), not a Many2many. An employee can have multiple skill records; each skill record belongs to one employee. This is the canonical One2many direction.

### `employee_skill_ids` on `res.users`

**File:** `models/res_users.py`

```python
class ResUsers(models.Model):
    _inherit = 'res.users'

    employee_skill_ids = fields.One2many(
        related='employee_id.employee_skill_ids'
    )
```

| Property | Value |
|----------|-------|
| **Type** | `One2many` (related) |
| **Target Model** | `hr.employee.skill` |
| **Related** | `employee_id.employee_skill_ids` |
| **Store** | No |
| **Prerequisite** | `res.users.employee_id` must exist (from `hr` module) |

**Role:** This field completes the bridge from `res.users` to `hr.employee.skill`. Without it, the traversal path from `project.task` would be:

```
task → user_ids → employee_id → employee_skill_ids
```

With this field, the path is shortened to:

```
task → user_ids → employee_skill_ids
```

This makes the final `user_skill_ids` on `project.task` read more naturally:

```python
user_skill_ids = fields.One2many(
    related='user_ids.employee_skill_ids'
)
# task.user_ids is a Many2many of res.users
# task.user_ids[0].employee_skill_ids returns hr.employee.skill records
```

### `user_skill_ids` on `report.project.task.user`

**File:** `report/report_project_task_user.py`

```python
class ReportProjectTaskUser(models.Model):
    _inherit = 'report.project.task.user'

    user_skill_ids = fields.One2many(
        'hr.employee.skill',
        related='user_ids.employee_skill_ids',
        string='Skills'
    )
```

| Property | Value |
|----------|-------|
| **Type** | `One2many` (related) |
| **Target Model** | `report.project.task.user` |
| **Base Model** | SQL-backed read model (`_auto = False`) |
| **String** | Explicitly set to `'Skills'` |

**About `report.project.task.user`:** This model (defined in `project` module) is a SQL-view-based analytic model that aggregates task data per user. It is not a standard ORM model — it has no `create()`, `write()`, or `unlink()`. The `related` field still works because Odoo's ORM can traverse across SQL views as long as the join path is valid in the database.

---

## L3: Cross-Module Integration, Override Patterns, and Workflow Triggers

### Cross-Module Integration Map

```
project_hr_skills
│
├── depends: [project, hr_skills]
│
├── EXTENDS project.task (models/project_task.py)
│   └── adds: user_skill_ids (One2many → hr.employee.skill, related)
│
├── EXTENDS res.users (models/res_users.py)
│   └── adds: employee_skill_ids (One2many → hr.employee.skill, related)
│
├── EXTENDS report.project.task.user (report/report_project_task_user.py)
│   └── adds: user_skill_ids (One2many → hr.employee.skill, related)
│
├── EXTENDS view: project.view_task_search_form_project_fsm_base
│   └── adds: Skills filter field in search view
│
└── DEPENDS ON:
    ├── project module:
    │   ├── project.task model (extended)
    │   ├── res.users (extended via project)
    │   └── report.project.task.user model
    └── hr_skills module:
        ├── hr.employee.skill model (traversed, not modified)
        ├── hr.skill model (displayed via skill.name)
        ├── hr.skill.type model
        ├── hr.skill.level model
        └── hr.employee model (user → employee bridge)
```

### Override Pattern: Pure Related Field Extension

`project_hr_skills` does not override any methods, constraints, or hooks. It uses only **related field extension** — a pattern where the module adds no business logic, only exposes existing data traversals through new field declarations.

This is the most lightweight override pattern possible:

```python
# No overrides — just new field declarations
class ProjectTask(models.Model):
    _inherit = "project.task"
    user_skill_ids = fields.One2many(related='user_ids.employee_skill_ids')
```

Compare to `project_sms` which uses hook overrides (`create()`, `write()`). `project_hr_skills` needs no hooks because skills do not change when a task changes — skills are a property of the assignee, not the task. There is no event to hook into.

### Skill Traversal Chain: Full Resolution

When Odoo evaluates `task.user_skill_ids`, it resolves:

```
task.user_skill_ids
  [task.user_ids is a Many2many to res.users]
  → task.user_ids  [set of res.users records, prefetched in batch]
    → for each user: user.employee_skill_ids
        [user.employee_id is a Many2one to hr.employee]
        [employee.employee_skill_ids is a One2many to hr.employee.skill]
      → set of hr.employee.skill records
  [union of all skill records from all assignees]
    → skill.skill_id.name  [display name of the skill]
```

The union is implicit — a task with 3 assignees, where assignee A has 2 skills, B has 1, and C has 0, produces a `user_skill_ids` recordset of 3 `hr.employee.skill` records.

### Skills Filter Domain: Full Resolution

**File:** `views/project_task_views.xml`

```xml
<field name="user_skill_ids"
       string="Skills"
       filter_domain="['|', ('user_ids', '=', False), ('user_skill_ids', 'ilike', self)]"/>
```

**Domain decomposition:**

| Branch | Operator | Evaluated As |
|--------|----------|--------------|
| Left | `('user_ids', '=', False)` | Tasks where `user_ids` is empty (unassigned tasks) |
| Right | `('user_skill_ids', 'ilike', self)` | Tasks where any assignee's skill matches the search string |

**Why `'|'` with `user_ids = False`:** The OR domain short-circuits. If a user enters "Python" in the Skills filter:
1. The `user_ids = False` branch matches unassigned tasks (cheap, no join).
2. The `user_skill_ids ilike 'Python'` branch matches tasks where any assignee has "Python" skill.
3. The OR of both returns the union.

If the search box is empty (`self = ''`):
- `ilike ''` matches everything (empty string is substring of any string).
- The OR returns all tasks (including unassigned ones).
- This is correct behavior — empty filter should not hide any tasks.

**Why `ilike` (case-insensitive) instead of `=`:** Skills are searched by name. Using `ilike` with partial matching (`%term%`) is standard for name searches in Odoo. The `ilike` operator generates SQL: `WHERE skill.name ILIKE '%python%'`.

---

## L4: Version Changes Odoo 18 to 19, Security Deep Dive, and Performance Analysis

### Version History

| Version | Changes |
|---------|---------|
| 1.0 | Initial module — present from Odoo ~16. This version unchanged through Odoo 19. |

The module's simplicity (three Python files, one view XML, no security files, no migrations) means it has been stable across Odoo versions. The `hr_skills` module it depends on has undergone significant refactoring (see below), but the interface `project_hr_skills` exposes has remained unchanged.

### Odoo 18 to 19: `hr_skills` Changes That Affect `project_hr_skills`

While `project_hr_skills` itself did not change, the `hr_skills` module it depends on had significant refactoring in Odoo 19. These changes affect how `project_hr_skills` behaves:

#### 1. `_get_transformed_commands()` Pattern (Odoo 18 → 19)

In Odoo 18, `hr.employee.skill` used direct ORM commands for skill updates (CREATE/WRITE/UNLINK). In Odoo 19, this changed to `_get_transformed_commands()` which enforces business rules during skill updates:

```python
# Odoo 18 pattern
def write(self, vals):
    # Direct field update
    return super().write(vals)

# Odoo 19 pattern
def write(self, vals):
    commands = self._get_transformed_commands(vals)
    return super().write(commands)
```

**Impact on `project_hr_skills`:** None directly. The related `user_skill_ids` on `project.task` reflects the current state of `hr.employee.skill` records. After a skill update, `user_skill_ids` on tasks automatically reflects the new skills — no cache invalidation needed because the field is not stored.

#### 2. `is_certification` and Certification Fallback

Odoo 19 introduced stricter certification handling in `hr_skills`:
- Certifications (`is_certification=True`) can have multiple active records if date ranges differ.
- `get_current_skills_by_employee()` now returns the most-recently-expired certification if no active certification exists.

**Impact on `project_hr_skills`:** When searching for skills on tasks, a task assignee with an expired certification will still appear in search results if that certification is the most-recently-expired one. This could be surprising — "expired" skills still match search filters.

#### 3. `display_warning_message` Field

Odoo 19 added a UI warning field (`display_warning_message`) to `hr.employee.skill` that triggers when `valid_to < valid_from`. This is purely a UI concern and does not affect `project_hr_skills`.

#### 4. `report.project.task.user` Extension — When Added

The `report/report_project_task_user.py` extension may have been added in Odoo 18 or 19. It adds `user_skill_ids` to the task analysis report, enabling grouping and filtering of task statistics by assignee skills.

### Security Deep Dive

#### No ACL Files Shipped

`project_hr_skills` ships **no security files** (`ir.model.access.csv` or `ir.rule`). All security is entirely inherited from its dependencies:

| Model | Access From | Access Group | Implication for `project_hr_skills` |
|-------|------------|-------------|-------------------------------------|
| `project.task` | `project` module ACL | `project.group_project_user` | Standard project users can read/write tasks |
| `hr.employee.skill` | `hr_skills` module ACL | `hr.group_hr_user` | **Only HR users** can read/write skill records |
| `res.users` | `base` module ACL | Standard | All internal users can read `res.users` |
| `hr.employee` | `hr` module ACL | `hr.group_hr_user` | Only HR users can read employee records |
| `report.project.task.user` | `project` module ACL | `project.group_project_user` | Project users can read the report |

#### ACL Cascade Effect on `user_skill_ids`

This creates a critical asymmetry:

```
project_user (project.group_project_user, no hr.group_hr_user)
  → can access project.task
  → can see user_skill_ids field in search view
  → enters "Python" in Skills filter
  → ORM evaluates user_skill_ids domain
    → ORM tries to read hr.employee.skill records
    → hr.group_hr_user ACL blocks the read
    → domain evaluates to: no matches
  → filter returns zero tasks
```

The field is **visible** but returns **no results** for non-HR users. This is the intended design — skill data is HR-confidential and should not be exposed to project-only users. However, it can be confusing for project managers who see the filter but get empty results.

**Resolution:** To see skill data in task searches, a user needs `hr.group_hr_user` access, or the ACL on `hr.employee.skill` must be relaxed to allow `perm_read` for `project.group_project_user`.

#### Portal User Behavior

Portal users (external collaborators) have `share=True` on their `res.users` record. In the standard `hr` module setup, portal users do not have a linked `hr.employee` record. Therefore:

```
portal_user.employee_id  → returns empty hr.employee recordset
portal_user.employee_skill_ids  → returns empty hr.employee.skill recordset
task_assigned_to_portal_user.user_skill_ids  → empty
skill-based search for portal-assigned tasks  → no match
```

Portal-facing project tasks will never match skill-based filters unless a custom `hr.employee` record is created for the portal user and skills are assigned to it.

#### ACL Inheritance Chain

When `project_task_user_rel` is queried for `user_ids`:

```
task.search([('user_skill_ids', 'ilike', 'Python')])
  → ORM generates subquery through:
    project_task_user_rel (m2m table)
      → res_users (via user_id)
        → hr_employee (via employee_id, from hr module)
          → hr_employee_skill (via employee_skill_ids, from hr_skills)
            → hr_skill (via skill_id)
```

If any table in this chain lacks the appropriate ACL, the query returns no results. The most common failure point is `hr_employee_skill` — only readable by `hr.group_hr_user` by default.

### Performance Deep Dive

#### Query Plan Analysis

When a user applies the Skills filter across N tasks:

```sql
-- Simplified SQL equivalent of the domain filter
SELECT t.id
FROM project_task t
WHERE (
    -- Left branch: unassigned tasks
    NOT EXISTS (SELECT 1 FROM project_task_user_rel r WHERE r.task_id = t.id)
    OR
    -- Right branch: tasks where any assignee has matching skill
    EXISTS (
        SELECT 1
        FROM project_task_user_rel ut
        JOIN res_users u ON u.id = ut.user_id
        JOIN hr_employee e ON e.user_id = u.id
        JOIN hr_employee_skill es ON es.employee_id = e.id
        JOIN hr_skill s ON s.id = es.skill_id
        WHERE ut.task_id = t.id
          AND s.name ILIKE '%python%'   -- the search term
    )
)
```

The `ILIKE` on `hr_skill.name` cannot use a standard B-tree index efficiently. A **trigram GIN index** is ideal:

```sql
-- Recommended index for skill name search
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_hr_skill_name_trgm ON hr_skill USING gin (name gin_trgm_ops);
```

Without this index, the `ILIKE '%python%'` performs a full table scan on `hr_skill`.

#### Index Status for All Join Tables

| Table | Column | Index Type | Source | Notes |
|-------|--------|-----------|--------|-------|
| `hr_employee_skill` | `employee_id` | B-tree | `hr_skills` model definition (`index=True`) | Already indexed |
| `hr_employee_skill` | `skill_id` | B-tree | `hr_skills` FK | Already indexed |
| `hr_skill` | `name` | B-tree (default) | `hr_skills` model | Standard index, but not optimal for `ilike` |
| `res_users` | `employee_id` | B-tree | `hr` module FK | Already indexed |
| `project_task_user_rel` | `task_id` | B-tree | `project` module m2m | Already indexed |
| `project_task_user_rel` | `user_id` | B-tree | `project` module m2m | Already indexed |

#### N+1 Query Potential

The related `user_skill_ids` field, when accessed in a loop, does NOT cause N+1 because:

```python
# NOT N+1 — ORM prefetches related records
for task in tasks:
    skills = task.user_skill_ids  # prefetch handles all in batch
    for skill in skills:
        print(skill.skill_id.name)
```

The prefetch mechanism loads all `user_ids` for the task batch, then all `employee_id` records, then all `employee_skill_ids` records, then all `skill_id` records — in 4 batch queries total regardless of N.

**However:** If the search view filter is applied, Odoo must evaluate the domain subquery for each task row. The subquery cannot use prefetch because it is a correlated subquery evaluated per row. With 10,000 tasks, the subquery runs 10,000 times (though PostgreSQL may optimize it).

#### `read_group` Performance on Report Model

When `user_skill_ids` is used in a `read_group` on `report.project.task.user`:

```python
result = env['report.project.task.user'].read_group(
    domain=[],
    fields=['user_skill_ids'],
    groupby=['user_skill_ids.skill_id'],
)
```

This triggers a complex aggregation query joining through the m2m table, `res_users`, `hr_employee`, `hr_employee_skill`, and `hr_skill`. For large datasets, ensure:
1. All columns in the join chain are indexed.
2. The `report.project.task.user` base view is not doing a full table scan on `project_task`.
3. Consider denormalizing skill data into the report view if real-time joins are too slow.

### Edge Cases — Complete Catalog

#### EC-1: Task with no assignees (`user_ids` is empty)

```
task.user_skill_ids  → empty recordset (no users to traverse)
skill-based search: ('user_ids', '=', False) branch matches → task appears in results
```

Unassigned tasks always appear in skills filter results via the left OR branch. This is intentional — it lets users find unassigned tasks as a side-effect of searching for skills.

#### EC-2: Assignee is not an employee (e.g., system user, admin)

```
user = res.users(5)  # system user, no employee_id
user.employee_skill_ids  → empty recordset (employee_id = False → no join)
```

System users, portal users without linked employees, and any `res.users` without `employee_id` set return empty `employee_skill_ids`. Their tasks do not match skill-based searches.

#### EC-3: Employee has skills but `skill_type_id` is inactive

```
skill_type = hr.skill.type(5, active=False)
skill = hr.employee.skill(..., skill_type_id=skill_type.id)
skill.display_name  → still accessible, but filtered in UI
```

`hr.employee.employee_skill_ids` has domain `[('skill_type_id.active', '=', True)]` in the employee form view, but the raw `hr.employee.skill` records still exist in the database. Direct ORM access bypasses the domain unless explicitly applied.

#### EC-4: Multiple assignees with overlapping skills

```
task.user_ids = [Alice, Bob]
Alice has: Python, Java
Bob has: Python, Accounting
task.user_skill_ids = [skill(Python), skill(Java), skill(Python), skill(Accounting)]
```

The recordset contains duplicate `hr.employee.skill` records if multiple assignees have the same skill. The `ilike` search on this recordset will match the task once (OR semantics — task either matches or doesn't).

#### EC-5: Skill level change (employee levels up)

```
skill = hr.employee.skill(..., skill_level_id=level_beginner)
skill_level_id = hr.skill.level(..., name='Expert')  # New level
skill.write({'skill_level_id': level_beginner.id})  # Archive old, create new

task.user_skill_ids  → now shows only the Expert level skill (old archived)
```

`hr_skills` archives the old `hr.employee.skill` record and creates a new one on level change. `project_hr_skills` always reflects the current state — archived skills are not shown.

#### EC-6: Task analysis report with no assignees

```
report.project.task.user  → typically only creates rows for tasks with assignees
task without assignees → no row in the report
user_skill_ids on report → N/A (record doesn't exist)
```

Unassigned tasks are excluded from the report model. Adding `user_skill_ids` to the report extends an already-aggregated view — it works correctly for assigned tasks but cannot surface unassigned ones.

#### EC-7: User's employee is deactivated (`hr.employee.active=False`)

```
employee = hr.employee(..., active=False)
employee.employee_skill_ids  → still returns skill records
```

Deactivating an employee does not cascade to their skill records. The skills remain in the database. A deactivated employee's tasks will still match skill-based searches.

#### EC-8: `ilike` vs `=like` — partial match behavior

```
skill.name = "Python Programming"
search "Python"  → matches (ilike is case-insensitive substring)
search "python"  → matches (ilike normalizes case)
search "py"      → matches (partial match)
search "py%on"   → matches (SQL LIKE pattern with % wildcard)
```

The `ilike` operator uses PostgreSQL's `ILIKE`, which supports both `%` wildcards and case-insensitivity. The filter_domain passes `self` as the literal search string — if a user types `py%on`, it will be interpreted as a LIKE pattern.

---

## Related Documentation

- [Modules/Project](Modules/Project.md) — `project.task`, `user_ids` Many2many, task assignee model
- [Modules/HR](Modules/HR.md) — `hr.employee`, `res.users.employee_id` bridge
- [Modules/hr_skills](Modules/hr_skills.md) — Full `hr_skills` L4 documentation — `hr.employee.skill`, `hr.skill`, `hr.skill.type`, `hr.skill.level`, `_get_transformed_commands()`, certification handling
- [Patterns/Security Patterns](Patterns/Security Patterns.md) — ACL inheritance, field groups, record rules
- [Core/BaseModel](Core/BaseModel.md) — ORM foundation, `_inherit`, related fields, `_rec_name`
- [Core/Fields](Core/Fields.md) — Field types including One2many, related fields, `store`, `copy`
- [Core/API](Core/API.md) — `@api.depends`, `@api.onchange`, ORM method decorators
