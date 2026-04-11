---
Module: hr_work_entry_holidays
Version: 18.0.0
Type: addon
Tags: #odoo18 #hr_work_entry_holidays
---

## Overview
Work Entries - Holidays. Bridge between `hr_holidays` (time off) and `hr_work_entry` (work entries). Links leave requests to work entries, automatically creates leave work entries when leaves are validated, detects conflicts between attendance work entries and leaves, and enables approving/refusing leaves directly from the work entry kanban. This module works together with `hr_holidays_contract` which links leave types to work entry types.

## Models

### hr.leave (Extension)
Inherits from: `hr.leave`
File: `~/odoo/odoo18/odoo/addons/hr_work_entry_holidays/models/hr_leave.py`

**Key Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _prepare_resource_leave_vals | self | dict | Adds `work_entry_type_id` from `holiday_status_id.work_entry_type_id` to the resource leave vals |
| _cancel_work_entry_conflict | self | None | Core method: (1) creates leave work entries for this leave, (2) archives work entries fully covered by the leave, (3) unlinks `leave_id` from overlapping entries |
| _validate_leave_request | self | bool | Calls `super()`, then `_cancel_work_entry_conflict()` to replace conflicting attendance entries with leave entries |
| action_refuse | self | action | Extends parent: calls `_regen_work_entries()` after refusal |
| _action_user_cancel | self, reason | action | Extends parent: calls `_regen_work_entries()` after cancellation |
| _regen_work_entries | self | None | Deactivates leave-linked work entries, recreates attendance work entries via `contract_id._get_work_entries_values` |
| _compute_can_cancel | self | None | Overrides parent: a leave cannot be cancelled if its work entries are in `validated` state |
| _get_leaves_on_public_holiday | self | recordset | Excludes `LEAVE110` (sick), `LEAVE210`, `LEAVE280` from public holiday detection |
| write | vals | bool | Wraps validation in `hr.work.entry._error_checking()` context for overlapping date ranges |
| create | vals_list | records | Same error-checking wrapper as `write` |
| action_reset_confirm | self | action | Same error-checking wrapper |

**`_cancel_work_entry_conflict` Algorithm:**
1. Creates leave work entries for the leave date range via `contracts._get_work_entries_values()`
2. Fetches all work entries for the leave's employee in the date range
3. Archives work entries **fully included** in the leave period (`included |= previous - overlapping`)
4. Clears `leave_id` from overlapping (partially covered) entries

### hr.work.entry (Extension)
Inherits from: `hr.work.entry`
File: `~/odoo/odoo18/odoo/addons/hr_work_entry_holidays/models/hr_work_entry.py`

| Field | Type | Description |
|-------|------|-------------|
| leave_id | Many2one(hr.leave) | Linked leave request |
| leave_state | Selection | Related from `leave_id.state` |

**Key Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| write | vals | bool | If `state` set to `'cancelled'`: auto-refuses the linked leave |
| _reset_conflicting_state | self | None | Clears `leave_id` from attendance entries during conflict resolution |
| _check_if_error | self | bool | Also checks for `leave_id` conflicts via `_compute_conflicts_leaves_to_approve` |
| _compute_conflicts_leaves_to_approve | self | bool | SQL query: finds work entries overlapping with `hr_leave` in 'confirm' or 'validate1' state; marks them as conflict |
| action_approve_leave | self | None | Approves the linked leave (handles double validation) |
| action_refuse_leave | self | None | Refuses the linked leave |
| _get_leaves_duration_between_two_dates | cls, employee_id, date_from, date_to | dict | Returns `{leave_type: total_hours}` of validated leave work entries for a payslip computation helper |

### hr.work.entry.type (Extension)
Inherits from: `hr.work.entry.type`
File: `~/odoo/odoo18/odoo/addons/hr_work_entry_holidays/models/hr_work_entry.py`

| Field | Type | Description |
|-------|------|-------------|
| leave_type_ids | One2many(hr.leave.type) | Reverse link; `help="Work entry used in the payslip"` |

### hr.contract (Extension)
Inherits from: `hr.contract`
File: `~/odoo/odoo18/odoo/addons/hr_work_entry_holidays/models/hr_contract.py`

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_leave_work_entry_type | leave | record | Returns `leave.holiday_id.holiday_status_id.work_entry_type_id` if `leave.holiday_id` exists, else `leave.work_entry_type_id` |
| _get_more_vals_leave_interval | interval, leaves | list | Adds `('leave_id', leave[2].holiday_id.id)` to leave interval vals |
| _get_interval_leave_work_entry_type | interval, leaves, bypassing_codes | record | Overrides parent: prioritizes leave-type intervals by code (e.g., sick > public holiday). Selects from `including_holiday_rcleaves` based on bypassing codes |
| _get_sub_leave_domain | self | domain | Extends parent domain with `('holiday_id.employee_id', 'in', self.employee_id.ids)` to include leave-type intervals |

## Data Files
File: `data/hr_payroll_holidays_data.xml` — sets `work_entry_type_id` on default leave types:
- `hr_holidays.holiday_status_comp` → `hr_work_entry_contract.work_entry_type_compensatory` (`LEAVE105`)
- `hr_holidays.holiday_status_unpaid` → `hr_work_entry_contract.work_entry_type_unpaid_leave` (`LEAVE90`)
- `hr_holidays.holiday_status_sl` → `hr_work_entry_contract.work_entry_type_sick_leave` (`LEAVE110`)
- `hr_holidays.holiday_status_cl` → `hr_work_entry_contract.work_entry_type_legal_leave` (`LEAVE120`)

## Critical Notes
- **`leave_id` on `hr.work.entry`:** The core linking field; enables bidirectional navigation between work entries and leave requests
- **Leave work entry creation:** Done in `_validate_leave_request()` (not at create time) — leaves are created as draft and only generate work entries when approved
- **`_get_leaves_on_public_holiday` exclusions:** Sick leave (`LEAVE110`), `LEAVE210`, `LEAVE280` are excluded from public holiday counting — they do NOT double-count as time off on public holidays
- **`_regen_work_entries`:** Called on refuse/cancel to restore attendance entries where the leave was — critical for attendance reconciliation
- **Conflict detection SQL:** Uses a raw SQL query (flushing both models first) for performance — marks overlapping entries as conflict
- **`_compute_can_cancel`:** A validated work entry prevents leave cancellation — this prevents payslip inconsistencies
- **v17→v18:** `leave_id` field was added to `hr.work.entry` in v18; previously the link was implicit through date/employee matching
