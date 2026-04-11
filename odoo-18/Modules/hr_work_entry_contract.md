---
Module: hr_work_entry_contract
Version: 18.0.0
Type: addon
Tags: #odoo18 #hr_work_entry_contract
---

## Overview
Work Entries - Contract. The core module for generating and managing work entries from contracts. Extends `hr.contract` with work entry generation logic, `hr.employee` with generation triggers, `hr.work.entry` with contract linking and conflict detection, and `resource.calendar` to filter leave-type attendances. Introduces `HrWorkEntryRegenerationWizard` for regenerating work entries. This is a foundational payroll module.

## Models

### hr.contract (Extension)
Inherits from: `hr.contract`
File: `~/odoo/odoo18/odoo/addons/hr_work_entry_contract/models/hr_contract.py`

| Field | Type | Description |
|-------|------|-------------|
| date_generated_from | Datetime | Lower bound of generated work entries; `readonly=True`, default=today midnight |
| date_generated_to | Datetime | Upper bound; `readonly=True`, default=today midnight |
| last_generation_date | Date | Most recent cron-triggered generation date |
| work_entry_source | Selection | `calendar` (default) — source for work entries generation |
| work_entry_source_calendar_invalid | Boolean | `compute`: True if source=calendar but no calendar set |

**Key Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_default_work_entry_type_id | self | int | `@ormcache`: returns `work_entry_type_attendance` ID |
| _get_leave_work_entry_type | leave | record | Returns `leave.work_entry_type_id` |
| _get_interval_work_entry_type | interval | record | Returns interval's `work_entry_type_id` or default attendance |
| _get_attendance_intervals | start_dt, end_dt | dict | Returns `{resource: Intervals}` batched by calendar; skips non-calendar contracts |
| _get_lunch_intervals | start_dt, end_dt | dict | Same as above, for lunch intervals |
| _get_leave_domain | start, end | domain | Domain for `resource.calendar.leaves` search |
| _get_resource_calendar_leaves | start, end | recordset | Searches `resource.calendar.leaves` in the contract's calendar |
| _get_contract_work_entries_values | date_start, date_stop | list of dict | Core generation: computes attendance intervals, subtracts leave intervals, creates work entry dicts |
| _get_work_entries_values | date_start, date_stop | list of dict | Wrapper; handles timezone conversion |
| has_static_work_entries | self | bool | Returns `True` if `work_entry_source == 'calendar'` |
| generate_work_entries | date_start, date_stop, force | records | Public entry point; groups contracts by (company, tz); calls `_generate_work_entries` |
| _generate_work_entries | date_start, date_stop, force | records | Core: cancels work entries for cancelled contracts, respects `date_generated_from/to`, batches by tz, writes `last_generation_date` |
| _remove_work_entries | self | None | Unlinks work entries outside contract period on `date_end` change |
| _cancel_work_entries | self | None | Unlinks non-validated work entries on `state`='draft' or 'cancel' |
| write | vals | bool | On `date_end`/`date_start` change: removes outside work entries; on `state` 'draft'/'cancel': cancels entries; on dependent fields: triggers recomputation |
| _c ron_generate_missing_work_entries | @api.model | None | Scheduled action: generates missing work entries for current month; batch size 100; retriggers if more pending |

### hr.employee (Extension)
Inherits from: `hr.employee`
File: `~/odoo/odoo18/odoo/addons/hr_work_entry_contract/models/hr_employee.py`

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| generate_work_entries | date_start, date_stop, force | records | Delegates to `current_contracts.generate_work_entries()` or all open/close contracts |

### hr.work.entry (Extension)
Inherits from: `hr.work.entry`
File: `~/odoo/odoo18/odoo/addons/hr_work_entry_contract/models/hr_work_entry.py`

| Field | Type | Description |
|-------|------|-------------|
| contract_id | Many2one(hr.contract) | Required on write; auto-set by `_set_current_contract` |
| employee_id | Many2one | Domain: only employees with open/pending contracts |

**SQL Performance:**
- `init`: Creates partial index `hr_work_entry_contract_date_start_stop_idx` on `(contract_id, date_start, date_stop)` WHERE `state IN ('draft', 'validated')`
- `_init_column('contract_id')`: Migrates existing NULL `contract_id` values using a `LEFT JOIN` with `hr_contract` by date range

**Key Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _set_current_contract | vals | dict | Sets `contract_id` by finding the contract whose dates cover `date_start`/`date_stop`. Raises `ValidationError` if no contract or multiple contracts overlap |
| create | vals_list | records | Auto-sets `contract_id` via `_set_current_contract` before create |
| _onchange_contract_id | self | None | `@onchange('employee_id', 'date_start', 'date_stop')`: auto-assigns `contract_id` |
| _compute_date_stop | self | None | For leave-type entries: uses `contract_id.resource_calendar_id.plan_hours(duration, date_start)` |
| _is_duration_computed_from_calendar | self | bool | Returns `True` for leave work entries (`work_entry_type_id.is_leave=True`) |
| _get_duration_batch | self | dict | Computes duration for leave entries via `calendar._attendance_intervals_batch` → `employees._get_work_days_data_batch` |
| _get_duration_is_valid | self | bool | Returns `work_entry_type_id.is_leave` |
| _check_if_error | self | bool | Extends parent: also calls `_mark_leaves_outside_schedule` |
| _get_leaves_entries_outside_schedule | self | recordset | Returns leave entries not in validated/cancelled state |
| _mark_leaves_outside_schedule | self | bool | Detects leave entries entirely outside contract calendar; sets `state='conflict'` |
| _to_intervals | self | WorkIntervals | Converts work entries to `WorkIntervals` objects (pytz.utc) |
| _from_intervals | cls, intervals | recordset | Converts `WorkIntervals` back to `hr.work.entry` records |

### hr.work.entry.type (Extension)
Inherits from: `hr.work.entry.type`
File: `~/odoo/odoo18/odoo/addons/hr_work_entry_contract/models/hr_work_entry.py`

| Field | Type | Description |
|-------|------|-------------|
| is_leave | Boolean | `default=False`; `string='Time Off'`; marks types that can be linked to time off types |

### resource.calendar (Extension)
Inherits from: `resource.calendar`
File: `~/odoo/odoo18/odoo/addons/hr_work_entry_contract/models/resource_calendar.py`

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_global_attendances | self | recordset | Returns attendances excluding those with `work_entry_type_id.is_leave=True` (filters out leave-type global time offs) |

### WorkIntervals (Utility Class)
File: `~/odoo/odoo18/odoo/addons/hr_work_entry_contract/models/hr_work_intervals.py`
Not an Odoo model — a Python class mimicking `resource.models.utils.Intervals` but with a key difference: **continuous intervals are NOT merged**. This allows tracking overlapping entries from different sources.

Implements: `__init__`, `__bool__`, `__len__`, `__iter__`, `__reversed__`, `__or__` (union), `__and__` (intersection), `__sub__` (difference), `_merge`.

### hr.work.entry.regeneration.wizard (Transient)
Inherits from: `base.TransientModel`
File: `~/odoo/odoo18/odoo/addons/hr_work_entry_contract/wizard/hr_work_entry_regeneration_wizard.py`

| Field | Type | Description |
|-------|------|-------------|
| earliest_available_date | Date | `compute`: min of contracts' `date_generated_from` |
| latest_available_date | Date | `compute`: max of contracts' `date_generated_to` |
| date_from / date_to | Date | Required; `compute_date_to` sets `to = from + 1 month - 1 day` |
| employee_ids | Many2many(hr.employee) | Required |
| validated_work_entry_ids | Many2many | `compute`: validated entries in date range |
| search_criteria_completed | Boolean | `compute`: True if all required fields filled |
| valid | Boolean | `compute`: True if criteria complete AND no validated entries in range |

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _check_dates | self | None | `@onchange`: auto-corrects `date_from > date_to`, clamps to available range, sets message |
| regenerate_work_entries | self | None | Validates, deactivates existing non-validated entries in range, calls `employee_ids.generate_work_entries()` |

## Data Files
File: `data/hr_work_entry_data.xml` — creates work entry types:
- `LEAVE100` Generic Time Off (is_leave=True)
- `LEAVE105` Compensatory Time Off (is_leave=True)
- `WORK110` Home Working (is_leave=True)
- `LEAVE90` Unpaid (is_leave=True)
- `LEAVE110` Sick Time Off (is_leave=True)
- `LEAVE120` Paid Time Off (is_leave=True)

File: `data/ir_cron_data.xml` — registers `ir_cron_generate_missing_work_entries` cron (nightly)

## Security
File: `security/hr_work_entry_security.xml` — ir.rule: `hr_work_entry` filtered to `company_id IN company_ids`

## Critical Notes
- **`work_entry_source`:** The `Selection` hint in the manifest shows "Attendances" and "Planning" as future options, but currently only `('calendar', 'Working Schedule')` is implemented
- **`is_leave=True` on work entry types:** Critical for `_get_duration_is_valid()` which controls whether duration is computed from the calendar (leave entries)
- **`WorkIntervals` vs `Intervals`:** This is the key architectural difference — work entries for overlapping periods are kept separate, which is needed for conflict detection
- **Cron batch size=100:** To avoid long-running transactions; retriggers itself if more contracts need processing
- **Migration `_init_column`:** The `contract_id` migration is highly optimized (~2ms for 2.6M records vs 7s raw query)
- **v17→v18:** `work_entry_source` field added in v18; `is_leave` added to `hr.work.entry.type` in v17→v18; `resource_calendar._get_global_attendances` filtering added
