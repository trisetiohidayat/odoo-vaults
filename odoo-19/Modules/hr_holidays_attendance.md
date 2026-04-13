# HR Holidays Attendance

## Overview
- **Name**: HR Attendance Holidays (`hr_holidays_attendance`)
- **Category**: Human Resources
- **Depends**: `hr_attendance`, `hr_holidays`
- **Version**: 1.0
- **License**: LGPL-3
- **Auto-install**: True

Converts extra attendance hours to leave allocations. Employees can convert overtime hours into time off.

## Models

### `hr.leave.allocation` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `overtime_deductible` | Boolean | Leave type is deducted from overtime balance |
| `employee_overtime` | Float | Computed employee overtime balance |

- `default_get`: Pre-selects overtime-deductible leave type when `deduct_extra_hours` context is set
- `create`: Validates that employee has enough overtime hours before creating allocation
- `write`: Validates overtime balance when editing allocation duration
- `_get_accrual_plan_level_work_entry_prorata`: Computes worked hours for "Per Hour Worked" accrual frequency

### `hr.leave` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `overtime_deductible` | Boolean | Leave type deducts from overtime |
| `employee_overtime` | Float | Available overtime for employee |

- `_check_overtime_deductible`: Validates overtime balance before approving/confirming leave
- `action_reset_confirm`, `action_approve`: Re-validates on state transitions
- `_validate_leave_request`: Updates attendance overtimes after validation
- `_update_leaves_overtime`: Triggers overtime recalculation for affected dates
- `_force_cancel`: Cancels leave and updates overtimes

### `hr.leave.type` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `overtime_deductible` | Boolean | When approved, extra hours in attendances are deducted |

- `_compute_display_name`: Appends available hours count to leave type name
- `get_allocation_data`: Includes overtime-deductible unspent balance in allocation response

### `hr.attendance.overtime.line` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `compensable_as_leave` | Boolean | Overtime line can be used as time off |

### `hr.attendance.overtime.rule` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `compensable_as_leave` | Boolean | Give back overtime as time off |

- `_extra_overtime_vals`: Propagates `compensable_as_leave` flag; handles `sum` rate combination mode

### `hr.leave.accrual.level` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `frequency` | Selection | Added `worked_hours` option (per hour worked accrual) |

- `_check_worked_hours`: Prevents "worked hours" frequency with accrual at start of period
- `_get_hourly_frequencies`: Includes `worked_hours`

## Key Features
- Employees with overtime can self-request leaves deducted from overtime balance
- Leave type with `overtime_deductible=true` converts attendance overtime to time off
- Accrual plans can use "Per Hour Worked" frequency
- Overtime lines marked as `compensable_as_leave` count toward leave balance

## Related
- [Modules/hr_attendance](odoo-18/Modules/hr_attendance.md) - Attendance tracking
- [Modules/hr_holidays](odoo-18/Modules/hr_holidays.md) - Leave management
- [Modules/hr_work_entry](odoo-17/Modules/hr_work_entry.md) - Work entries for payroll
