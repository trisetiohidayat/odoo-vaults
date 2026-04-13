---
Module: hr_gamification
Version: Odoo 18
Type: Integration
Tags: #odoo #odoo18 #hr #gamification #badges #challenges
Related Modules: [Modules/Gamification](odoo-18/Modules/gamification.md), [Modules/HR](odoo-18/Modules/hr.md)
---

# HR Gamification (`hr_gamification`)

## Overview

`hr_gamification` bridges the Gamification framework with the HR module, allowing badges and challenges to be managed at the employee level. It extends `gamification.badge` and `gamification.badge.user` to link them to `hr.employee` records, and adds computed goal/badge fields to `hr.employee.base`.

**Depends:** `gamification`, `hr`
**Auto-install:** `True`
**Models:** 4 (1 new, 3 extended)

## Models

### `gamification.badge.user` — Badge Awards (EXTENDED)

Links badge awards directly to employees, not just system users.

**File:** `~/odoo/odoo18/odoo/addons/hr_gamification/models/hr_employee.py`

#### Fields

| Field | Type | Description |
|---|---|---|
| `employee_id` | Many2one `hr.employee` | The employee who received the badge. Indexed. |
| `user_id` | Many2one `res.users` | Inherited from base model — the user who received the badge. |
| `badge_id` | Many2one `gamification.badge` | Inherited from base model. |
| `create_date` | Datetime | Inherited from base model — when the badge was awarded. |

#### Constraints

```python
@api.constrains('employee_id')
def _check_employee_related_user(self):
    # Validates that the selected employee belongs to the badge recipient user
    # Checks via allowed_company_ids to respect multi-company rules
```

Raises `ValidationError` if the selected employee is not in the badge recipient user's employee list (accounting for company access).

#### Key Methods

- **`action_open_badge()`** — Opens the badge's form view.
  ```python
  def action_open_badge(self):
      self.ensure_one()
      return {
          'type': 'ir.actions.act_window',
          'res_model': 'gamification.badge',
          'view_mode': 'form',
          'res_id': self.badge_id.id,
      }
  ```

---

### `gamification.badge` — Badges (EXTENDED)

Adds a computed count and an action to view all granted employees.

**File:** `~/odoo/odoo18/odoo/addons/hr_gamification/models/hr_employee.py`

#### Fields

| Field | Type | Description |
|---|---|---|
| `granted_employees_count` | Integer (computed) | Number of employees (not just users) who have received this badge. Computed over `owner_ids.employee_id`. |

#### Key Methods

- **`_compute_granted_employees_count()`** — `@api.depends('owner_ids.employee_id')`
  Counts `gamification.badge.user` records where `employee_id` is set.

- **`get_granted_employees()`** — Smart button action
  Returns an `ir.actions.act_window` targeting `hr.employee.public` with the granted employees. Displays in `kanban,list,form` views.

---

### `hr.employee.base` — Employee Presence & Gamification Mixin (EXTENDED)

Adds gamification goals and badges to the base employee abstract model.

**File:** `~/odoo/odoo18/odoo/addons/hr_gamification/models/hr_employee_base.py`

#### Fields

| Field | Type | Description |
|---|---|---|
| `goal_ids` | One2many `gamification.goal` | Employee goals filtered to `challenge_category = 'hr'`. Computed via `_compute_employee_goals()`. |
| `badge_ids` | One2many `gamification.badge.user` | All badges for this employee (direct or via user). Computed. |
| `has_badges` | Boolean (computed) | True if `badge_ids` is non-empty. |
| `direct_badge_ids` | One2many `gamification.badge.user` | Badges directly linked to `employee_id` (not through user). Inverse of `badge_id.employee_id`. |

#### Key Methods

- **`_compute_employee_goals()`** — `@api.depends('user_id.goal_ids.challenge_id.challenge_category')`
  Filters goals to HR category:
  ```python
  goal_ids = self.env['gamification.goal'].search([
      ('user_id', '=', employee.user_id.id),
      ('challenge_id.challenge_category', '=', 'hr'),
  ])
  ```

- **`_compute_employee_badges()`** — `@api.depends('direct_badge_ids', 'user_id.badge_ids.employee_id')`
  Searches badges by employee OR by user (via linked employee):
  ```python
  badge_ids = self.env['gamification.badge.user'].search([
      '|', ('employee_id', 'in', employee.ids),
           '&', ('employee_id', '=', False),
                ('user_id', 'in', employee.user_id.ids)
  ])
  ```

---

### `res.users` — Users (EXTENDED)

Links goals and badges to the user record.

**File:** `~/odoo/odoo18/odoo/addons/hr_gamification/models/res_users.py`

#### Fields

| Field | Type | Description |
|---|---|---|
| `goal_ids` | One2many `gamification.goal` | All goals for this user. |
| `badge_ids` | One2many `gamification.badge.user` | All badge awards for this user. |

---

## Integration Points

### Gamification Framework

The module inherits from the `gamification` module's models. The gamification system provides:
- `gamification.challenge` — challenge container with category `hr`
- `gamification.goal` — individual goal linked to a user and challenge
- `gamification.badge` — badge definition
- `gamification.badge.user` — badge award record

### HR Layer

- `hr.employee` inherits `hr.employee.base` which is extended by this module
- Employee badges appear on the employee profile (via computed fields)
- Goals are scoped to the `hr` challenge category

---

## L4: What HR Metrics Can Be Gamified

The gamification module's challenge system drives the goal generation. Challenges in the `hr` category include:

### Attendance & Presence
- Badge for perfect monthly attendance
- Challenge for consistent on-time arrivals

### Time Off Management
- Challenge to submit time-off requests in advance
- Goal for maintaining leave balance thresholds

### Performance Goals
- Goal types defined in `gamification.goal.mixin` linked to `hr` challenges
- Custom goal definitions for HR-specific metrics

### Training & Development
- Badge for completing mandatory training courses
- Challenge for cross-skilling milestones

### Collaboration
- Badge for helping colleagues (peer recognition)
- Challenge for knowledge-sharing sessions conducted

### Workflow

```
gamification.challenge (category='hr')
  └── gamification.goal (user_id → res.users)
        └── badge triggered on completion
              └── gamification.badge.user (employee_id → hr.employee)
```

The `hr_gamification` module ensures that `gamification.badge.user` records are directly linkable to `hr.employee`, so badges appear on the employee's profile page and in HR reporting views.