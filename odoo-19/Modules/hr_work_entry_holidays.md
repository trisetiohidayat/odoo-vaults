# Time Off in Payslips (hr_work_entry_holidays)

## Overview
- **Category:** Human Resources/Payroll
- **Depends:** `hr_holidays`, `hr_work_entry`
- **Auto-install:** True
- **License:** LGPL-3

Integrates leave requests with the work entry system for payroll. Approved leaves generate corresponding work entries so they appear correctly in payslips.

## Models

### `hr.leave.type` (inherited)
| Field | Type | Description |
|-------|------|-------------|
| `work_entry_type_id` | Many2one | Links leave type to a work entry type for payroll |

### `hr.leave` (inherited)
Extends leave validation and work entry generation:

## Key Methods

### Work Entry Generation
`_cancel_work_entry_conflict()` — core method called on leave validation:
1. Creates new work entries for each leave period (using `work_entry_type_id` from leave type)
2. Finds overlapping existing work entries
3. Archives work entries completely covered by the leave
4. Unlinks leave assignment from overlapping work entries that extend beyond the leave period

### Leave Lifecycle Integration
- `_validate_leave_request()` — calls `_cancel_work_entry_conflict()` after leave approval
- `action_refuse()` — archives linked work entries and regenerates attendance entries for refused leaves
- `_move_validate_leave_to_confirm()` — regenerates work entries when a leave moves to confirmed
- `_action_user_cancel()` — regenerates work entries when a leave is cancelled by user
- `_regen_work_entries()` — deactivates leave work entries and recreates attendance entries for the period

### Work Entry Conflict Detection
- `create()` / `write()` — wraps in `hr.work.entry._error_checking()` context to detect conflicts before saving
- Checks a buffer of 1 day before/after the leave period for timezone tolerance

### Public Holiday Override
`_get_leaves_on_public_holiday()` — excludes certain leave types (codes `LEAVE110`, `LEAVE210`, `LEAVE280`) from the public holiday deduction logic.

### Cancellation Control
`_compute_can_cancel()` — prevents cancelling a leave if validated work entries exist for that leave.

## Post-Init Hook
`_validate_existing_work_entry()` — validates all existing work entries after module installation.

## Related
- [Modules/hr_holidays](odoo-18/Modules/hr_holidays.md) — Leave management
- [Modules/hr_work_entry](odoo-17/Modules/hr_work_entry.md) — Work entries
- [Modules/hr_holidays_attendance](odoo-17/Modules/hr_holidays_attendance.md) — Holidays + Attendance
