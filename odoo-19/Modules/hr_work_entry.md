---
type: module
module: hr_work_entry
tags: [odoo, odoo19, hr, work-entry, payroll, contract]
created: 2026-04-06
---

# Work Entries

**Source path:** `~/odoo/odoo19/odoo/addons/hr_work_entry/`
**Odoo version:** 19 CE
**License:** LGPL-3
**Module key:** `hr_work_entry`
**Category:** Human Resources/Employees

---

## Overview

The `hr_work_entry` module is the backbone of Odoo's time-tracking and payroll integration system. It manages **work entries** — granular time records representing either working time or absences for each employee per day. Work entries are the source data for payroll computation: validated work entries feed directly into the payroll engine (via `hr_payroll`).

The module's architecture centers on four concerns:
1. **Entry management**: Create, edit, split, and delete work entries
2. **Conflict detection**: Automatically detect and flag overlapping, overlong, or schedule-violating entries
3. **Validation**: Lock validated entries into the payroll system
4. **Generation**: Auto-generate entries from employee contracts, calendars, or attendance records via the `hr.version` model

---

## Dependencies

```
hr_work_entry
  └─ hr (required)
       ├─ resource (required, transitive)
       │    ├─ resource.mixin
       │    ├─ resource.calendar
       │    └─ resource.calendar.attendance
       ├─ hr.version (via hr.employee inheritance)
       └─ hr.contract (via hr.version)
```

**Dependent modules** (require `hr_work_entry`):
- `hr_work_entry_holidays` — leave request integration
- `hr_attendance` — attendance-based entry generation
- `hr_payroll` — payroll computation from validated entries

---

## Module Files

| File | Models Defined | Purpose |
|------|---------------|---------|
| `models/hr_work_entry.py` | `hr.work.entry` | Core work entry record |
| `models/hr_work_entry_type.py` | `hr.work.entry.type` | Entry type taxonomy |
| `models/hr_version.py` | `hr.version` (extends) | Entry generation engine |
| `models/hr_employee.py` | `hr.employee` (extends) | Employee-level entry actions |
| `models/resource_calendar.py` | `resource.calendar` (extends) | Filter global leave from work hours |
| `models/resource_calendar_attendance.py` | `resource.calendar.attendance` (extends) | Per-attendance work entry type |
| `models/resource_calendar_leaves.py` | `resource.calendar.leaves` (extends) | Per-leave work entry type |
| `models/hr_user_work_entry_employee.py` | `hr.user.work.entry.employee` | Personal calendar filter |
| `wizard/hr_work_entry_regeneration_wizard.xml` | Regeneration wizard | Batch regenerate entries |

---

## L1: `hr.work.entry` — Complete Field Reference

**File:** `models/hr_work_entry.py` (~337 lines)

```python
class HrWorkEntry(models.Model):
    _name = 'hr.work.entry'
    _description = 'HR Work Entry'
    _order = 'create_date'
```

### Core Identity

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char | computed | `{type}: {employee}` or "Undefined" |
| `display_name` | Char | computed | `{type} - {duration_h}h{MM}` |
| `active` | Boolean | `True` | `False` = cancelled entry |

### Employee & Contract Linkage

| Field | Type | Notes |
|-------|------|-------|
| `employee_id` | `Many2one(hr.employee)` | Required. Domain: same company or no company. Indexed. |
| `version_id` | `Many2one(hr.version)` | The employee contract/version active on `date`. Required, indexed. Set automatically by `_set_current_contract()` on create. |
| `work_entry_source` | Selection (related) | Inherited from `version_id`: `calendar`, `attendance`, or `planning`. |
| `department_id` | `Many2one(hr.department)` (related, stored) | From `employee_id.department_id`. Stored for search/group performance. |

### The Critical `version_id` — Why It Exists

The `hr.version` model (introduced in Odoo 17 as a successor to `hr.contract`) represents an employee's employment contract at a point in time. An employee can have multiple versions (contracts) over their career, with different work schedules, work entry sources, or benefits.

`version_id` is the **effective contract on the entry's date**. It is set by `_set_current_contract()`:

```python
@api.model
def _set_current_contract(self, vals):
    if not vals.get('version_id') and vals.get('date') and vals.get('employee_id'):
        employee = self.env['hr.employee'].browse(vals.get('employee_id'))
        active_version = employee._get_version(vals['date'])
        return dict(vals, version_id=active_version.id)
    return vals
```

This means:
- The same employee on different dates may have different `version_id` values
- Leave entries and attendance entries generated on either side of a contract change will reference the correct contract
- This enables accurate payroll even when an employee changes contracts mid-period

### Date and Duration

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `date` | Date | required | The calendar day of the entry |
| `duration` | Float (hours) | `8.0` | `> 0` and `<= 24`. Enforced by `_check_duration`. |

### Work Entry Type Linkage

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `work_entry_type_id` | `Many2one(hr.work.entry.type)` | First type found | Domain filtered by country via `_get_work_entry_type_domain()` |
| `display_code` | Char (related) | — | From `work_entry_type_id.display_code` |
| `code` | Char (related) | — | From `work_entry_type_id.code` — used by payroll |
| `external_code` | Char (related) | — | For third-party export |
| `color` | Integer (related) | — | From `work_entry_type_id.color` |
| `amount_rate` | Float | copied from type on create | Pay rate multiplier (e.g., 2.0 = double pay) |

### State Machine

```python
state = fields.Selection([
    ('draft', 'New'),
    ('conflict', 'In Conflict'),
    ('validated', 'In Payslip'),
    ('cancelled', 'Cancelled')
], default='draft')
```

**State transition table:**

| From | To | Trigger | Notes |
|------|----|---------|-------|
| `draft` | `conflict` | `_check_if_error()` called on create/write | Entry has a validation problem |
| `draft` | `validated` | `action_validate()` succeeds | Entry locked for payroll |
| `conflict` | `draft` | `_reset_conflicting_state()` | After user fixes the conflict |
| `conflict` | `validated` | `action_validate()` succeeds | Retry after fixes |
| `draft/conflict` | `cancelled` | `write({'active': False})` or `write({'state': 'cancelled'})` | Sets `active=False` |
| `cancelled` | `draft` | `write({'active': True})` | Resets to `state='draft'` |

### Company and Audit

| Field | Type | Notes |
|-------|------|-------|
| `company_id` | `Many2one(res.company)` | Required, default `env.company`. Set from `employee_id.company_id` on create if not provided. |
| `country_id` | `Many2one(res.country)` (related, searchable) | From `employee_id.company_id.country_id`. Used for country-filtered work entry type domain. |

### Database Index — Performance-Critical

```python
# Line 53 of hr_work_entry.py:
_contract_date_start_stop_idx = models.Index(
    "(version_id, date) WHERE state IN ('draft', 'validated')"
)
```

This is a **partial B-tree index** on `(version_id, date)` for entries in `draft` or `validated` states. It dramatically accelerates:
- The conflict detection queries in `_mark_already_validated_days()`
- The date-range searches in `_check_if_error()`
- The `_reset_conflicting_state()` queries

Without this index, a company with 2.6M work entries (the scale cited in the code comment: "FROM 7s by query to 2ms") would suffer 7-second queries on each entry creation.

---

## L2: Field Types, Defaults, Constraints

### Duration Constraint

```python
@api.constrains('duration')
def _check_duration(self):
    for work_entry in self:
        if float_compare(work_entry.duration, 0, 3) <= 0
           or float_compare(work_entry.duration, 24, 3) > 0:
            raise ValidationError(
                self.env._("Duration must be positive and cannot exceed 24 hours."))
```

**Design rationale:** A day cannot have more than 24 hours of work entries. This is enforced at the ORM level (triggers on write/create) and reinforced by the SQL query in `_mark_conflicting_work_entries()` which uses `HAVING SUM(duration) > 24`. Using `float_compare` with precision 3 avoids floating-point rounding issues.

### `active` ↔ `state` Dualism

Work entries use a dual-state system where `active` and `state` are synchronized:

```python
def write(self, vals):
    # state='draft' → active=True
    if 'state' in vals:
        if vals['state'] == 'draft':
            vals['active'] = True
        elif vals['state'] == 'cancelled':
            vals['active'] = False
            # Only allow cancelling non-conflicting entries directly
            skip_check &= all(self.mapped(lambda w: w.state != 'conflict'))

    if 'active' in vals:
        vals['state'] = 'draft' if vals['active'] else 'cancelled'
```

This means:
- Setting `active=False` is equivalent to cancelling
- Cancelled entries are still queryable (via `active_test=False`)
- The `active` flag drives archive behavior; `state` drives payroll eligibility

### Company Auto-Set on Create

```python
def create(self, vals_list):
    vals_list = [self._set_current_contract(vals) for vals in vals_list]
    company_by_employee_id = {}
    for vals in vals_list:
        # Auto-set amount_rate from type
        if not 'amount_rate' in vals and (work_entry_type_id := vals.get('work_entry_type_id')):
            work_entry_type = self.env['hr.work.entry.type'].browse(work_entry_type_id)
            vals['amount_rate'] = work_entry_type.amount_rate

        # Auto-set company from employee
        if not vals.get('company_id'):
            if vals['employee_id'] not in company_by_employee_id:
                employee = self.env['hr.employee'].browse(vals['employee_id'])
                company_by_employee_id[employee.id] = employee.company_id.id
            vals['company_id'] = company_by_employee_id[vals['employee_id']]
```

This is a bulk-optimized batch: it avoids N employee lookups by caching `company_by_employee_id` keyed by employee ID, then applies the lookup only once per unique employee in the batch.

---

## L3: Cross-Model, Override Patterns, Workflow Triggers, Failure Modes

### `hr_version` — The Entry Generation Engine

**File:** `models/hr_version.py` (~725 lines)

`hr.version` is the central model for generating work entries from an employee's working schedule or attendance records. It inherits from `hr.version` (the base contract model) and adds work-entry-specific logic.

#### Key Fields Added by `hr_work_entry`

| Field | Type | Notes |
|-------|------|-------|
| `date_generated_from` | Datetime | Start of the generated-entry window (updated as generation progresses) |
| `date_generated_to` | Datetime | End of the generated-entry window |
| `last_generation_date` | Date | When entries were last regenerated |
| `work_entry_source` | Selection | `calendar` (default), `attendance`, or `planning` |
| `work_entry_source_calendar_invalid` | Boolean (computed) | True when source=`calendar` but no calendar assigned |

#### The Generation Flow

```
generate_work_entries(date_start, date_stop)
  └─ _generate_work_entries(date_start_tz, date_stop_tz)
       ├─ _get_work_entries_values(date_start, date_stop)
       │    ├─ _get_version_work_entries_values()  [per-tz grouping]
       │    │    ├─ _get_attendance_intervals()   [working hours]
       │    │    ├─ _get_resource_calendar_leaves() [time off]
       │    │    ├─ Interval arithmetic (subtract leaves from attendances)
       │    │    ├─ _get_real_attendance_work_entry_vals()
       │    │    └─ _get_real_leave_work_entry_vals()
       │    └─ _generate_work_entries_postprocess()
       │         ├─ Convert date_start/date_stop → date/duration
       │         ├─ Split entries spanning midnight (timezone)
       │         └─ Merge consecutive same-type entries per day
       └─ create(vals_list)
```

#### Interval-Based Generation

The system uses `odoo.tools.intervals.Intervals` to perform set operations on time periods:

```python
real_attendances = attendances - leaves - worked_leaves
```

Where:
- `attendances`: Working hours from the calendar
- `leaves`: Time-off intervals from `resource.calendar.leaves`
- `worked_leaves`: Work-time intervals (e.g., half-day public holiday treated as work)

This interval arithmetic correctly handles:
- Multi-day leaves
- Overlapping leaves (employee on multiple leave types simultaneously)
- Partial-day leaves
- Flexible-hour calendars (variable working hours)

#### Flexible Hours Handling

When `calendar.flexible_hours = True` (or no calendar):

```python
# For multi-day leaves: occupy 12 AM to average daily hours
one_day_leaves = Intervals([l for l in leaves if l[0].date() == l[1].date()])
multi_day_leaves = leaves - one_day_leaves
real_leaves = (static_attendances & multi_day_leaves) | one_day_leaves
```

This means a 3-day leave on a flexible schedule generates leave entries spanning the full days, not just the declared hours.

#### Timezone-Aware Processing

```python
tz = pytz.timezone(
    resource.tz if version._is_fully_flexible()
    else calendar.tz
)
version_vals += versions._get_version_work_entries_values(
    tz.localize(date_start),
    tz.localize(date_stop))
```

Each version's entries are computed in the employee's timezone, then converted to UTC for storage. The postprocessing step splits entries that span midnight in the employee's local time.

### `action_split` — Entry Splitting

```python
def action_split(self, vals):
    self.ensure_one()
    if self.duration < 1:
        raise UserError("You can't split a work entry with less than 1 hour.")
    if self.duration <= vals['duration']:
        raise UserError("Split duration must be less than existing duration.")
    self.duration -= vals['duration']       # Reduce original
    split_work_entry = self.copy()          # Copy remaining as new
    split_work_entry.write(vals)           # Apply split duration to new
    return split_work_entry.id
```

This is the correct way to handle a partial-day absence: split the 8-hour attendance entry into two pieces, change the type of one piece to the leave type.

### `_error_checking()` — Context Manager Pattern

```python
@contextmanager
def _error_checking(self, start=None, stop=None, skip=False, employee_ids=False):
    try:
        skip = skip or self.env.context.get('hr_work_entry_no_check', False)
        start = start or min(self.mapped('date'), default=False)
        stop = stop or max(self.mapped('date'), default=False)
        if not skip and start and stop:
            domain = (
                Domain('date', '<=', stop)
                & Domain('date', '>=', start)
                & Domain('state', 'not in', ('validated', 'cancelled'))
            )
            if employee_ids:
                domain &= Domain('employee_id', 'in', list(employee_ids))
            work_entries = self.sudo().with_context(hr_work_entry_no_check=True).search(domain)
            work_entries._reset_conflicting_state()
        yield
    except OperationalError:
        skip = True
        raise
    finally:
        if not skip and start and stop:
            work_entries.exists()._check_if_error()
```

This is used in `write()` and `unlink()` to ensure that any operation affecting a date range also re-validates all OTHER entries in that range. The `skip` flag prevents recursive re-entry (when `_check_if_error()` calls `write()` internally).

### Failure Modes

| Failure Mode | Cause | Symptom | Fix |
|-------------|-------|---------|-----|
| `version_id` not set | `_set_current_contract()` failed silently | `ValidationError` or missing contract linkage | Return empty dict to let validation catch it |
| Duration > 24h | Multiple overlapping entries on same day | `state='conflict'` after create | Split or remove overlapping entries |
| Leave outside schedule | Leave entry not matching any calendar attendance | `state='conflict'` after create | Adjust leave dates or calendar |
| Already validated | Attempting to create/validate for already-paid date | `state='conflict'` | Cannot override; payroll is locked |
| Cycle in context manager | OperationalError from nested transaction | `skip=True` and re-raise | Transaction dead-lock; retry |
| Missing timezone | No calendar on contract and no employee timezone | `UserError` in `_generate_work_entries_postprocess` | Assign calendar or set employee timezone |

---

## L4: Performance, Version Changes, Security, Conflict Algorithm

### Performance: Database Index Design

The module handles potentially millions of work entry records. Key optimizations:

#### Index 1: Partial Composite on `(version_id, date)`

```python
_contract_date_start_stop_idx = models.Index(
    "(version_id, date) WHERE state IN ('draft', 'validated')"
)
```

- **Columns**: `(version_id, date)` — covers date-range lookups per contract
- **Partial condition**: Only indexes `draft` and `validated` entries; `conflict` and `cancelled` are excluded
- **Effect**: The `_mark_already_validated_days()` query (which searches by date range per employee) goes from 7 seconds to 2 milliseconds on 2.6M rows

#### SQL Conflict Detection

`_mark_conflicting_work_entries()` uses raw SQL for maximum performance:

```sql
WITH excessive_days AS (
    SELECT employee_id, date
    FROM hr_work_entry
    WHERE active = TRUE
      AND date BETWEEN %(start)s AND %(stop)s
      AND employee_id IN %(employee_ids)s
    GROUP BY employee_id, date
    HAVING 0 >= SUM(duration) OR SUM(duration) > 24
)
SELECT we.id
FROM hr_work_entry we
JOIN excessive_days ed
  ON we.employee_id = ed.employee_id
 AND we.date = ed.date
WHERE we.active = TRUE
```

This is a single-pass SQL query that:
1. Aggregates total duration per employee per day
2. Filters to days exceeding 24 hours
3. Joins back to find all entries on those days
4. Returns IDs to mark as `conflict`

**Scaling**: On very large deployments (millions of rows), the `GROUP BY employee_id, date` can still be slow. The `active=TRUE` filter and partial index help significantly. For companies with >10M entries, consider partitioning the `hr_work_entry` table by month.

#### Interval Operations — O(n log n) vs O(n^2)

The `_mark_leaves_outside_schedule()` method uses Python `Intervals` objects:

```python
entries_intervals = entries._to_intervals()
overlapping_entries = self._from_intervals(entries_intervals & calendar_intervals)
outside_entries |= entries - overlapping_entries
```

The `&` (intersection) operator on `Intervals` is implemented efficiently using interval tree algorithms, not naive O(n^2) pairwise comparison. This is critical when processing monthly batches for thousands of employees.

### Odoo 17 → 18 → 19 Changes

#### Odoo 17 → 18 Key Changes

1. **`hr.contract` replaced by `hr.version`**: Odoo 18 introduced `hr.version` as the new contract model, replacing `hr.contract`. `hr_work_entry` was updated to depend on `hr.version` instead.
2. **`work_entry_source` selection**: The `hr.version.work_entry_source` field supports three sources: `calendar` (default), `attendance`, and `planning`. The attendance and planning sources are provided by separate bridge modules.
3. **Timezone-aware generation**: The `_get_work_entries_values()` method was rewritten to group versions by timezone (`versions_by_tz`) and process each timezone separately, then localize dates correctly.
4. **Flexible hours handling**: The complex interval arithmetic for flexible-hour calendars was added to correctly handle variable schedules.

#### Odoo 18 → 19 Key Changes

1. **`_contract_date_start_stop_idx` partial index**: Added specifically to address performance at scale (2.6M+ entries). The code comment explicitly states the performance improvement: "FROM 7s by query to 2ms".
2. **`@api.ondelete(at_uninstall=False)` on `_unlink_except_validated_work_entries`**: The hook now skips during module uninstall, allowing clean removal of the module.
3. **Company-aware generation batching**: The `generate_work_entries()` method was refactored to group versions by `(company, tz)` tuple and process per company, ensuring that multi-company instances generate entries independently per company.
4. **`_generate_work_entries_postprocess` merge optimization**: Entries with identical `(date, work_entry_type_id, employee_id, version_id, company_id)` are merged by summing duration. This was refined to handle timezone-spanning entries more robustly.
5. **`ormcache()` on type defaults**: `_get_default_work_entry_type_id()` and `_get_default_work_entry_type_overtime_id()` use `@ormcache()` to avoid repeated `env.ref()` lookups for the attendance/overtime types.

### Security Model

#### Access Control

`hr.work.entry` is a sensitive model: it contains payroll data. Access is controlled by:

1. **ACL CSV** (`security/ir.model.access.csv`): Group-based permissions on `hr.work.entry` and `hr.work.entry.type`
2. **Field-level groups**: `has_work_entries` on `hr.employee` is computed and restricted to `base.group_system, hr.group_hr_user`
3. **Record rules**: Standard Odoo multi-company rules apply via `company_id` on all entries
4. **`hr_work_entry_security.xml`**: Module-specific security rules

#### Validated Entries Cannot Be Deleted

```python
@api.ondelete(at_uninstall=False)
def _unlink_except_validated_work_entries(self):
    if any(w.state == 'validated' for w in self):
        raise UserError(_("This work entry is validated. You can't delete it."))
```

This prevents accidental or malicious deletion of payroll source data. The `at_uninstall=False` ensures the check is skipped when the module itself is being uninstalled (data cleanup is allowed).

#### Multi-Company Compliance

Every work entry carries `company_id` (auto-set from the employee's company on create). The `company_id` is:
- Set on all generated entries from the version's company
- Used in `_mark_already_validated_days()`: only checks validated entries within `self.env.company`
- Propagated to generated leave entries

#### Country-Filtered Work Entry Types

```python
def _get_work_entry_type_domain(self):
    if len(self.env.companies.country_id.ids) > 1:
        return [('country_id', '=', False)]
    return ['|', ('country_id', '=', False), ('country_id', 'in', self.env.companies.country_id.ids)]
```

In multi-country deployments, users only see work entry types relevant to their company. Types without a country (global) are always visible.

### Conflict Detection Algorithm — Complete Walkthrough

The `_check_if_error()` method runs four independent checks:

```
Step 1: undefined_type = entries without work_entry_type_id
        → write state='conflict' on these

Step 2: _mark_conflicting_work_entries(start, stop)
        → SQL: find days where SUM(duration) > 24 or <= 0
        → write state='conflict' on all entries on those days

Step 3: _mark_leaves_outside_schedule()
        → For each leave entry:
             Get calendar intervals for the date range
             Compute intersection of leave interval with calendar
             If leave is entirely outside calendar → mark conflict
        → Note: skips flexible-hour calendars and no-calendar versions

Step 4: _mark_already_validated_days()
        → Find all validated entries in the date range for the same company
        → Group by (employee_id, date)
        → Any entry in self that overlaps a validated date → mark conflict
```

Steps 1-3 can be re-run (after fixing the conflict) by calling `action_validate()` again. Step 4 is sticky: once a date is validated, no new entries for that date can be validated in the same payroll period.

### Cron Job — Missing Entry Generation

```python
@api.model
def _cron_generate_missing_work_entries(self):
    today = fields.Date.today()
    start = datetime.combine(today + relativedelta(day=1), time.min)
    stop = datetime.combine(today + relativedelta(months=1, day=31), time.max)

    # Find all versions whose generated windows have gaps this month
    versions_todo = all_versions.filtered(
        lambda v:
        (v.date_generated_from > start or v.date_generated_to < stop) and
        (not v.last_generation_date or v.last_generation_date < today))

    # Batch processing: 100 versions per run
    # Trigger re-run if more pending
    if version_todo_count > BATCH_SIZE:
        self.env.ref('ir_cron_generate_missing_work_entries')._trigger()
```

This cron fills gaps in generated work entries. It is triggered automatically by the scheduler and also when contract changes occur (via `_cron_generate_missing_work_entries`).

---

## `hr.work.entry.type` — Complete Reference

**File:** `models/hr_work_entry_type.py` (~69 lines)

```python
class HrWorkEntryType(models.Model):
    _name = 'hr.work.entry.type'
    _description = 'HR Work Entry Type'
```

Work entry types classify entries for payroll processing. They are typically country-specific and map to payroll wage types.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char (required, translate) | Localized type name |
| `display_code` | Char (size=3, translate) | Short code for UI (max 3 chars) |
| `code` | Char (required) | Payroll integration code. Changing it can break payroll exports. |
| `external_code` | Char | Third-party export mapping |
| `color` | Integer | Kanban card color |
| `sequence` | Integer | Sort order in type dropdown |
| `active` | Boolean | Allows hiding without deleting |
| `country_id` | Many2one(res.country) | Scopes the type to a specific country |
| `country_code` | Char (related) | Convenience reference |
| `is_leave` | Boolean | Links to time off system (time off type) |
| `is_work` | Boolean (computed/inverse) | Inverse of `is_leave`. Work time = not leave time. |
| `amount_rate` | Float (default=1.0) | Pay rate multiplier (2.0 = double pay) |
| `is_extra_hours` | Boolean | Add to monthly pay as bonus hours |

### Key Constraints

```python
@api.constrains('code', 'country_id')
def _check_code_unicity(self):
    # Code must be unique per (code, country_id) pair
    # False/NULL country means "all countries"
```

```python
@api.constrains('country_id')
def _check_work_entry_type_country(self):
    # Cannot change country of the attendance type (ref 'work_entry_type_attendance')
    # Cannot change country if type is already in use
```

### Standard Types (seeded by module data)

| XML ID | Name | Code | Purpose |
|--------|------|------|---------|
| `work_entry_type_attendance` | Attendance | `ATTD` | Standard working time |
| `work_entry_type_leave` | Leave | `LEAVE100` | Default time off |
| `work_entry_type_overtime` | Overtime | `OTE` | Extra hours |

---

## `hr.version` Extensions

**File:** `models/hr_version.py` (~725 lines)

The `hr_work_entry` module extends `hr.version` with work-entry generation capabilities.

### Entry Generation Methods

| Method | Lines | Purpose |
|-------|-------|---------|
| `_get_attendance_intervals()` | ~20 | Fetch working hours from calendar per employee |
| `_get_lunch_intervals()` | ~17 | Fetch lunch breaks (excluded from work time) |
| `_get_resource_calendar_leaves()` | ~1 | Fetch time-off records for the period |
| `_get_version_work_entries_values()` | ~165 | Core generation: attendance + leaves → entry dicts |
| `_get_work_entries_values()` | ~42 | Wrapper that handles timezone grouping |
| `_generate_work_entries()` | ~75 | Delete-out-of-range + create new entries |
| `generate_work_entries()` | ~24 | Public entry point; groups by company/tz |
| `_generate_work_entries_postprocess()` | ~120 | Convert datetimes to date/duration, merge |
| `_remove_work_entries()` | ~19 | Delete entries outside contract period |
| `_cancel_work_entries()` | ~18 | Cancel entries when contract changes |
| `_recompute_work_entries()` | ~8 | Trigger regeneration via wizard |
| `_get_fields_that_recompute_we()` | ~2 | Return list of fields that trigger recompute |
| `_cron_generate_missing_work_entries()` | ~30 | Nightly cron for missing entries |

### Fields Tracked on Version

| Field | Purpose |
|-------|---------|
| `date_generated_from` | Lower bound of generated entry window |
| `date_generated_to` | Upper bound of generated entry window |
| `last_generation_date` | When generation last ran |
| `work_entry_source` | `calendar`/`attendance`/`planning` |

---

## `hr.employee` Extensions

**File:** `models/hr_employee.py` (~60 lines)

```python
class HrEmployee(models.Model):
    _inherit = 'hr.employee'
```

### Fields Added

| Field | Type | Notes |
|-------|------|-------|
| `has_work_entries` | Boolean (computed) | Shows whether employee has any work entries. Restricted to `base.group_system, hr.group_hr_user`. Uses SQL for performance on large datasets. |
| `work_entry_source` | Selection (related, inherited) | From `version_id.work_entry_source`. Manager-only. |
| `work_entry_source_calendar_invalid` | Boolean (related, inherited) | Manager-only. |

### Methods

| Method | Purpose |
|-------|---------|
| `create_version()` | Override that sets `date_generated_from/to` to now when creating a new contract version |
| `action_open_work_entries()` | Opens the work entry calendar for this employee |
| `generate_work_entries()` | Public API to generate entries for a date range |

```python
def action_open_work_entries(self, initial_date=False):
    ctx = {'default_employee_id': self.id, 'initial_date': initial_date}
    return {
        'type': 'ir.actions.act_window',
        'name': _('%s work entries', self.display_name),
        'view_mode': 'calendar,list,form',
        'res_model': 'hr.work.entry',
        'path': 'work-entries',
        'context': ctx,
        'domain': [('employee_id', '=', self.id)],
    }
```

---

## `resource.calendar` Extensions

**File:** `models/resource_calendar.py`

```python
class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'
```

- **`_compute_hours_per_week()`**: Override adds `'attendance_ids.work_entry_type_id.is_leave'` to the `@api.depends`. This ensures hours-per-week recalculates when an attendance's work entry type changes.
- **`_get_global_attendances()`**: Filters out global attendance records that have `work_entry_type_id.is_leave = True`. These are treated as leave, not work, in interval calculations.

---

## `resource.calendar.attendance` Extensions

**File:** `models/resource_calendar_attendance.py`

| Field Added | Type | Notes |
|------------|------|-------|
| `work_entry_type_id` | Many2one(hr.work.entry.type) | Default: `work_entry_type_attendance`. Determines what type of work entry is generated for this specific attendance slot. |

- `_copy_attendance_vals()`: Ensures `work_entry_type_id` is copied when duplicating attendance lines
- `_is_work_period()`: Returns `True` only when the attendance's work entry type is NOT a leave

---

## `resource.calendar.leaves` Extensions

**File:** `models/resource_calendar_leaves.py`

| Field Added | Type | Notes |
|------------|------|-------|
| `work_entry_type_id` | Many2one(hr.work.entry.type) | Determines what type of leave entry is generated for this specific leave interval |

- `_copy_leave_vals()`: Ensures `work_entry_type_id` is copied when duplicating leave records

---

## `hr.user.work.entry.employee`

**File:** `models/hr_user_work_entry_employee.py`

A simple bridge model for the personal work entry calendar filter:

```python
class HrUserWorkEntryEmployee(models.Model):
    _name = 'hr.user.work.entry.employee'
    _description = 'Work Entries Employees'

    user_id = fields.Many2one('res.users', 'Me', default=lambda self: self.env.user)
    employee_id = fields.Many2one('hr.employee', 'Employee', required=True)
    is_checked = fields.Boolean(default=True)

    _user_id_employee_id_unique = models.Constraint(
        'UNIQUE(user_id, employee_id)',
        'You cannot have the same employee twice.')
```

One record per user-employee pair. Controls which employees appear in the user's personal work entry calendar view.

---

## Complete Method Reference

### `hr.work.entry`

| Method | Signature | Purpose |
|-------|-----------|---------|
| `_check_duration()` | `self` | `@constrains('duration')` — 0 < d <= 24 |
| `_compute_name()` | `self` | `"{type}: {employee}"` |
| `_compute_display_name()` | `self` | `"{type} - {H}h{MM}"` |
| `_compute_conflict()` | `self` | `conflict = (state == 'conflict')` |
| `_onchange_version_id()` | `self` | Calls `_set_current_contract()` on employee/date change |
| `_set_current_contract()` | `self, vals` | Sets `version_id` from employee and date |
| `get_unusual_days()` | `self, date_from, date_to` | Get unusual days from company calendar |
| `action_validate()` | `self` | Try to validate; returns `True`/`False` |
| `action_split()` | `self, vals` | Split entry at given duration |
| `_check_if_error()` | `self` | Run all four validation checks |
| `_mark_conflicting_work_entries()` | `self, start, stop` | SQL: days with >24h total |
| `_mark_leaves_outside_schedule()` | `self` | Leave entries outside calendar |
| `_mark_already_validated_days()` | `self` | Already-validated date overlap |
| `_to_intervals()` | `self` | Convert entries to `Intervals` |
| `_from_intervals()` | `self, intervals` | Convert `Intervals` back to entries |
| `create()` | `self, vals_list` | Auto-set contract, company, amount_rate |
| `write()` | `self, vals` | Sync active↔state, run `_error_checking()` |
| `unlink()` | `self` | Raise if validated; run `_error_checking()` |
| `_reset_conflicting_state()` | `self` | Reset conflict → draft |
| `_error_checking()` | `self, start, stop, skip, employee_ids` | Context manager for re-validation |
| `_get_work_entry_type_domain()` | `self` | Country-filtered type domain |
| `_search_country_id()` | `self, operator, value` | Search by employee country |

### `hr.version` (extended)

| Method | Purpose |
|-------|---------|
| `_get_default_work_entry_type_id()` | Cached ref to attendance type |
| `_get_default_work_entry_type_overtime_id()` | Cached ref to overtime type |
| `_get_leave_work_entry_type_dates()` | Map leave to work entry type |
| `_get_interval_leave_work_entry_type()` | Determine leave type per interval |
| `_get_sub_leave_domain()` | Domain for sub-leaves (company calendar-specific) |
| `_get_leave_domain()` | Full leave search domain |
| `_get_attendance_intervals()` | Working hours per employee |
| `_get_lunch_intervals()` | Lunch breaks per employee |
| `_get_interval_work_entry_type()` | Determine type for attendance interval |
| `_get_real_attendance_work_entry_vals()` | Build attendance entry dicts |
| `_get_version_work_entries_values()` | Core generation for a version's date range |
| `_get_work_entries_values()` | Timezone-aware wrapper |
| `has_static_work_entries()` | `work_entry_source == 'calendar'` |
| `generate_work_entries()` | Public API: groups by company/tz |
| `_generate_work_entries()` | Delete-gap + create new entries |
| `_generate_work_entries_postprocess()` | Date/duration conversion, merging, timezone splits |
| `_remove_work_entries()` | Delete entries outside contract period |
| `_cancel_work_entries()` | Cancel entries when contract changes |
| `write()` | Track changes; trigger recompute if calendar/source changes |
| `unlink()` | Cancel work entries before unlinking version |
| `_recompute_work_entries()` | Trigger regeneration via wizard |
| `_get_fields_that_recompute_we()` | Return `['resource_calendar_id', 'work_entry_source']` |
| `_cron_generate_missing_work_entries()` | Nightly cron job |

---

## Related

- [Modules/hr](Modules/HR.md) — HR core
- [Modules/hr_work_entry_holidays](Modules/hr_work_entry_holidays.md) — Leave integration
- [Modules/hr_attendance](Modules/hr_attendance.md) — Attendance-based generation
- [Modules/HR](Modules/HR.md) — Payroll computation from validated entries
- [Modules/HR](Modules/HR.md) — Contract/Version model
- [Core/Fields](Core/Fields.md) — Field type reference
- [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) — State machine design
