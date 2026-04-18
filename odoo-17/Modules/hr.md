---
tags: [odoo, odoo17, module, hr, research_depth]
research_depth: deep
---

# HR Module — Deep Research (Odoo 17)

**Source:** `addons/hr/models/`

Files: `hr_employee.py` (617 lines), `hr_employee_base.py` (303 lines), `hr_employee_public.py` (94 lines), `hr_department.py` (181 lines), `hr_job.py` (64 lines)

## Module Architecture

```
hr.employee.base (abstract mixin, shared fields)
    └── hr.employee (HrEmployeePrivate) — main employee model
         ├── hr.employee.public (SQL view, read-only facade)
         └── _inherits: resource.mixin, mail.thread.main.attachment, mail.activity.mixin, avatar.mixin

hr.department
    └── parent_id (self-referential hierarchy, _parent_store=True)
    └── manager_id (→ hr.employee)

hr.job
    └── department_id (→ hr.department)
    └── contract_type_id (→ hr.contract.type)
```

The module also contains: `hr_employee_category.py`, `hr_departure_reason.py`, `hr_contract_type.py`, `hr_work_location.py`, `hr_contract.py` (if installed), `resource.py`, and mail-related models.

---

## hr.employee.base — Shared Fields Mixin

File: `addons/hr/models/hr_employee_base.py` (303 lines)

Abstract model (`_name = 'hr.employee.base'`). Defines fields and logic shared between `hr.employee` and `hr.employee.public`.

### All Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Employee name |
| `active` | Boolean | Active status |
| `color` | Integer | Color index for kanban |
| `department_id` | Many2one hr.department | Employee's department |
| `member_of_department` | Boolean (computed+search) | Is member of active user's department or its children |
| `job_id` | Many2one hr.job | Job position |
| `job_title` | Char | Personal job title (computed from `job_id.name`, store=True) |
| `company_id` | Many2one res.company | Company |
| `address_id` | Many2one res.partner | Work address (computed from `company_id.partner_id`, store=True) |
| `work_phone` | Char | Computed from `address_id.phone`, stored |
| `mobile_phone` | Char | From `work_contact_id.mobile`, stored, inverse enabled |
| `work_email` | Char | From `work_contact_id.email`, stored, inverse enabled |
| `work_contact_id` | Many2one res.partner | Work contact partner (created on employee creation) |
| `work_location_id` | Many2one hr.work.location | Work location |
| `user_id` | Many2one res.users | Linked user account |
| `resource_id` | Many2one resource.resource | Linked resource record |
| `resource_calendar_id` | Many2one resource.calendar | Working schedule |
| `parent_id` | Many2one hr.employee | Manager. Computed from `department_id.manager_id` unless manually set |
| `coach_id` | Many2one hr.employee | Coach. Auto-set to `parent_id` if not set and manager changes |
| `tz` | Selection | Timezone (related to `resource_id.tz`) |
| `hr_presence_state` | Selection | `present`, `absent`, `to_define`. Computed from user.im_status |
| `last_activity` | Date (computed) | Last activity date from bus.presence |
| `last_activity_time` | Char (computed) | Formatted time if today |
| `hr_icon_display` | Selection | Presence icon display: `presence_present`, `presence_absent`, etc. |
| `show_hr_icon_display` | Boolean (computed) | Whether to show the icon |
| `newly_hired` | Boolean (computed+search) | Created within last 90 days |

### Presence Computation: `_compute_presence_state()` (Line 137-154)

```python
check_login = literal_eval(self.env['ir.config_parameter'].sudo().get_param(
    'hr.hr_presence_control_login', 'False'))

employee_to_check_working = self.filtered(lambda e: e.user_id.im_status == 'offline')
working_now_list = employee_to_check_working._get_employee_working_now()

for employee in self:
    state = 'to_define'
    if check_login:
        if employee.user_id.im_status in ['online', 'leave_online']:
            state = 'present'
        elif employee.user_id.im_status in ['offline', 'leave_offline'] and \
             employee.id not in working_now_list:
            state = 'absent'
    employee.hr_presence_state = state
```

Config param `hr.hr_presence_control_login` enables/disables login-based presence checking. Even when `check_login=False`, employees with a working schedule are shown as `present` if they're in working hours via `_get_employee_working_now()`.

### `_get_employee_working_now()` (Line 271-292)

Batch process: groups employees by timezone, then by calendar. For each group, asks `resource_calendar_id._work_intervals_batch()` whether the employee is in a working interval at the current time. Returns list of employee IDs currently working.

### `_compute_coach()` (Line 176-184)

```python
def _compute_coach(self):
    for employee in self:
        manager = employee.parent_id
        previous_manager = employee._origin.parent_id
        if manager and (employee.coach_id == previous_manager or not employee.coach_id):
            employee.coach_id = manager  # Auto-promote manager to coach
        elif not employee.coach_id:
            employee.coach_id = False
```

Auto-promotes manager to coach: if the manager changes and the coach was the old manager (or coach is empty), set coach to new manager. Prevents orphaned coach assignments.

### `_compute_parent_id()` (Line 238-241)

```python
def _compute_parent_id(self):
    for employee in self.filtered('department_id.manager_id'):
        employee.parent_id = employee.department_id.manager_id
```

Defaults parent_id to the department manager. Only applies if `department_id` has a `manager_id` and employee has no explicit parent set. **Bidirectional with department manager**: changing department manager auto-updates employee parent_id.

### Work Contact Creation and Sync (Line 206-230)

`_create_work_contacts()`: bulk-creates `res.partner` records for employees without a work contact. Sets email from `work_email`, mobile from `mobile_phone`, name from employee name, image from employee image, company from company.

`_inverse_work_contact_details()`: when `mobile_phone` or `work_email` changes, syncs back to `work_contact_id`. If no work contact exists, adds to a list to be bulk-created.

### Newly Hired: `_compute_newly_hired()` (Line 73-91)

```python
new_hire_date = fields.Datetime.now() - timedelta(days=90)
for employee in self:
    if not employee[new_hire_field]:
        employee.newly_hired = False
    elif not isinstance(employee[new_hire_field], datetime):
        employee.newly_hired = employee[new_hire_field] > new_hire_date.date()
    else:
        employee.newly_hired = employee[new_hire_field] > new_hire_date
```

Default field: `create_date`. 90-day window. Supports override via `_get_new_hire_field()` for modules that want a different trigger (e.g., onboarding completion date).

---

## hr.employee — The Private Employee Model

File: `addons/hr/models/hr_employee.py` (617 lines)

`HrEmployeePrivate`. Inherits: `hr.employee.base`, `mail.thread.main.attachment`, `mail.activity.mixin`, `resource.mixin`, `avatar.mixin`.

### All Fields (complete, lines 39-143)

#### Resource/User fields
| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Related to `resource_id.name`, store=True, tracking=True |
| `user_id` | Many2one res.users | Related to `resource_id.user_id`, store=True, ondelete='restrict' |
| `user_partner_id` | Many2one res.partner | Related to `user_id.partner_id`, related_sudo=False |
| `active` | Boolean | Related to `resource_id.active`, default=True, store=True |
| `resource_calendar_id` | Many2one | Tracking enabled |
| `department_id` | Many2one | Tracking enabled |
| `company_id` | Many2one res.company | Required |
| `company_country_id` | Many2one res.country | Related to `company_id.country_id` |
| `company_country_code` | Char | Related to `company_country_id.code` |

#### Private info (groups="hr.group_hr_user")
| Field | Type | Description |
|-------|------|-------------|
| `private_street/city/state_id/zip/country_id` | Various | Home address |
| `private_phone` | Char | Home phone |
| `private_email` | Char | Private email |
| `lang` | Selection | Language |
| `country_id` | Many2one res.country | Nationality |
| `gender` | Selection | Male/female/other |
| `marital` | Selection | Single/married/cohabitant/widower/divorced |
| `spouse_complete_name` | Char | Spouse name |
| `spouse_birthdate` | Date | Spouse birthday |
| `children` | Integer | Number of dependent children |
| `place_of_birth` | Char | Birth place |
| `country_of_birth` | Many2one res.country | Birth country |
| `birthday` | Date | Date of birth |
| `ssnid` | Char | Social Security Number |
| `sinid` | Char | Social Insurance Number |
| `identification_id` | Char | ID number |
| `passport_id` | Char | Passport number |
| `bank_account_id` | Many2one res.partner.bank | Salary payment bank account |
| `permit_no` | Char | Work permit number |
| `visa_no` | Char | Visa number |
| `visa_expire` | Date | Visa expiration |
| `work_permit_expiration_date` | Date | Work permit expiry |
| `has_work_permit` | Binary | Work permit document |
| `work_permit_scheduled_activity` | Boolean | Cron scheduling flag (default=False) |
| `additional_note` | Text | Additional notes |
| `certificate` | Selection | Education level |
| `study_field` | Char | Field of study |
| `study_school` | Char | School |
| `emergency_contact` | Char | Emergency contact name |
| `emergency_phone` | Char | Emergency contact phone |
| `km_home_work` | Integer | Home-work distance in km |

#### Employment/Company fields
| Field | Type | Description |
|-------|------|-------------|
| `job_id` | Many2one | Tracking enabled |
| `child_ids` | One2many hr.employee | Direct subordinates |
| `category_ids` | Many2many hr.employee.category | Tags/labels |
| `notes` | Text | Internal notes |
| `color` | Integer | Color index for kanban (default=0) |
| `barcode` | Char | Badge ID (unique). Used for attendance kiosk. groups="hr.group_hr_user" |
| `pin` | Char | PIN for attendance kiosk and POS cashier. groups="hr.group_hr_user" |
| `departure_reason_id` | Many2one hr.departure.reason | Reason for leaving |
| `departure_description` | Html | Additional departure info |
| `departure_date` | Date | Departure/archive date |
| `employee_type` | Selection | `employee`/`student`/`trainee`/`contractor`/`freelance`. Required. Impact: only "employee" type is supposed to be under contract |
| `message_main_attachment_id` | Many2one | Main attachment |
| `id_card` | Binary | ID card copy |
| `driving_license` | Binary | Driver's license |
| `private_car_plate` | Char | Car plate |
| `currency_id` | Many2one res.currency | Related to `company_id.currency_id` |
| `employee_properties` | Properties | Custom properties from company definition |

#### SQL Constraints
```python
('barcode_uniq', 'unique (barcode)', "The Badge ID must be unique...")
('user_uniq', 'unique (user_id, company_id)', "A user cannot be linked to multiple employees in the same company.")
```

### Access Control: `hr.employee.public` Proxy

Non-HR users cannot directly access `hr.employee` private fields. The model overrides several methods to route through `hr.employee.public`:

#### `_search()` (Line 301-317)
```python
def _search(self, domain, offset=0, limit=None, order=None, access_rights_uid=None):
    if self.check_access_rights('read', raise_exception=False):
        return super()._search(domain, offset, limit, order, access_rights_uid)
    try:
        ids = self.env['hr.employee.public']._search(domain, offset, limit, order, access_rights_uid)
    except ValueError:
        raise AccessError(_('You do not have access to this document.'))
    return super(HrEmployeePrivate, self.sudo())._search([('id', 'in', ids)], order=order)
```

Non-HR users: search returns IDs from `hr.employee.public`, then browses on `hr.employee` (with sudo) so field values come through correctly despite the access restrictions.

#### `get_view()` and `get_views()` (Line 286-298)
Non-HR users: `get_view` → `hr.employee.public.get_view`, `get_views` → `hr.employee.public.get_views` with model mapping.

#### `search_fetch()` and `fetch()` (Line 216-246)
Non-HR users: read from `hr.employee.public` and copy cache values. Private fields raise `AccessError` via `_check_private_fields()`.

#### `get_formview_id()` (Line 319-329)
HR users → normal form. Non-HR users → hardcoded `hr.hr_employee_public_view_form`.

### Avatar Computation (Line 150-180)

Five avatar resolutions (1920/1024/512/256/128). Logic:
1. If employee has no user and no stored image: compute SVG from initials
2. If employee has user: use user's avatar
3. If employee has stored image: use stored image
4. Priority: user avatar > stored image > SVG

```python
def _compute_avatar(self, avatar_field, image_field):
    for employee in self:
        if not employee.user_id and not employee._origin[image_field]:
            employee_wo_user_and_image += employee
            continue
        avatar = employee._origin[image_field]
        if not avatar and employee.user_id:
            avatar = employee.user_id.sudo()[avatar_field]
        employee[avatar_field] = avatar
    super(HrEmployeePrivate, employee_wo_user_and_image)._compute_avatar(...)
```

### User Sync: `_sync_user()` (Line 378-387)

```python
def _sync_user(self, user, employee_has_image=False):
    vals = dict(
        work_contact_id=user.partner_id.id if user else self.work_contact_id.id,
        user_id=user.id,
    )
    if not employee_has_image:
        vals['image_1920'] = user.image_1920
    if user.tz:
        vals['tz'] = user.tz
    return vals
```

Called on create and write when `user_id` changes. Propagates partner (for work contact), avatar (if not already set), and timezone. Also calls `_remove_work_contact_id()` to detach previous work contacts.

### Work Contact Management

`_remove_work_contact_id()` (Line 367-376): When assigning a user to an employee, remove that user's partner from other employees without a user_id in the same company. Prevents orphaned work contacts.

On employee create (Line 402-439): If no work contact exists, `sudo()._create_work_contacts()`. If no image, generate SVG avatar and assign to employee AND work contact.

### Employee Creation Side Effects (Line 402-439)

```python
employees = super().create(vals_list)
# Sudo: create work contacts (HR officer may not have Contact Creation group)
employees.filtered(lambda e: not e.work_contact_id).sudo()._create_work_contacts()
# Generate SVG avatars if no image_1920
employee_sudo.image_1920 = employee_sudo._avatar_generate_svg()
employee_sudo.work_contact_id.image_1920 = employee_sudo.image_1920

# Subscribe to department channels
self.env['discuss.channel'].sudo().search([
    ('subscription_department_ids', 'in', employee_departments.ids)
])._subscribe_users_automatically()

# Post onboarding recommendation message
onboarding_notes_bodies = {...}
employees._message_log_batch(onboarding_notes_bodies)
```

### Work Permit Validity Cron: `_cron_check_work_permit_validity()` (Line 266-284)

Runs daily. Finds work permits expiring within 1 month. Schedules `mail.activity` on the employee's manager (`parent_id.user_id`) with localized date formatting. Sets `work_permit_scheduled_activity=True` to prevent duplicate scheduling.

### Toggle Active / Archive (Line 487-522)

On archive (`active=False`):
1. Clears `departure_reason_id`, `departure_description`, `departure_date`
2. Opens departure wizard (if `len(self)==1` and `no_wizard` context not set)
3. Empties `parent_id` and `coach_id` via `_get_employee_m2o_to_empty_on_archived_employees()`

On unarchive (`active=True`): clears departure fields only.

### `_get_tz()` and `_get_tz_batch()` (Line 536-549)

Priority for timezone: `employee.tz` → `resource_calendar_id.tz` → `company_id.resource_calendar_id.tz` → `'UTC'`.

### `_get_expected_attendances()` (Line 559-570)

Uses `resource_calendar_id._work_intervals_batch()` to compute working intervals for a date range. Returns intervals filtered by company.

---

## hr.employee.public — Read-Only Facade

File: `addons/hr/models/hr_employee_public.py` (94 lines)

### Model Configuration

```python
class HrEmployeePublic(models.Model):
    _name = "hr.employee.public"
    _inherit = ["hr.employee.base"]  # Reuses all base fields
    _description = 'Public Employee'
    _order = 'name'
    _auto = False  # SQL view, not a table
    _log_access = True  # Includes magic fields __create_uid, etc.

    employee_id = fields.Many2one('hr.employee', compute="_compute_employee_id", search="_search_employee_id")
```

### SQL View Definition (Line 87-93)

```python
def init(self):
    tools.drop_view_if_exists(self.env.cr, self._table)
    self.env.cr.execute("""CREATE or REPLACE VIEW %s as (
        SELECT %s FROM hr_employee emp
    )""" % (self._table, self._get_fields()))
```

`_get_fields()` (Line 84-85): Returns comma-separated list of `emp.<field_name>` for all stored fields that are not many2many/one2many. Creates a live SQL view — any changes to `hr_employee` are immediately reflected.

### Manager Detection: `_compute_is_manager()` (Line 54-59)

```python
def _compute_is_manager(self):
    all_reports = self.env['hr.employee.public'].search([
        ('id', 'child_of', self.env.user.employee_id.id)
    ]).ids
    for employee in self:
        employee.is_manager = employee.id in all_reports
```

Uses `child_of` domain on employee hierarchy. `child_of` uses `parent_path` (stored as `/1/3/7/`) for efficient tree queries without recursion.

### `employee_id` Bridge (Line 79-81)

```python
def _compute_employee_id(self):
    for employee in self:
        employee.employee_id = self.env['hr.employee'].browse(employee.id)
```

Since `hr.employee.public` shares the same IDs as `hr.employee`, `browse(employee.id)` returns the actual private employee record. This allows manager-only fields to be fetched from the real employee for managers.

---

## hr.department — Organization Structure

File: `addons/hr/models/hr_department.py` (181 lines)

### All Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Department name, required, translateable |
| `complete_name` | Char | Computed recursive full path (e.g., "Acme / Engineering / Backend"). Stored. |
| `active` | Boolean | Active status, default=True |
| `company_id` | Many2one res.company | Company, index, default=env.company |
| `parent_id` | Many2one hr.department | Parent department, index, check_company |
| `child_ids` | One2many hr.department | Child departments |
| `manager_id` | Many2one hr.employee | Department manager, tracking enabled |
| `member_ids` | One2many hr.employee | Employees in this department (readonly) |
| `total_employee` | Integer (computed) | Count of employees in department + children |
| `jobs_ids` | One2many hr.job | Jobs in this department |
| `plan_ids` | One2many mail.activity.plan | Activity plans for this department |
| `plans_count` | Integer (computed) | Count of plans (including generic plans with no department) |
| `note` | Text | Internal notes |
| `color` | Integer | Color index for kanban |
| `parent_path` | Char | Stored tree path (e.g., `/1/3/7/`). Used for `child_of` domain. Indexed, unaccent=False |
| `master_department_id` | Many2one hr.department (computed+stored) | Top-most ancestor, derived from `parent_path.split('/')[0]` |

### `_parent_store = True`

Enables efficient tree queries via stored `parent_path`. `child_of` domain operator uses this column instead of recursive SQL. Essential for performance in large org structures.

### Complete Name Computation: `_compute_complete_name()` (Line 48-54)

```python
def _compute_complete_name(self):
    for department in self:
        if department.parent_id:
            department.complete_name = '%s / %s' % (
                department.parent_id.complete_name, department.name)
        else:
            department.complete_name = department.name
```

Uses recursive formula: `parent.complete_name + " / " + name`. Stored for performance. The `hierarchical_naming` context key (default True) controls whether to show complete name or just the name.

### Manager Change Side Effects: `_update_employee_manager()` (Line 116-124)

```python
def _update_employee_manager(self, manager_id):
    employees = self.env['hr.employee']
    for department in self:
        employees = employees | self.env['hr.employee'].search([
            ('id', '!=', manager_id),
            ('department_id', '=', department.id),
            ('parent_id', '=', department.manager_id.id)  # Old manager
        ])
    employees.write({'parent_id': manager_id})
```

When a department's manager changes, all employees who reported to the old manager (via `parent_id`) now report to the new manager. Skip the new manager themselves (`id != manager_id`). This cascade is triggered from `write()` when `manager_id` is in vals.

### Manager Auto-Subscribe (Line 91-95)

On department create, if `manager_id` has a `user_id`, subscribe that user to the department's message thread.

### Department Hierarchy: `get_department_hierarchy()` (Line 156-180)

```python
def get_department_hierarchy(self):
    hierarchy = {
        'parent': {...} if self.parent_id else False,
        'self': {...},
        'children': [...]
    }
    return hierarchy
```

Returns dict with parent/self/children info including employee counts. Useful for org chart displays.

---

## hr.job — Job Positions

File: `addons/hr/models/hr_job.py` (64 lines)

### All Fields

| Field | Type | Description |
|-------|------|-------------|
| `active` | Boolean | Default True |
| `name` | Char | Job position name, required, index='trigram', translateable |
| `sequence` | Integer | Sort order, default=10 |
| `expected_employees` | Integer (computed+stored) | `no_of_employee + no_of_recruitment`. Forecasted headcount |
| `no_of_employee` | Integer (computed+stored) | Current employees in this position |
| `no_of_recruitment` | Integer | Target headcount to recruit, default=1, copy=False |
| `no_of_hired_employee` | Integer | Hired during recruitment phase, copy=False |
| `employee_ids` | One2many hr.employee | Employees in this position (groups: base.group_user) |
| `description` | Html | Job description. Uses `handle_history_divergence` for history tracking. Default template provided. |
| `requirements` | Text | Job requirements |
| `department_id` | Many2one hr.department | Department |
| `company_id` | Many2one res.company | Company, default=env.company |
| `contract_type_id` | Many2one hr.contract.type | Employment type |

### SQL Constraints

```python
('name_company_uniq', 'unique(name, company_id, department_id)',
    'The name of the job position must be unique per department in company!')
('no_of_recruitment_positive', 'CHECK(no_of_recruitment >= 0)', ...)
```

Job name must be unique per `(company_id, department_id)` combination — not just per company.

### Employee Count Computation: `_compute_employees()` (Line 39-45)

```python
employee_data = self.env['hr.employee']._read_group(
    [('job_id', 'in', self.ids)], ['job_id'], ['__count'])
result = {job.id: count for job, count in employee_data}
for job in self:
    job.no_of_employee = result.get(job.id, 0)
    job.expected_employees = result.get(job.id, 0) + job.no_of_recruitment
```

Count is only of **active** employees (default domain of `_read_group`). `expected_employees` combines current + planned headcount.

---

## Key Discoveries

1. **`hr.employee.public` is a live SQL view, not a separate table**: `init()` recreates the view on every module load, and `employee_id = browse(employee.id)` on the same ID returns the real private record. The view exists solely to bypass field-level ACLs for non-HR users.

2. **`member_of_department` uses double negation search**: Searching for employees not in active user's department uses `[('department_id', 'child_of', user_dept.id)]` with `!` prefix. Supports `=`/`!=` with boolean values.

3. **Manager ↔ Department manager bidirectional link**: `hr.department.manager_id` and `hr.employee.parent_id` are synchronized via `_compute_parent_id` on employee and `_update_employee_manager` on department. Changing either cascades to the other.

4. **Coach auto-promotion**: When `parent_id` (manager) changes, `coach_id` is auto-promoted to the new manager unless it was explicitly set to something else. Prevents employees from having coaches from old management.

5. **`newly_hired` search is sudo'd**: `_search_newly_hired` calls `self.env['hr.employee'].sudo()` to find new hires without access restrictions.

6. **`toggle_active()` with no_wizard context**: When archiving an employee via `write({'active': False})`, the departure wizard is shown unless `context={'no_wizard': True}` is passed. This allows programmatic archival without UI.

7. **Employee unlink cascades to resource**: `hr.employee.unlink()` calls `super().unlink()` then `resources.unlink()`. The resource record is deleted with the employee.

8. **`_get_employee_m2o_to_empty_on_archived_employees()` returns `['parent_id', 'coach_id']`**: These fields are cleared when archiving. The return value is consumed by `toggle_active()` to find employees pointing to the archived employee and clear those references.

9. **`work_permit_scheduled_activity` is a cron dedup flag**: Without it, the daily cron would schedule duplicate activities for the same employee every day until the permit is renewed. Set to False when permit is renewed.

10. **`handle_history_divergence` on job description**: Uses the web_editor tool to manage history/versions of the HTML description field. Allows rollback to previous versions.

## See Also

- [Modules/hr_expense](Modules/hr_expense.md) — Expense reports by employees
- [Modules/hr_attendance](Modules/hr_attendance.md) — Attendance check-in/out
- [Modules/hr_holidays](Modules/hr_holidays.md) — Leave management
- [Modules/hr_contract](Modules/hr_contract.md) — Employment contracts
- [Modules/base](Modules/base.md) — `res.users`, `res.partner`, `res.groups`
- [Core/Fields](Core/Fields.md) — Field type reference