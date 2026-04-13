# HR Maintenance

## Overview
- **Name**: Maintenance - HR (`hr_maintenance`)
- **Category**: Human Resources
- **Depends**: `hr`, `maintenance`
- **Version**: 1.0
- **License**: LGPL-3
- **Auto-install**: True

Bridges HR and Maintenance modules. Tracks equipment assigned to employees and links maintenance requests to employees.

## Models

### `hr.employee` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `equipment_ids` | One2many | Equipment assigned to employee |
| `equipment_count` | Integer | Number of assigned equipment items |

- `_compute_equipment_count`: Counts linked equipment records

### `hr.employee.public` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `equipment_count` | Integer | Related equipment count |

### `maintenance.equipment` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `employee_id` | Many2one | Assigned employee (computed, writable) |
| `department_id` | Many2one | Assigned department (computed, writable) |
| `equipment_assign_to` | Selection | Used by: Employee / Department / Other |
| `owner_user_id` | Many2one | Computed owner based on assignment |
| `assign_date` | Date | Assignment date |

- `_compute_equipment_assign`: Sets employee/department based on `equipment_assign_to`
- `_compute_owner`: Sets owner to employee user / department manager / current user
- `_track_subtype`: Notifies on equipment assignment
- `create`: Subscribes employee and department manager to equipment notifications
- `write`: Subscribes new assignees on change

### `maintenance.request` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `employee_id` | Many2one | Employee linked to this request (default: current user) |
| `owner_user_id` | Many2one | Computed owner (for employee-type requests) |
| `equipment_id` | Many2one | Equipment, filtered to employee's own equipment first |

- `create`: Subscribes employee to request notifications
- `message_new`: Sets requester as employee from email sender's user

## Key Features
- Equipment can be assigned to specific employees or departments
- Maintenance requests can be opened by employees for their own equipment
- Employee equipment count shown on employee kanban/card
- Notification subscribers set on assignment changes

## Related
- [Modules/HR](modules/hr.md) - Core HR module
- [Modules/maintenance](modules/maintenance.md) - Maintenance module
