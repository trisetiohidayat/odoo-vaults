# HR Hourly Cost

## Overview
- **Name**: Employee Hourly Wage (`hr_hourly_cost`)
- **Category**: Services/Employee Hourly Cost
- **Depends**: `hr`
- **Version**: 1.0
- **License**: LGPL-3

Adds an hourly cost field to employees for use by cost calculation modules (e.g., `hr_timesheet`).

## Models

### `hr.employee` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `hourly_cost` | Monetary | Hourly cost currency-aware field, groups=hr.group_hr_user, default=0.0, tracking=True |

## Key Features
- Stores employee hourly cost on the employee record
- Currency-aware monetary field
- Used by `hr_timesheet` for billing rate calculation
- Tracked for audit history

## Related
- [Modules/HR](modules/hr.md) - Core HR module
- [Modules/hr_timesheet](modules/hr_timesheet.md) - Timesheet billing uses hourly cost
