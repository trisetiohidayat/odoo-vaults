# Odoo 18 - hr_contract Module

## Overview

Employee contract management module. Defines the contract model with state machine, wage computation, and automatic lifecycle transitions via cron. Handles contract scheduling, permit expiry tracking, and calendar sync.

## Source Path

`~/odoo/odoo18/odoo/addons/hr_contract/`

## Key Model

### hr.contract (`hr.contract`)

Employee contract. Inherits `mail.thread`, `mail.activity.mixin`.

**Key Fields:**
- `name`: Contract reference, required.
- `active`: Boolean (default `True`).
- `employee_id` (`hr.employee`): Contract holder.
- `active_employee`: Related to `employee_id.active`.
- `department_id`: Computed from `employee_id.department_id` (store=True).
- `job_id`: Computed from `employee_id.job_id` (store=True).
- `resource_calendar_id`: Working schedule. Computed from `employee_id.resource_calendar_id` (store=True). Default: company calendar. Synced to employee on contract start.
- `date_start`: Contract start date, required.
- `date_end`: Contract end date (nullable for indefinite contracts).
- `trial_date_end`: Trial period end date.
- `wage`: Monthly gross wage, required.
- `contract_wage`: Computed from `_get_contract_wage()`.
- `state`: Selection: `draft` (New), `open` (Running), `close` (Expired), `cancel` (Cancelled). Default: `draft`.
- `kanban_state`: Selection: `normal` (Ongoing), `done` (Ready/Incoming), `blocked` (Warning). Default: `normal`.
- `structure_type_id` (`hr.payroll.structure.type`): Salary structure type. Computed per company country or fallback.
- `contract_type_id` (`hr.contract.type`): Contract type (e.g., full-time, part-time).
- `company_id`: Required. Computed from `employee_id.company_id` (store=True).
- `hr_responsible_id` (`res.users`): HR person responsible for contract.
- `calendar_mismatch`: Boolean — employee's calendar differs from contract's calendar.
- `first_contract_date`: Related from `employee_id.first_contract_date`.
- `notes`: HTML notes field.
- `contracts_count`: Related field from `employee_id.contracts_count` (group-restricted).

**Kanban State Semantics:**
- `draft` + `kanban_state=done` = "Incoming" (will auto-transition to `open` when `date_start` is reached).
- `open` + `kanban_state=blocked` = "Pending" (contract about to expire — set by cron).
- `open` + `kanban_state=blocked` also set when work permit is expiring.

**Key Methods:**
- `_compute_employee_contract()`: Syncs `job_id`, `department_id`, `resource_calendar_id`, `company_id` from `employee_id` when set.
- `_compute_structure_type_id()`: Sets default `hr.payroll.structure.type` based on company's country. Falls back to country-independent structure if no country-specific one exists.
- `_compute_calendar_mismatch()`: `resource_calendar_id != employee_id.resource_calendar_id`.
- `_compute_contract_wage()`: Calls `_get_contract_wage()` → `_get_contract_wage_field()`.
- `_get_contract_wage()`: Returns value of the wage field. Override point for country-specific wage computation.
- `_get_contract_wage_field()`: Returns `'wage'` — the name of the wage field. Override in localization modules.
- `_is_fully_flexible()`: `True` if no `resource_calendar_id` set on contract.
- `_check_current_contract()`: SQL constraint check — no overlapping active contracts for same employee. Excludes `draft` (unless `kanban_state=done`) and `cancel`.
- `_check_dates()`: `date_start < date_end`.
- `_assign_open_contract()`: Writes `contract_id` to `employee_id`.
- `_get_employee_vals_to_update()`: Returns dict to update on employee when contract becomes open.
- `_track_subtype()`: Returns `mt_contract_pending` on open+blocked, `mt_contract_close` on close.

**Cron Method — `update_state()`:**
1. Finds contracts expiring within `company.contract_expiration_notice_period` days. Schedules activity + message_post, sets `kanban_state=blocked`.
2. Finds contracts with work permits expiring within `company.work_permit_expiration_notice_period`. Same treatment.
3. Closes contracts past `date_end` or work permit expiry date.
4. Opens contracts where `state=draft` + `kanban_state=done` + `date_start <= today`.
5. Auto-sets `date_end` on closed contracts that are immediately followed by another contract.

**`_safe_write_for_cron()`:**
- When called from cron, commits per-record after each write (auto-commit for reliability).
- When called normally, does a single write.
- Wrapped in `savepoint` per record; catches `ValidationError` and logs it without failing the whole batch.

**State Transitions:**
- `draft` → `open`: via `write({'state': 'open'})` or via cron when `kanban_state=done` and `date_start` reached.
- `open` → `close`: via `write({'state': 'close'})`, via cron when `date_end` passed, or when work permit expires.
- `close` → `open`: Not automatic. Must create new contract.

**Sync on State Change:**
- On write to `state='open'`: calls `_assign_open_contract()`.
- On write to `state='close'`: if no `date_end` set, auto-sets to `max(today, date_start)`.
- On `resource_calendar_id` change: syncs to employee if contract is open (or draft+done with first contract).
- On `kanban_state` change: if `state` changed without `kanban_state`, resets `kanban_state='normal'`.

---

### hr.contract.type (`hr.contract.type`)

Contract type classification.

**Key Fields:**
- `name`: Type name (required).
- `code`: Type code (auto-computed from name via onchange if empty).
- `sequence`: Display order.
- `country_id`: Country association (for localization).

Minimal model (~23 lines). Code auto-set from name via onchange: `code = name.upper().replace(' ', '_')[:8]`.

## Cross-Model Relationships

| Model | Field | Purpose |
|-------|-------|---------|
| `hr.contract` | `employee_id` | Contract holder |
| `hr.contract` | `structure_type_id` | Salary structure (from `hr_payroll`) |
| `hr.contract` | `resource_calendar_id` | Working hours schedule |
| `hr.employee` | `contract_id` (inverse) | Current active contract |
| `hr.contract.type` | (via field) | Contract type classification |

## Edge Cases & Failure Modes

1. **Overlapping contracts**: `_check_current_contract()` SQL constraint prevents overlap. However, draft contracts (kanban_state != done) are excluded from the check, allowing draft preparation.
2. **No end date on closed contract**: `write()` auto-sets `date_end = max(today, date_start)` when closing.
3. **Contract followed by new contract**: Cron auto-sets `date_end` of closed contract to `next_contract.date_start - 1 day` to avoid work entry gaps.
4. **Work permit expiry**: Both the contract and the employee record track work permit expiry. Cron checks both and sets `kanban_state=blocked` for either condition.
5. **Employee calendar sync**: When `resource_calendar_id` changes on an open contract, employee's calendar is updated. This allows contract-level schedule changes.
6. **Fully flexible employees**: `_is_fully_flexible()` returns True if no calendar set on contract. This bypasses attendance expectations and overtime computation in `hr_attendance`.
7. **Country-specific wage**: `_get_contract_wage_field()` returns `'wage'` by default. Localization modules override this to point to country-specific wage fields (e.g., `wage` vs `hourly_wage` vs `l10n_*_wage`).
8. **Structure type by country**: `_compute_structure_type_id()` auto-selects based on `company_id.country_id`. If country has no structure, falls back to country-independent structure.

## Security Groups

- `hr_contract.group_hr_contract_employee_manager`: Access to `contracts_count` field on employee.
- `hr.group_hr_user`: Implicit — required for contract management UI.

## Workflow

```
Create contract (draft, kanban_state=normal)
        ↓
Set kanban_state=done ("Ready")
        ↓
Cron: date_start reached
        ↓
state → open
employee.contract_id updated
employee.resource_calendar_id synced
        ↓
Cron: date_end approaching (within notice period)
        ↓
kanban_state → blocked
activity scheduled on hr_responsible
message posted
        ↓
Cron: date_end passed
        ↓
state → close
date_end auto-set if missing
        ↓
New contract created
        ↓
Previous contract date_end auto-set to new.start - 1 day
```

## Integration Points

- **hr**: Uses `hr.employee`, `hr.department`, `hr.job`. Syncs `resource_calendar_id`, `job_id`, `department_id` from employee.
- **resource**: Working schedule from `resource.calendar`. Overtime calculations use contract calendar.
- **hr_payroll**: `hr.payroll.structure.type` for salary structure. `hr.contract` does not depend on `hr_contract` type — it uses `hr.contract.type` directly.
- **mail**: Threading and activity scheduling for contract expiry warnings.