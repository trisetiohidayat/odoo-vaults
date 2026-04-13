# HR Org Chart

## Overview
- **Name**: HR Org Chart (`hr_org_chart`)
- **Category**: Human Resources
- **Depends**: `hr`, `web_hierarchy`
- **Version**: 1.0
- **License**: LGPL-3
- **Auto-install**: True (with `hr`)

Extends the employee form with an interactive organizational chart showing N+1 (manager), N+2 (manager's manager), and direct subordinates.

## Models

### `hr.employee` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `subordinate_ids` | One2many | All subordinates (direct + indirect), computed |
| `is_subordinate` | Boolean | Whether current user is subordinate of this employee |
| `child_count` | Integer | Direct subordinates count |
| `child_all_count` | Integer | Indirect subordinates count |
| `department_color` | Integer | Department color (related) |

- `_get_subordinates`: Recursively computes all subordinates
- `_compute_subordinates`: Sets `subordinate_ids` and `child_all_count`
- `_compute_is_subordinate`: Checks if current user is subordinate
- `_compute_child_count`: Counts direct child employees

### `hr.employee.public` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `subordinate_ids` | One2many | Related to employee |
| `is_subordinate` | Boolean | Related |
| `child_count`, `child_all_count` | Integer | Computed via `_compute_from_employee` |
| `department_color` | Integer | Related |

### `hr_org_chart.mixin` (Mixin's helper)
Provides org chart field definitions that can be reused in other apps.

## Key Features
- N+1 manager display on employee form
- N+2 hierarchy
- Direct and indirect subordinates count
- Department color coding
- Interactive hierarchy widget via `web_hierarchy`

## Related
- [Modules/HR](Modules/hr.md) - Core HR module
- [Modules/web_hierarchy](Modules/web_hierarchy.md) - Hierarchy tree widget
