---
Module: hr_holidays_contract
Version: 18.0.0
Type: addon
Tags: #odoo18 #hr_holidays_contract
---

## Overview
Hr Holidays Contract. Bridge module between time off and contracts. When this module is active, the resource calendar for a leave is determined by the employee's active contract(s) at the time of the leave, not by the employee's default calendar. Also enforces that a leave cannot span contracts with different working schedules, and splits leaves that end up spanning multiple contracts.

## Models

### hr.leave (Extension)
Inherits from: `hr.leave`
File: `~/odoo/odoo18/odoo/addons/hr_holidays_contract/models/hr_leave.py`

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _compute_resource_calendar_id | self | None | Overrides parent: for employees, searches overlapping contracts and sets `resource_calendar_id` to the first contract's calendar |
| _get_overlapping_contracts | self, contract_states | recordset | Searches contracts overlapping with the leave's date range; respects contract state |
| _check_contracts | self | None | `@constrains('date_from', 'date_to')`: raises `ValidationError` if overlapping contracts have more than 1 distinct `resource_calendar_id`. Note: existing leaves spanning contracts at install time are grandfathered |

### hr.contract (Extension)
Inherits from: `hr.contract`
File: `~/odoo/odoo18/odoo/addons/hr_holidays_contract/models/hr_contract.py`

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _check_contracts | self | None | `@constrains('date_start', 'date_end', 'state')`: delegates to `self._get_leaves()` then calls `holiday._check_contracts()` |
| _get_leaves | self | recordset | Returns leaves overlapping with any of `self`'s date range and belonging to the contract's employee |
| write | vals | bool | When setting `state='open'` or `kanban_state='done'`: (1) detects existing leaves spanning multiple contracts, (2) splits them into per-contract copies, (3) calls `action_refuse()` on the original, (4) creates new leaves for each contract segment |

**`write` on contract state='open' — Split Leave Algorithm:**
When a new contract is activated in the middle of an existing leave:
1. Finds all overlapping leaves
2. For leaves spanning multiple calendars: calls `action_refuse()` on the original
3. Creates new leave copies with date ranges clamped to each contract's period
4. Validates leaves that were previously validated
5. Posts chatter "origin_link" messages on new leaves

### hr.employee.base (Extension)
Inherits from: `hr.employee.base`
File: `~/odoo/odoo18/odoo/addons/hr_holidays_contract/models/hr_employee_base.py`

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| write | vals | bool | Passes `no_leave_resource_calendar_update=True` in context to prevent `hr.employee` from updating leave calendars on employee write |

## Critical Notes
- **`no_leave_resource_calendar_update` context:** Prevents `hr.employee` writes from updating `hr.leave.resource_calendar_id` — with this module, contracts control leave calendars
- **Leave splitting:** When a contract with a different schedule is activated during an existing leave, the leave is split into per-contract copies
- **`_check_contracts` constraint:** A leave CAN be created spanning two contracts IF both contracts have the same calendar (different dates but same schedule is fine)
- **`_compute_resource_calendar_id`:** Uses `request_date_to` and `request_date_from` (not `date_from`/`date_to`) for the search — these are user-facing dates before timezone conversion
- **v17→v18:** No major architectural changes; the leave-splitting logic on contract activation was refined
