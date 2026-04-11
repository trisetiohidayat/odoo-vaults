---
Module: hr_homeworking
Version: Odoo 18
Type: Integration
Tags: #hr, #homeworking, #remote-work, #work-location, #attendance
---

# hr_homeworking — Remote Work Management

## Overview

**Module:** `hr_homeworking`
**Category:** Human Resources / Remote Work
**Version:** 2.0
**Depends:** `hr`
**License:** LGPL-3
**Canonical path:** `~/odoo/odoo18/odoo/addons/hr_homeworking/`

`hr_homeworking` lets companies formally track and manage where employees work each day. It extends `hr.employee` with a weekly recurring schedule (one `hr.work.location` per weekday), adds a new `hr.employee.location` model for exceptional one-day location overrides, and wires this into the employee presence system so the live location icon reflects today's actual or planned work location.

---

## Model Map

| Model | Type | File | Description |
|---|---|---|---|
| `hr.employee.base` | Extended (Abstract) | `hr_employee.py` | Weekly schedule fields, exceptional location, presence icon |
| `hr.work.location` | Extended | `hr_work_location.py` | Unlink protection + cascade delete of exceptions |
| `hr.employee.location` | New | `hr_homeworking.py` | Per-employee, per-date exceptional location records |
| `res.users` | Extended | `res_users.py` | Day-location fields mirrored for self-service |
| `res.partner` | Extended | `res_partner.py` | IM status reflects location type |

---

## `hr.work.location` — Base Model

Defined in `hr` module. Extended by `hr_homeworking`.

| Field | Type | Notes |
|---|---|---|
| `active` | `Boolean` | Default `True` |
| `name` | `Char` (required) | Location display name |
| `company_id` | `Many2one(res.company)` | Required, defaults to current company |
| `location_type` | `Selection([('home', 'Home'), ('office', 'Office'), ('other', 'Other')])` | Required, default `'office'` |
| `address_id` | `Many2one(res.partner)` | The work address associated with this location |
| `location_number` | `Char` | Optional building/room identifier |

### `hr_homeworking` Extension: `_unlink_except_used_by_employee()`

```python
@api.ondelete(at_uninstall=False)
def _unlink_except_used_by_employee(self):
    domains = [(day, 'in', self.ids) for day in DAYS]
    employee_uses_location = self.env['hr.employee'].search_count(domains, limit=1)
    if employee_uses_location:
        raise UserError(_("You cannot delete locations that are being used by your employees"))
    exceptions_using_location = self.env['hr.employee.location'].search([
        ('work_location_id', 'in', self.ids)
    ])
    exceptions_using_location.unlink()
```

**Before deleting a work location:**
1. Check if any employee has this location set as a **weekly schedule default** for any day (one of the 7 `*_location_id` fields). If yes, block deletion.
2. Find all `hr.employee.location` exception records using this location and **cascade-delete them**.

This protects the weekly schedule defaults while cleaning up orphaned exceptions.

---

## `hr.employee.location` — New Model

**Internal name:** `hr.employee.location`
**Description:** "Employee Location"
**File:** `hr_homeworking.py`

This is the **exceptional one-day override** model. Where the weekly schedule sets recurring defaults, this model handles ad-hoc deviations (e.g., "working from a client site on Tuesday").

### Fields

| Field | Type | Notes |
|---|---|---|
| `work_location_id` | `Many2one(hr.work.location)` | Required. The location for this day. |
| `work_location_name` | `Char` (related) | Read-only mirror of `work_location_id.name` |
| `work_location_type` | `Selection` (related) | Read-only mirror of `work_location_id.location_type` |
| `employee_id` | `Many2one(hr.employee)` | Required. Defaults to `self.env.user.employee_id`. Cascade delete. |
| `employee_name` | `Char` (related) | Read-only mirror of `employee_id.name` |
| `date` | `Date` | The specific calendar date this override applies to. |
| `day_week_string` | `Char` (computed) | The weekday name of `date`, computed via `date.strftime("%A")` (e.g., "Monday"). |

### SQL Constraints

```python
_sql_constraints = [
    ('uniq_exceptional_per_day',
     'unique(employee_id, date)',
     'Only one default work location and one exceptional work location per day per employee.')
]
```

Enforces exactly one location record per employee per date. This covers both default schedule records (future enhancement path) and exceptional overrides (current use).

### Compute: `_compute_day_week_string()`

```python
@api.depends('date')
def _compute_day_week_string(self):
    for record in self:
        record.day_week_string = record.date.strftime("%A")
```

Returns the locale-aware weekday name for the exception date.

### DA Constants

```python
DAYS = ['monday_location_id', 'tuesday_location_id', 'wednesday_location_id',
        'thursday_location_id', 'friday_location_id', 'saturday_location_id',
        'sunday_location_id']
```

The 7-element `DAYS` list is used across `hr_homeworking` models to programmatically reference the weekly schedule fields. It is the canonical definition of day field names.

---

## `hr.employee.base` — EXTENDED (Abstract)

Inherited from `hr.employee.base`. These fields live on the `hr.employee` model at runtime.

### Fields

| Field | Type | Notes |
|---|---|---|
| `monday_location_id` | `Many2one(hr.work.location)` | Employee's default location for Mondays. |
| `tuesday_location_id` | `Many2one(hr.work.location)` | Default Tuesday location. |
| `wednesday_location_id` | `Many2one(hr.work.location)` | Default Wednesday location. |
| `thursday_location_id` | `Many2one(hr.work.location)` | Default Thursday location. |
| `friday_location_id` | `Many2one(hr.work.location)` | Default Friday location. |
| `saturday_location_id` | `Many2one(hr.work.location)` | Default Saturday location. |
| `sunday_location_id` | `Many2one(hr.work.location)` | Default Sunday location. |
| `exceptional_location_id` | `Many2one(hr.work.location)` | Today's exceptional override, if any. Computed. |
| `hr_icon_display` | `Selection` (extended) | New values: `'presence_home'`, `'presence_office'`, `'presence_other'` |
| `today_location_name` | `Char` | Used in search view as a placeholder for today's location field. |

### Key Methods

#### `_get_current_day_location_field()` — static

```python
@api.model
def _get_current_day_location_field(self):
    return DAYS[fields.Date.today().weekday()]
```

Returns the field name for today (e.g., `'wednesday_location_id'`). This is called dynamically so all the weekly fields can be treated as a unified schedule.

#### `_compute_exceptional_location_id()`

```python
def _compute_exceptional_location_id(self):
    today = fields.Date.today()
    current_employee_locations = self.env['hr.employee.location'].search([
        ('employee_id', 'in', self.ids),
        ('date', '=', today),
    ])
    employee_work_locations = {l.employee_id.id: l.work_location_id for l in current_employee_locations}
    for employee in self:
        employee.exceptional_location_id = employee_work_locations.get(employee.id, False)
```

Looks up today's `hr.employee.location` record for each employee. Returns `False` if no exception exists.

#### `_compute_work_location_name_type()` — extended

```python
@api.depends("work_location_id.name", "work_location_id.location_type",
             "exceptional_location_id", *DAYS)
def _compute_work_location_name_type(self):
    super()._compute_work_location_name_type()
    dayfield = self._get_current_day_location_field()
    for employee in self:
        current_location_id = employee.exceptional_location_id or employee[dayfield]
        employee.work_location_name = current_location_id.name or employee.work_location_name
        employee.work_location_type = current_location_id.location_type or employee.work_location_type
```

Extends the parent computation. Takes `exceptional_location_id` first; falls back to today's scheduled location (`employee[dayfield]`). Populates `work_location_name` and `work_location_type` — these are the fields shown in list/kanban views.

#### `_compute_presence_icon()` — extended

```python
@api.depends(*DAYS, 'exceptional_location_id')
def _compute_presence_icon(self):
    super()._compute_presence_icon()
    dayfield = self._get_current_day_location_field()
    for employee in self:
        today_employee_location_id = employee.exceptional_location_id or employee[dayfield]
        if not today_employee_location_id or employee.hr_icon_display.startswith('presence_holiday'):
            continue
        employee.hr_icon_display = f'presence_{today_employee_location_id.location_type}'
        employee.show_hr_icon_display = True
```

Overwrites `hr_icon_display` with today's location type. Priority:
1. If employee is on holiday → keep `presence_holiday_*` (do not override).
2. If exceptional location is set → use that.
3. Otherwise → use the weekly schedule field for today.

This drives the **live presence indicator** (green home icon / blue office icon / orange other icon) in the Employee app and in the Discuss/Chatter sidebar.

#### `get_views()` — dynamic field substitution

```python
@api.model
def get_views(self, views, options=None):
    res = super().get_views(views, options)
    dayfield = self._get_current_day_location_field()
    if 'search' in res['views']:
        res['views']['search']['arch'] = res['views']['search']['arch'].replace(
            'today_location_name', dayfield
        )
    if 'list' in res['views']:
        res['views']['list']['arch'] = res['views']['list']['arch'].replace(
            'work_location_name', dayfield
        )
    return res
```

This is a clever **view-time patching mechanism**: the XML arch strings contain the literal placeholder `'today_location_name'` which is replaced at fetch time with the actual today's field name (e.g., `'wednesday_location_id'`). This allows a single search view to dynamically group/filter by today's location without needing a computed group field.

---

## `res.users` — EXTENDED

### Fields

Each day-location field is mirrored from `employee_id`:

```python
monday_location_id    = fields.Many2one(related="employee_id.monday_location_id",    readonly=False)
tuesday_location_id   = fields.Many2one(related="employee_id.tuesday_location_id",   readonly=False)
wednesday_location_id = fields.Many2one(related="employee_id.wednesday_location_id", readonly=False)
thursday_location_id  = fields.Many2one(related="employee_id.thursday_location_id",  readonly=False)
friday_location_id    = fields.Many2one(related="employee_id.friday_location_id",    readonly=False)
saturday_location_id  = fields.Many2one(related="employee_id.saturday_location_id",  readonly=False)
sunday_location_id    = fields.Many2one(related="employee_id.sunday_location_id",    readonly=False)
```

`readonly=False` allows employees to update their own weekly schedule directly from the user preferences form.

### `_get_employee_fields_to_sync()`

```python
def _get_employee_fields_to_sync(self):
    return super()._get_employee_fields_to_sync() + DAYS
```

Adds all 7 day-location fields to the set of fields synced from `res.users` to `hr.employee` when the employee record is updated.

### `_compute_im_status()` — extended

```python
def _compute_im_status(self):
    super()._compute_im_status()
    dayfield = self.env['hr.employee']._get_current_day_location_field()
    for user in self:
        location_type = user[dayfield].location_type
        if not location_type:
            continue
        im_status = user.im_status
        if im_status in ("online", "away", "offline"):
            user.im_status = f"presence_{location_type}_" + im_status
```

Transforms the user's IM status into a location-aware variant:
- `online` → `presence_home_online`, `presence_office_online`, `presence_other_online`
- `away` → `presence_home_away`, `presence_office_away`, etc.
- `offline` → `presence_home_offline`, etc.

This enables the Discuss app to show enriched presence indicators based on today's planned work location.

### `_is_user_available()`

```python
def _is_user_available(self):
    location_types = self.env['hr.work.location']._fields['location_type'].get_values(self.env)
    return self.im_status in ['online'] + [
        f'presence_{location_type}_online' for location_type in location_types
    ]
```

Returns `True` if the user is either directly `online` OR `presence_*_online` (any location). Used by the company-wide availability checker in Discuss.

### Field Access

- `SELF_READABLE_FIELDS`: includes all 7 day fields.
- `SELF_WRITEABLE_FIELDS`: includes all 7 day fields.

---

## `res.partner` — EXTENDED

```python
def _compute_im_status(self):
    super()._compute_im_status()
    for user in self.user_ids:
        dayfield = self.env['hr.employee']._get_current_day_location_field()
        location_type = user[dayfield].location_type
        if not location_type:
            continue
        im_status = user.partner_id.im_status
        if im_status in ("online", "away", "offline"):
            user.partner_id.im_status = location_type + "_" + im_status
```

Mirrors the user location-based IM status onto the partner record. A partner with multiple users uses the first one's location type.

---

## Security

| Record | Rule | Scope |
|---|---|---|
| `hr.employee.location` | `homeworking_own_rule` (ir.rule) | Employee can only see/modify their own records. Group: `base.group_user`. |
| `hr.employee.location` | `homeworking_admin_rule` (ir.rule) | HR User can see/modify all records. Group: `hr.group_hr_user`. |

Access rights (ir.model.access.csv):
| ID | Model | Group | CRUD |
|---|---|---|---|
| `access_hr_employee_location` | `model_hr_employee_location` | `hr.group_hr_user` | Full |
| `access_user_employee_location` | `model_hr_employee_location` | `base.group_user` | Full |

Both regular users and HR users get full CRUD on their own records.

---

## L4: How This Integrates with Attendance and Payroll

### Integration with Attendance

The `exceptional_location_id` and the weekly schedule fields feed directly into `hr_icon_display` (the employee presence indicator). The key integration point is `_compute_presence_icon()`:

1. An employee badges in at the office → attendance record created with `work_location_id` matching the office.
2. The presence icon in the Employee app and Discuss sidebar shows `presence_office` for today (or the exceptional override).
3. If the employee has an exceptional location set for today (via `hr.employee.location`), the icon shows `presence_home` or `presence_other` instead.

There is **no automatic attendance record creation** from homeworking data. The module is purely declarative: it records where the employee *plans* to work. Actual badge-in records come from `hr_attendance`. However, the planned location serves as a reference for:
- **Kiosk/badging**: The attendance system can display the employee's planned location to a reception guard.
- **Geo-attendance**: When combined with geo-fencing apps, planned homeworking days can auto-validate remote check-ins.
- **Reporting**: Managers can cross-reference planned vs. actual attendance locations.

### How `exceptional_location_id` Takes Priority

The precedence chain for today's effective location is:

```
exceptional_location_id (hr.employee.location for today)
        OR
[weekday]_location_id (employee's weekly schedule for today)
        OR
work_location_id (the legacy single-field work location on hr.employee)
```

The weekly schedule is a **recurring default** that repeats every week. The exceptional record is a **one-day override** that supersedes the default for a specific date. Both together allow employees to set a regular hybrid schedule (e.g., Mon/Wed/Fri office, Tue/Thu home) with the ability to deviate on any given day.

### Payroll Implications

`hr_homeworking` is a **purely declarative/dimensional** module — it does not directly affect payroll calculations. However, it provides the data needed for:

| Use Case | How It Feeds Payroll |
|---|---|
| **Home office allowances** | Payroll can query `sunday–saturday_location_id` / `location_type` to count homeworking days per period and apply allowances. |
| **Travel reimbursement** | The number of office days (vs. home days) per month can be derived from the schedule for expense processing. |
| **Timesheet project allocation** | If timesheet projects are linked to work locations, the weekly schedule can pre-populate project allocation defaults. |
| **Attendance-based accrual** | `hr_holidays_attendance` accrual plans with `frequency_hourly_source='attendance'` benefit from knowing planned vs. actual days. |
| **Flexible working policy enforcement** | HR/management dashboards can verify compliance with agreed hybrid schedules. |

### View Integration

The module modifies three standard employee views:
- **Form view** (`view_employee_form`): Adds a "Remote Work" group with all 7 day fields. Replaces the single `work_location_id` field (made invisible).
- **Tree view** (`view_employee_tree`): Adds `work_location_name` as an optional column showing today's effective location.
- **Search view** (`view_employee_filter`): Adds a "Work location" filter/groupby that dynamically resolves to today's weekday field via `get_views()` patching.

This means the **Employee app list view** becomes a live heatmap of today's locations across the company.

### `get_views()` Dynamic Field Substitution — Deep Dive

The search view XML contains:
```xml
<filter name="_search_today_location" string="Work location"
        domain="[]" context="{'group_by':'today_location_name'}"/>
```

At view fetch time, `get_views()` replaces `'today_location_name'` with the actual field name (`'wednesday_location_id'`, etc.), making the groupby dynamically reflect today's column. This is a runtime view transformation — the XML on disk always contains the placeholder, but the ORM serves the substituted arch to the client.
