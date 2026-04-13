---
Module: hr_work_entry
Version: Odoo 18
Type: Core
Tags: #odoo #odoo18 #hr #work-entry #payroll #attendance
Related Modules: [Modules/HR](odoo-18/Modules/hr.md), [Modules/Resource](odoo-18/Modules/resource.md), [hr_work_entry_contract](modules/hr-contracts.md), [hr_work_entry_holidays](modules/hr-holidays.md)
---

# Work Entry Management (`hr_work_entry`)

## Overview

`hr_work_entry` is the foundational module for time tracking in Odoo HR. It introduces `hr.work.entry` — a record that represents a unit of worked (or non-worked) time for an employee — and `hr.work.entry.type` which classifies those entries (attendance, overtime, leave, etc.).

Work entries are the canonical source for payroll computation. They are generated from contracts (calendar-based) and from leave requests, and validated before being consumed by payroll.

**Depends:** `hr`
**Sequence:** 39
**Models:** 6 (3 new, 3 extended)

## Models

### `hr.work.entry` — Work Entry (NEW)

A time interval assigned to an employee with a specific work entry type. This is the core model — all HR payroll computation flows through work entries.

**File:** `~/odoo/odoo18/odoo/addons/hr_work_entry/models/hr_work_entry.py`

#### Fields

| Field | Type | Description |
|---|---|---|
| `employee_id` | Many2one `hr.employee` (required) | The employee. Domain filters by company. Indexed. |
| `date_start` | Datetime (required) | Start of the work entry. |
| `date_stop` | Datetime (computed/store) | End of the work entry. Computed from `duration` or stored if set directly. |
| `duration` | Float (hours, computed/store) | Duration in hours. Computed as `(date_stop - date_start).total_seconds() / 3600`. Uses caching for performance. |
| `work_entry_type_id` | Many2one `hr.work.entry.type` | Type of work entry. Defaults to first found type. Domain filters by country. Indexed. |
| `code` | Char (related) | Related from `work_entry_type_id.code`. |
| `external_code` | Char (related) | Related from `work_entry_type_id.external_code`. |
| `color` | Integer (related, readonly) | Related from `work_entry_type_id.color` — used in calendar view. |
| `state` | Selection | `draft` / `validated` / `conflict` / `cancelled`. Default `draft`. |
| `active` | Boolean | Default `True`. When `state = 'cancelled'`, `active` flips to `False`. |
| `conflict` | Boolean (computed) | True when `state = 'conflict'`. Used to sort conflicting entries first. |
| `company_id` | Many2one `res.company` | Required. Defaults to `env.company`. |
| `department_id` | Many2one `hr.department` | Related from `employee_id.department_id`. Stored. |
| `country_id` | Many2one `res.country` | Related from `employee_id.company_id.country_id`. |
| `name` | Char (required, computed) | Format: `"<work_entry_type.name>: <employee.name>"` or `"Undefined"` if employee missing. |

#### SQL Constraints

```sql
('_work_entry_has_end',         -- date_stop must be set
 check (date_stop IS NOT NULL))

('_work_entry_start_before_end',  -- start must be before stop
 check (date_stop > date_start))

('_work_entries_no_validated_conflict',  -- PostgreSQL GIST EXCLUDE
 EXCLUDE USING GIST (
     tsrange(date_start, date_stop, '()') WITH &&,
     int4range(employee_id, employee_id, '[]') WITH =
 )
 WHERE (state = 'validated' AND active = TRUE)
 -- Prevents overlapping validated work entries for the same employee
)
```

The `EXCLUDE` constraint uses PostgreSQL's GiST index for conflict detection. This handles concurrent transactions that could create invisible overlaps.

#### Key Methods

- **`action_validate()`** — Validates work entries.
  ```python
  def action_validate(self):
      work_entries = self.filtered(lambda w: w.state != 'validated')
      if not work_entries._check_if_error():
          work_entries.write({'state': 'validated'})
          return True
      return False
  ```
  Returns `True` if validation succeeded, `False` if conflicts were found.

- **`_check_if_error()`** — Checks for undefined types and overlapping entries.
  - Sets `state = 'conflict'` on entries with no `work_entry_type_id`
  - Calls `_mark_conflicting_work_entries()` which uses SQL `tsrange` overlap detection

- **`_mark_conflicting_work_entries(start, stop)`** — Raw SQL query:
  ```sql
  SELECT b1.id, b2.id
    FROM hr_work_entry b1
    JOIN hr_work_entry b2
      ON b1.employee_id = b2.employee_id
     AND b1.id <> b2.id
   WHERE b1.date_start <= %(stop)s
     AND b1.date_stop >= %(start)s
     AND b1.active = TRUE
     AND b2.active = TRUE
     AND tsrange(b1.date_start, b1.date_stop, '()')
         && tsrange(b2.date_start, b2.date_stop, '()')
  ```
  All conflicting entries are set to `state = 'conflict'`.

- **`write(vals)`** — State machine for `active` and `state`:
  - `state = 'draft'` → `active = True`
  - `state = 'cancelled'` → `active = False`
  - `active = True` → `state = 'draft'`
  - `active = False` → `state = 'cancelled'`

- **`_unlink_except_validated_work_entries()`** — `@api.ondelete` prevents deletion of validated entries. Raises `UserError`.

- **`_error_checking(start, stop, skip, employee_ids)`** — Context manager wrapping `create/write/unlink`:
  ```python
  with self._error_checking(employee_ids=[...]):
      super().write(vals)
  # On exit: resets conflict state on nearby entries, then re-checks
  ```
  Uses `hr_work_entry_no_check` context to prevent recursive checking. Handles `OperationalError` (dead cursor) gracefully.

#### Indexes

```sql
CREATE INDEX hr_work_entry_date_start_date_stop_index
ON hr_work_entry(date_start, date_stop)
```

---

### `hr.work.entry.type` — Work Entry Type (NEW)

Classifies work entries. Each type has a `code` used in payroll integrations.

**File:** `~/odoo/odoo18/odoo/addons/hr_work_entry/models/hr_work_entry.py`

#### Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char (required, translate) | Display name. |
| `code` | Char (required) | Payroll code. Changing it can break external integrations. |
| `external_code` | Char | Used to export data to third-party payroll systems. |
| `color` | Integer (default 0) | Calendar color coding. |
| `sequence` | Integer (default 25) | Display order. |
| `active` | Boolean (default True) | Allows hiding without removing. |
| `country_id` | Many2one `res.country` | Country-specific work entry types. |
| `country_code` | Char (related) | From `country_id.code`. |

#### Constraints

- **`_check_work_entry_type_country`** — Prevents changing the country of the `work_entry_type_attendance` reference entry, or of any type currently in use by work entries.

- **`_check_code_unicity`** — Ensures each `code` is unique within a country scope. Types with `country_id=False` share a global namespace for their code.

#### Default Data (installed with module)

| XML ID | Name | Code | Color |
|---|---|---|---|
| `work_entry_type_attendance` | Attendance | `WORK100` | 0 |
| `overtime_work_entry_type` | Overtime Hours | `OVERTIME` | 4 |

---

### `hr.user.work.entry.employee` — Personal Calendar Filter (NEW)

Associates a user with employees for filtering the work entry calendar view.

**File:** `~/odoo/odoo18/odoo/addons/hr_work_entry/models/hr_work_entry.py`

#### Fields

| Field | Type | Description |
|---|---|---|
| `user_id` | Many2one `res.users` | Required. Defaults to `env.user`. Ondelete cascade. |
| `employee_id` | Many2one `hr.employee` | Required. |
| `active` | Boolean (default True) | |

#### Constraints

```sql
('user_id_employee_id_unique', 'UNIQUE(user_id, employee_id)')
-- Prevents the same employee twice per user
```

---

### `resource.calendar.attendance` — Working Hours (EXTENDED)

Attaches a work entry type to a working hour band in the resource calendar.

**File:** `~/odoo/odoo18/odoo/addons/hr_work_entry/models/resource.py`

#### Fields

| Field | Type | Description |
|---|---|---|
| `work_entry_type_id` | Many2one `hr.work.entry.type` | Default: `work_entry_type_attendance`. Groups: `hr.group_hr_user`. |

#### Key Methods

- **`_copy_attendance_vals()`** — Preserves `work_entry_type_id` when duplicating attendance lines.

---

### `resource.calendar.leaves` — Time Off Calendar (EXTENDED)

Attaches a work entry type to calendar-level time off (global leaves, not employee-specific).

**File:** `~/odoo/odoo18/odoo/addons/hr_work_entry/models/resource.py`

#### Fields

| Field | Type | Description |
|---|---|---|
| `work_entry_type_id` | Many2one `hr.work.entry.type` | Groups: `hr.group_hr_user`. |

#### Key Methods

- **`_copy_leave_vals()`** — Preserves `work_entry_type_id` on leave line duplication.

---

### `hr.employee` — Employee (EXTENDED)

Adds a computed flag and a smart button to open the employee's work entry calendar.

**File:** `~/odoo/odoo18/odoo/addons/hr_work_entry/models/hr_employee.py`

#### Fields

| Field | Type | Description |
|---|---|---|
| `has_work_entries` | Boolean (computed, groups) | True if the employee has any `hr.work.entry` records. Groups: `base.group_system`, `hr.group_hr_user`. |

#### Key Methods

- **`_compute_has_work_entries()`** — Raw SQL for performance:
  ```python
  SELECT id, EXISTS(SELECT 1 FROM hr_work_entry WHERE employee_id = e.id limit 1)
    FROM hr_employee e
   WHERE id in %s
  ```
  Avoids ORM overhead for large employee sets.

- **`action_open_work_entries(initial_date=False)`** — Opens work entry calendar for the employee.
  ```python
  ctx = {'default_employee_id': self.id}
  if initial_date:
      ctx['initial_date'] = initial_date
  return {
      'type': 'ir.actions.act_window',
      'name': _('%s work entries', self.display_name),
      'view_mode': 'calendar,list,form',
      'res_model': 'hr.work.entry',
      'context': ctx,
      'domain': [('employee_id', '=', self.id)],
  }
  ```

---

## Key Relationships

```
hr.employee
  └── hr.contract
        └── hr.work.entry (via contract_id)
              └── hr.work.entry.type

hr.leave
  └── hr.work.entry (via leave_id, in hr_work_entry_holidays)
        └── hr.work.entry.type (via work_entry_type_id)
              └── hr.leave.type (via leave_type_ids, in hr_work_entry_contract)

resource.calendar
  ├── resource.calendar.attendance
  │     └── hr.work.entry.type (optional per band)
  └── resource.calendar.leaves
        └── hr.work.entry.type (optional per global leave)
```

---

## L4: How Work Entries Relate to Attendance and Payroll

### Work Entry Generation (from Calendar)

`hr_work_entry_contract` generates work entries from the contract's `resource.calendar_id`:

```
hr.contract.generate_work_entries(date_start, date_stop)
  └── hr.contract._generate_work_entries(datetime_start, datetime_stop)
        └── hr.contract._get_work_entries_values(date_start, date_stop)
              └── hr.contract._get_contract_work_entries_values(start_dt, end_dt)
                    ├── calendar._attendance_intervals_batch() → attendance intervals
                    ├── resource.calendar.leaves → leave intervals
                    ├── (attendance - leaves) → work entries with work_entry_type_id
                    └── (leaves & schedule) → leave work entries
```

Each attendance interval creates a `hr.work.entry` record with `work_entry_type_id` pointing to `work_entry_type_attendance` (or a custom type from the calendar band). Each leave interval creates a leave work entry.

### Work Entry Generation (from Leaves)

`hr_work_entry_holidays` links leave approvals to work entries:

```
hr.leave.action_validate()
  → creates hr.work.entry records with:
      leave_id = hr.leave.id
      work_entry_type_id = hr.leave.holiday_status_id.work_entry_type_id
```

### Validation State Machine

```
draft → [action_validate()] → validated
                          ↓ (if conflict detected)
                       conflict

draft → (write active=False) → cancelled
validated → (write active=False) → cancelled  (requires state != 'conflict')
```

### Conflict Detection Layers

1. **SQL EXCLUDE constraint** — Prevents overlapping `validated` work entries at the DB level.
2. **`_check_if_error()`** — On `create/write`, marks undefined-type entries and overlapping entries as `conflict`.
3. **`_error_checking` context manager** — Wraps write/create to reset and re-check conflicts on surrounding entries.

### Payroll Consumption

Validated work entries are consumed by payroll modules (e.g., `hr_payroll`). The `code` field on `hr.work.entry.type` maps to salary rules in the payroll engine.

### Duration Computation

Duration is normally computed as a simple time difference. However, for leave entries (identified by `work_entry_type_id.is_leave = True`), the contract's `hr_work_entry_contract` module overrides `_compute_date_stop` and `_get_duration_batch` to use the resource calendar's working hours:

```python
def _compute_date_stop(self):
    if work_entry._get_duration_is_valid():  # is_leave
        calendar = work_entry.contract_id.resource_calendar_id
        work_entry.date_stop = calendar.plan_hours(duration, date_start, compute_leaves=True)
```

This ensures leave duration is measured in working hours, not calendar hours.