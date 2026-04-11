# HR Gamification

## Overview
- **Name**: HR Gamification (`hr_gamification`)
- **Category**: Human Resources
- **Depends**: `gamification`, `hr`
- **Version**: 1.0
- **License**: LGPL-3
- **Auto-install**: True

Bridges the Gamification module with HR. Allows HR officers to send badges to employees (not just generic users). Badges received are displayed on the employee profile.

## Models

### `hr.employee` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `goal_ids` | One2many | Employee HR goals (via `gamification.goal`, category=hr) |
| `badge_ids` | One2many | All badges linked to the employee (directly or via user) |
| `has_badges` | Boolean | Whether the employee has any badges |
| `direct_badge_ids` | One2many | Badges directly linked to the employee |

### `hr.employee.public` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `badge_ids` | One2many | Public view of employee badges |
| `has_badges` | Boolean | Public view of has_badges |

### `gamification.badge.user` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `employee_id` | Many2one | Linked HR employee |
| `has_edit_delete_access` | Boolean | Edit/delete access (HR user or creator) |

- Constrains: `employee_id` must correspond to the badge's `user_id`
- `_notify_get_recipients_groups`: Adds button to view badge from employee profile
- `action_open_badge`: Opens badge form in dialog mode

### `gamification.badge` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `granted_employees_count` | Integer | Count of employees who received this badge |

- `get_granted_employees`: Returns kanban/list/form action for granted employees

### `res.users` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `goal_ids` | One2many | User goals |
| `badge_ids` | One2many | User badges |

## Key Features
- Employees appear in gamification challenges and goals
- HR officers can grant badges to employees
- Badges display on employee public profile
- Grant count tracked per badge

## Related
- [[Modules/gamification]] - Core gamification module
- [[Modules/HR]] - Core HR module
