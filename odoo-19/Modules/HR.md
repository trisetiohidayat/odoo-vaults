---
type: module
module: hr
tags: [odoo, odoo19, hr, employee, human-resources]
updated: 2026-04-11
version: "1.2"
---

## Quick Access

### Reference
-> Model & Field tables below

### Flows (Technical — AI & Developer)
-> [Flows/HR/employee-creation-flow](odoo-19/Flows/HR/employee-creation-flow.md) — hr.employee create + hr.version
-> [Flows/HR/employee-archival-flow](odoo-19/Flows/HR/employee-archival-flow.md) — Archive/unarchive + subordinates
-> [Flows/HR/employee-transfer-flow](odoo-19/Flows/HR/employee-transfer-flow.md) — Department change + approval
-> [Flows/HR/leave-request-flow](odoo-19/Flows/HR/leave-request-flow.md) — Leave request lifecycle (hr_holidays)
-> [Flows/HR/attendance-checkin-flow](odoo-19/Flows/HR/attendance-checkin-flow.md) — Check-in/check-out + overtime
-> [Flows/HR/contract-lifecycle-flow](odoo-19/Flows/HR/contract-lifecycle-flow.md) — Contract create/renew/terminate
-> [Flows/HR/expense-request-flow](odoo-19/Flows/HR/expense-request-flow.md) — Expense submit + approval + journal
-> [Flows/HR/recruitment-applicant-flow](odoo-19/Flows/HR/recruitment-applicant-flow.md) — Applicant → hire → employee
-> [Flows/HR/timesheet-submission-flow](odoo-19/Flows/HR/timesheet-submission-flow.md) — Timesheet + billing type branching
-> [Flows/HR/department-creation-flow](odoo-19/Flows/HR/department-creation-flow.md) — Department + hierarchy + manager
-> [Flows/HR/job-position-flow](odoo-19/Flows/HR/job-position-flow.md) — Job vacancy + applicant pipeline

### How-To Guides (Functional — Business)
-> [Business/HR/quickstart-employee-setup](odoo-19/Business/HR/quickstart-employee-setup.md) — Step-by-step employee creation
-> [Business/HR/leave-management-guide](odoo-19/Business/HR/leave-management-guide.md) — Leave management process

### Related Modules
-> [Modules/resource](odoo-18/Modules/resource.md) — resource.resource, resource.calendar
-> [Modules/mail](odoo-18/Modules/mail.md) — mail.thread, activity integration
-> [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — State machine pattern

---

## Module Info (`__manifest__.py`)

**File:** `/Users/tri-mac/odoo/odoo19/odoo/addons/hr/__manifest__.py`

| Property | Value |
|----------|-------|
| Name | Employees |
| Version | 1.1 |
| Category | Human Resources/Employees |
| Sequence | 95 |
| Summary | Centralize employee information |
| Author | Odoo S.A. |
| License | LGPL-3 |
| Application | True |
| Installable | True |

**Dependencies:**
- `base_setup` — Initial setup wizard and configuration
- `digest` — Scheduled KPI digest emails
- `phone_validation` — Phone number formatting/normalization
- `resource_mail` — Resource scheduling with mail integration
- `web` — Web framework

**L4 - Why these dependencies matter:**
- `phone_validation` is used by `_onchange_phone_validation_employee` to format `work_phone` and `mobile_phone` using `force_format='INTERNATIONAL'`
- `resource_mail` bridges `resource.calendar` with mail.activity so that meeting invitations respect employee schedules
- `digest` uses the `digest.digest` model to email HR KPIs (employee counts, upcoming contract expirations) on a schedule

**Security Groups:**
- `hr.group_hr_user` — "Officer: Manage all employees" (implies `base.group_user`)
- `hr.group_hr_manager` — "Administrator" (implies `hr.group_hr_user`; root and admin auto-added)
- `res_groups_privilege_employees` — "Employees" privilege (used by both hr_user and hr_manager)

**Asset Bundles:**
- `web.assets_backend` — All HR JavaScript/SCSS
- `im_livechat.assets_embed_core` + `mail.assets_public` — Employee presence/chat integration (employees visible in livechat)
- Test suites in `web.qunit_suite_tests`, `web.assets_unit_tests`, `web.assets_tests`

---

## 1. HR Employee (`hr.employee`)

**File:** `/Users/tri-mac/odoo/odoo19/odoo/addons/hr/models/hr_employee.py`

### Basic Info

| Property | Value |
|----------|-------|
| `_name` | `hr.employee` |
| `_description` | Employee |
| `_inherit` | `mail.thread.main.attachment`, `mail.activity.mixin`, `resource.mixin`, `avatar.mixin` |
| `_inherits` | `{'hr.version': 'version_id'}` |
| `_order` | name |
| `_primary_email` | `work_email` |

**L4 - `_inherits` Delegation Pattern:**
`hr.employee` uses Odoo's delegation inheritance (`_inherits`) rather than classic extension. This means:
- Every `hr.employee` record has a corresponding `hr.version` record stored in a separate table (`hr_version`)
- Fields defined on `hr.version` appear directly on `hr.employee` via SQL join at read time
- **At create time**: `version_id` (the Many2one to `hr.version`) is auto-created and linked before the employee record is inserted
- **At write time**: Fields inherited from `hr.version` are written to the version record, not the employee record
- `version_id` is NOT stored (`store=False`) — it is computed via `_compute_version_id` and searched via `_search_version_id`
- The `_field_to_sql` override ensures searching on `version_id` field expressions routes to `current_version_id`
- **Performance**: `_inherits` causes a SQL JOIN between `hr_employee` and `hr_version` on every read. For reports or search operations across many employees, this can be a bottleneck. Consider adding explicit indexes on `current_version_id` (already stored) for frequently filtered fields.
- **Extension point**: Custom fields that should track contract changes over time (e.g., job title, department, wage) belong on `hr.version`, not `hr.employee`, to get automatic versioning.

**L4 - Odoo 18 to 19 Breaking Change:**
In Odoo 18, `hr.contract` was a separate model with a Many2one to `hr.employee`. In Odoo 19, `hr.contract` was replaced entirely by `hr.version`. The `hr.contract` model is now in the `hr_contract` sub-module and acts as a view/component layer on top of `hr.version`. This is a **major architectural shift** — all contract fields (`contract_date_start`, `contract_date_end`, `trial_date_end`, `wage`, `contract_type_id`, `structure_type_id`, `resource_calendar_id`) live on `hr.version`.

### Inheritance Chain

```
mail.thread.main.attachment  (Message posting, attachments, mail tracking)
    └─ mail.activity.mixin  (Activity scheduling, deadline tracking)
        └─ resource.mixin   (Calendar attendance, timezone, working hours)
            └─ avatar.mixin (Avatar image management)
                └─ hr.employee
```

### Key Fields

#### Identity & Resource Fields

| Field | Type | Groups | Notes |
|-------|------|--------|-------|
| `name` | Char | — | Related to `resource_id.name`; `store=True, readonly=False` so name changes write back to `resource.resource` |
| `resource_id` | Many2one (`resource.resource`) | — | **Required**. Created automatically via `_inherits`. Cascade-deletes when employee is deleted. |
| `resource_calendar_id` | Many2one (`resource.calendar`) | — | **Inherited from `version_id`**. Related stored on `hr.version`; `index=False, store=False` on employee. Calendar changes on current version trigger `resource.resource` write via `write()` override. |
| `user_id` | Many2one (`res.users`) | — | Related to `resource_id.user_id`; `store=True, precompute=True`. Used for presence detection, login, messaging. `ondelete='restrict'`. |
| `user_partner_id` | Many2one (`res.partner`) | — | `related_sudo=False` — always computed with user ACLs |
| `share` | Boolean | — | Related to `user_id.share` — portal/external users |
| `phone` | Char | — | Related to `user_id.phone` |
| `im_status` | Char | — | Related to `user_id.im_status` — online/away/offline |
| `email` | Char | — | Related to `user_id.email` |

#### Company & Org Structure

| Field | Type | Groups | Notes |
|-------|------|--------|-------|
| `company_id` | Many2one (`res.company`) | — | **Required**. Set at create time from context/company. `tracking=True` — every change is logged. |
| `company_country_id` | Many2one (`res.country`) | base.group_system, hr.group_hr_user | Related to `company_id.country_id` |
| `company_country_code` | Char | base.group_system, hr.group_hr_user | ISO country code |
| `department_id` | Many2one (`hr.department`) | — | **On `hr.version`**, not `hr.employee` directly. Inherited. Drives department access via `member_ids`. |
| `parent_id` | Many2one (`hr.employee`) | — | The employee's direct **manager**. Used in org chart, approval chains, security rules. |
| `child_ids` | One2many (`hr.employee`) | — | Inverse of `parent_id`. Direct subordinates only. |
| `coach_id` | Many2one (`hr.employee`) | — | Coach (distinct from manager). `compute`/`store` from manager. Auto-set to `parent_id` if not explicitly set. No enforced rights — purely informational. |
| `category_ids` | Many2many (`hr.employee.category`) | hr.group_hr_user | Tags for grouping employees (e.g., "Remote", "Contractor"). Displayed as colored chips. |

#### Contact & Communication

| Field | Type | Groups | Notes |
|-------|------|--------|-------|
| `work_contact_id` | Many2one (`res.partner`) | — | Work contact partner. Created automatically by `_create_work_contacts()` if not provided. Single partner per employee. Used for messaging. |
| `work_email` | Char | — | `compute`/`store`/`inverse` from `work_contact_id`. Normalized on write via `email_normalize`. Set as `_primary_email`. |
| `work_phone` | Char | — | `compute`/`store`/`inverse` from `work_contact_id`. Formatted with `phone_validation` on change. |
| `mobile_phone` | Char | — | Separate from work contact partner. Does NOT sync back to partner. |
| `work_location_id` | Many2one (`hr.work.location`) | — | **On `hr.version`**. Work site/building/address. `domain="[('address_id', '=', address_id)]"`. |
| `work_location_name` | Char | — | Computed from `version_id.work_location_id.name` |
| `work_location_type` | Selection | — | Computed from `version_id.work_location_id.location_type`. Values: `home`, `office`, `other`. |

#### Presence & Activity (resource.mixin)

| Field | Type | Notes |
|-------|------|-------|
| `hr_presence_state` | Selection | Computed: `present`, `absent`, `archive`, `out_of_working_hour`. Override point for `hr_attendance`, `hr_holidays` modules. |
| `hr_icon_display` | Selection | `presence_present`, `presence_out_of_working_hour`, `presence_absent`, `presence_archive`, `presence_undetermined`. Used in Kanban card icons. |
| `show_hr_icon_display` | Boolean | True if employee has a `user_id` |
| `last_activity` | Date | Last time user was "online" in the system |
| `last_activity_time` | Char | Formatted time of last activity (today only) |
| `newly_hired` | Boolean | `True` if `create_date` < 90 days ago. `search` enabled. |

**L4 - Presence State Computation:**
`_compute_presence_state()` has two control paths:
1. **Presence control disabled** (`company.hr_presence_control_login = False`): Employee is always `out_of_working_hour` unless archived
2. **Presence control enabled**: Looks at `res.users.presence_ids` for "online" status. If online → `present`; if offline during working hours → `absent`. This is extended by `hr_attendance` to include badge check-in data.

#### Private / Sensitive Info (hr.group_hr_user)

| Field | Type | Notes |
|-------|------|-------|
| `legal_name` | Char | `compute` from `name` if not set. For employees with different legal vs. display name. |
| `private_email` / `private_phone` / `private_lang` | Char/Selection | Personal contact info. Not synced to any partner. |
| `private_street`, `private_street2`, `private_city`, `private_zip` | Char | Home address. Related to `hr.version` via `_inherits`. |
| `private_state_id` | Many2one (`res.country.state`) | Domain-limited to `private_country_id`. Onchange sets `private_country_id` from state. |
| `private_country_id` | Many2one (`res.country`) | Controls state domain via `_compute_allowed_country_state_ids`. |
| `private_latitude` / `private_longitude` | Float | Geolocation of home address. Used by `hr_homeworking` for remote work requests. |
| `is_address_home_a_company` | Boolean | Flags home address as corporate property. |
| `birthday` | Date | Private. Displayed publicly only if `birthday_public_display = True`. `birthday_public_display_string` computes human-readable format. |
| `gender` / `sex` | Selection | `sex` on `hr.version` (legal gender); `gender` may be added by localization modules. |
| `marital` | Selection | `_get_marital_status_selection` returns: `single`, `married`, `cohabitant`, `widower`, `divorced`. Default: `single`. |
| `spouse_complete_name` / `spouse_birthdate` | Char/Date | |
| `children` | Integer | Dependent children count |
| `place_of_birth` / `country_of_birth` | Char/M2O | |
| `identification_id` | Char | National ID number (government-issued). SSN, Aadhaar, SIN, etc. Help text explicitly enumerates examples. |
| `ssnid` | Char | Social Security Number (US-specific concept; localizations add constraints). |
| `passport_id` / `passport_expiration_date` | Char/Date | |
| `permit_no` | Char | Work permit number |
| `visa_no` / `visa_expire` | Char/Date | Visa details |
| `work_permit_expiration_date` | Date | Triggers `_cron` scheduled activity warning via `notify_expiring_contract_work_permit()` |
| `has_work_permit` | Binary | File upload for work permit document |
| `work_permit_name` | Char | Computed: `{name}_{permit_no}_work_permit`. Used as file attachment name. |
| `id_card` / `driving_license` | Binary | Document uploads |
| `private_car_plate` | Char | Supports space-separated multiple plates |
| `emergency_contact` / `emergency_phone` | Char | |
| `certificate` | Selection | Education: `graduate`, `bachelor`, `master`, `doctor`, `other` |
| `study_field` / `study_school` | Char | |
| `termination_date` | Date | Set on `hr.version` (`departure_date`). Reflected as `date_end` when version is past. |

#### Bank & Salary

| Field | Type | Groups | Notes |
|-------|------|--------|-------|
| `bank_account_ids` | Many2many (`res.partner.bank`) | hr.group_hr_user | Domain: `partner_id = work_contact_id`. Bank accounts used for salary payment. |
| `salary_distribution` | Json | hr.group_hr_user | Map of `{bank_account_id: {sequence, amount, amount_is_percentage}}`. Auto-syncs when bank accounts change. Percentages must sum to 100%. |
| `is_trusted_bank_account` | Boolean | hr.group_hr_user | `True` if primary bank account has `allow_out_payment = True`. Triggers warning UI. |
| `primary_bank_account_id` | Many2one | hr.group_hr_user | Minimum sequence bank account from `salary_distribution` |
| `has_multiple_bank_accounts` | Boolean | hr.group_hr_user | `True` if > 1 bank account |

**L4 - `salary_distribution` Json Structure:**
```python
{
  "<bank_account_id_int>": {
    "sequence": int,          # sort order
    "amount": float,          # percentage (0-100) or fixed amount
    "amount_is_percentage": bool
  }
}
```
Auto-populated when bank accounts are added. Percentages redistributed on removal. Constraint validates sum == 100% for percentage-mode accounts. Fixed-amount accounts bypass the 100% sum check.

#### Contract / Version Fields (hr.version via _inherits, groups=hr.group_hr_manager)

| Field | Notes |
|-------|-------|
| `version_id` | Non-stored computed Many2one to current version. Used as `_inherits` anchor. |
| `current_version_id` | **Stored**. Most-recent version by `date_version <= today()`. Used for all business logic. |
| `current_date_version` | Related to `current_version_id.date_version` |
| `version_ids` | All versions for this employee (One2many). Required=True. |
| `versions_count` | Count of all versions |
| `contract_date_start` / `contract_date_end` | Contract validity period. `contract_date_end = False` = indefinite. |
| `trial_date_end` | Trial period end |
| `date_start` / `date_end` | Computed: `date_version` vs. `contract_date_start` max; next version's `date_version - 1 day` vs. `contract_date_end` min. |
| `is_current` / `is_past` / `is_future` | Computed boolean flags for version status |
| `is_in_contract` | `True` if today falls within contract period |
| `wage` / `contract_wage` | Monthly gross wage. `contract_wage` computed from `_get_contract_wage()` which returns `wage` unless overridden by `hr_payroll`. |
| `contract_type_id` / `structure_type_id` | Contract type (CDD/CDI) and payroll structure type |

#### Misc

| Field | Type | Groups | Notes |
|-------|------|--------|-------|
| `barcode` | Char | hr.group_hr_user | Badge ID for attendance kiosk. **Unique**. Alphanumeric, max 18 chars. `copy=False`. Generated randomly via `generate_random_barcode()`: prefix `'041'` + 9 random digits. |
| `pin` | Char | hr.group_hr_user | Numeric PIN for attendance kiosk and POS cashier. `copy=False`. Must be all digits. |
| `color` | Integer | — | Kanban card color. Default 0 (neutral). |
| `tz` | Selection | — | User timezone. Onchange syncs from `resource_calendar_id.tz`. Falls back to company calendar tz, then UTC. |
| `employee_properties` | Properties | hr.group_hr_user | Company-specific custom fields defined via `company_id.employee_properties_definition` |
| `activity_ids` | One2many | hr.group_hr_user | Mail activities scheduled on this employee |

### Key Methods

#### Version & Contract Management

**`create_version(values)`** — Creates a new `hr.version` for this employee at a specific date.
- Requires `date_version` in `values`
- Copies all fields from `_get_version(date)` (the effective version at that date)
- Overwrites copied values with explicit `values` entries
- Writes `contract_date_end` back to the previous version if date gaps would occur
- Handles `sync_contract_dates` context internally
- Returns the newly created `hr.version` record

**`create_contract(date)`** — Shorthand for creating a version with `contract_date_start = date`.
- Finds the next future version and sets new `contract_date_end = next_version.date_version - 1 day`
- Returns existing version if one already exists at that exact date

**`_get_version(date=Today)`** — Returns the version effective at a given date (max `date_version <= date`). Falls back to earliest version if no match.

**`_get_contract_dates(date)`** — Returns `(date_from, date_to)` tuple for the contract active on `date`. Returns `(False, False)` if no active contract.

**`_get_contracts(date_start, date_end, use_latest_version=True, domain=None)`** — Returns contracts active within a date range, grouped by employee. Uses `_get_contract_versions()` internally.

**`_get_contract_versions(date_start, date_end, domain)`** — Returns a nested defaultdict: `{employee_id: {contract_start_date: versions}}`. Groups by day-level `date_version` granularity.

**`_get_versions_with_contract_overlap_with_period(date_from, date_to)`** — Returns versions that overlap at least one day with the given period. Used by attendance/timesheet reporting to find active contracts.

**`_get_all_contract_dates()`** — Returns all `(date_from, date_to)` intervals where employee was in contract. Used for gap analysis.

**`_check_dates()`** — `hr.version` constraint. Prevents overlapping contracts for the same employee. Uses `_read_group` with day-level granularity on `contract_date_start`/`contract_date_end`. Also validates `contract_date_start <= contract_date_end`.

**L4 - Overlap Detection Logic:**
The constraint reads all other versions for the same employee (excluding self), groups by `(contract_date_start:day, contract_date_end:day)`, and checks whether any existing version's period overlaps with the new/changed version's period. Periods `A` and `B` overlap if: `A_start <= B_end AND B_start <= A_end`.

#### User Synchronization

**`_onchange_user()`** — Called when `user_id` is set/changed.
- Syncs: `work_contact_id`, `user_id`, `image_1920` (if employee has no image), `tz`
- Also sets `name` from user if not already set
- Called during `create()` when `vals['user_id']` is provided

**`_sync_user(user, employee_has_image=False)`** — Returns dict of vals to sync from user to employee. Used by both `_onchange_user()` and `create()`.

**`_remove_work_contact_id(user, employee_company)`** — Unlinks `work_contact_id` from old employees sharing the same partner when a user is reassigned to a new employee in the same company.

**L4 - Work Contact Partner Lifecycle:**
- On create: `_create_work_contacts()` creates a `res.partner` for each employee (sudo, in case HR officer lacks contact creation rights). Sets `name`, `email`, `phone`, `image_1920`, `company_id`.
- On write: `_inverse_work_contact_details()` syncs `email` and `phone` back to the partner when they change on the employee. If partner has multiple employees linked, syncing is skipped (avoids conflicts).
- On `work_contact_id` change: `write()` unsubscribes the old partner from messages, moves bank accounts to new partner (resetting `allow_out_payment`), and re-subscribes new partner.

#### Presence & Attendance

**`_compute_presence_state()`** — Sets `hr_presence_state` based on `user_id.im_status` and calendar working hours. `sudo` needed to read `presence_ids` from `res.users`. Overridden by `hr_attendance` to include badge data.

**`_get_employee_working_now()`** — Batch-computes which employees are within their scheduled working hours right now. Groups by timezone to minimize `resource.calendar` singleton calls. Returns list of employee IDs.

**`_get_calendars(date_from=None)`** — Returns `{employee_id: resource.calendar}` for the contract active at `date_from`. Filters `version_ids` to those where `_is_in_contract(date_from)`.

**`_get_expected_attendances(date_from, date_to)`** — Returns `Intervals` of expected working time for this employee over the period. Aggregates across all valid contract versions in the period. Falls back to company calendar if no contract.

**`_get_calendar_attendances(date_from, date_to)`** — Returns `{'days': int, 'hours': float}` of expected working days/hours. Aggregates across multiple contract versions.

**`_get_unusual_days(date_from, date_to)`** — Returns dict of public holidays / non-working days within the period. Checks all overlapping contract versions' calendars.

#### Archive / Lifecycle

**`action_archive()`** — Sets `active=False` on `resource.resource` (via `resource.mixin` inheritance). Triggers:
1. `is_past` flag → `True`
2. `hr_presence_state` → `'archive'`
3. `hr_icon_display` → `'presence_archive'`
4. Subordinates have `parent_id` nulled (via `_get_employee_m2o_to_empty_on_archived_employees`)
5. `hr.departure.wizard` opened (unless `no_wizard` context flag set)
6. Pending activities cancelled (via `mail.activity.mixin`)

**`action_unarchive()`** — Clears `departure_reason_id`, `departure_description`, `departure_date` on all versions. Restores `active=True`.

#### Banking

**`_sync_salary_distribution()`** — `@api.depends('bank_account_ids')`. Reacts to bank account additions/removals:
- **Added accounts**: Get `remaining_percentage / n_new` of the unallocated percentage (last account gets the remainder)
- **Removed accounts**: Their percentage is redistributed to the first remaining percentage-mode account
- Order preserved from `salary_distribution` sequence values

**`_check_salary_distribution()`** — SQL-level constraint. Validates each percentage is 0-100. Validates total percentage sum == 100% (with 4-digit float precision tolerance via `float_is_zero`).

**`action_open_allocation_wizard()`** — Opens `hr.bank.account.allocation.wizard` for managing `salary_distribution`.

**`action_toggle_primary_bank_account_trust()`** — Toggles `allow_out_payment` on the primary bank account.

#### Cron Jobs

**`_cron_update_current_version_id()`** — Searches all employees and recomputes `current_version_id`. Should be run daily via `ir.cron` to handle date transitions (when a new day begins and a future version becomes current).

**`notify_expiring_contract_work_permit()`** — `@api.model` cron. Searches for:
- Employees whose `contract_date_end == today + company.contract_expiration_notice_period`
- Employees whose `work_permit_expiration_date == today + company.work_permit_expiration_notice_period`
- Schedules `mail.activity` on each employee with deadline = expiration date

### Constraints

```python
_barcode_uniq = models.Constraint(
    'unique (barcode)',
    'The Badge ID must be unique, this one is already assigned to another employee.')
_user_uniq = models.Constraint(
    'unique (user_id, company_id)',
    'A user cannot be linked to multiple employees in the same company.')
```

**L4 - `barcode` Constraint:**
Format enforced by `_verify_barcode()`: alphanumeric (`^[A-Za-z0-9]+$`), max 18 chars. Numeric-only barcodes can be auto-generated. The `'041'` prefix in `generate_random_barcode()` follows Code 128 format conventions.

**L4 - `user_id` Multi-Company Constraint:**
A user CAN be linked to multiple employees across different companies (no constraint violation), but within the same company the link must be 1:1. This is enforced at DB level. The `ResUsers._compute_company_employee()` method correctly returns only the employee in the current active company.

### Security: Field Prefetch Design

**Critical L4 Pattern:**
The docstring on `HrEmployee` class explicitly warns: *"Any field only available on hr.employee (not hr.employee.public) should have `groups="hr.group_hr_user"` on its definition to avoid being prefetched when the user hasn't access to hr.employee."*

When a non-HR user searches/browses `hr.employee`, the ORM evaluates all fields on the model. Without group restrictions, the ORM would attempt to SELECT private fields and crash with an AccessError. By marking private fields with `groups="hr.group_hr_user"`, the ORM skips them during prefetch for non-HR users, allowing the search to succeed.

**`_ALLOW_READ_HR_EMPLOYEE` Sentinel:**
A module-level sentinel object used to grant read access to `hr.employee` in specific contexts (e.g., when setting many2many fields from models that don't have HR access). Used by `hr.mixin` and `_check_access()` override to bypass the ACL check.

### Access Bypass Flow

When a user without `hr.group_hr_user` calls `search()` or `read()` on `hr.employee`:
1. `_search()` override detects no `has_access('read')`
2. Proxies the search to `hr.employee.public` (which has no group restrictions)
3. Returns IDs of matching public employees
4. Super call filters to those IDs on the private model
5. `fetch()` / `search_fetch()` copies cache from public model for shared fields; raises `AccessError` for private fields

---

## 2. HR Version (`hr.version`)

**File:** `/Users/tri-mac/odoo/odoo19/odoo/addons/hr/models/hr_version.py`

### Basic Info

| Property | Value |
|----------|-------|
| `_name` | `hr.version` |
| `_description` | Version |
| `_inherit` | `mail.thread`, `mail.activity.mixin` |
| `_order` | `date_version` |
| `_rec_name` | `name` |

### Purpose & Design

`hr.version` is the **delegation inheritance** model for `hr.employee`. It stores all fields that change with the employment contract over time: job, department, working hours, wage, work location, etc.

Each `hr.employee` record has one or more `hr.version` records. The **current version** (most recent by `date_version`) determines the employee's active state.

**L4 - Why delegation and not classic inheritance?**
- `hr.employee` and `hr.version` share the same database ID space (`_inherits` creates a 1:1 relationship)
- `hr.version` can exist independently as a **contract template** (`employee_id = False`) — reusable blueprints for new hires
- When used as a template, the version's `get_values_from_contract_template()` copies a whitelist of fields (`job_id`, `department_id`, `contract_type_id`, `structure_type_id`, `wage`, `resource_calendar_id`, `hr_responsible_id`)
- When linked to an employee, the version becomes part of that employee's contract history

### Key Fields

| Field | Type | Groups | Notes |
|-------|------|--------|-------|
| `employee_id` | Many2one (`hr.employee`) | — | The parent employee. `index=True`. When `False`, this is a contract template. |
| `name` | Char | — | Auto-display: if linked to employee, shows formatted `date_version` (via `format_date_abbr()`); if template, shows the explicit `name`. |
| `date_version` | Date | hr.group_hr_user | **Required**. The effective date of this version. Unique index on `(employee_id, date_version) WHERE active = TRUE`. |
| `display_name` | Char | — | Computed: `name` for templates; `format_date_abbr(date_version)` for employee versions |
| `active` | Boolean | — | Version active flag. Can be used to soft-delete versions. |
| `last_modified_uid` / `last_modified_date` | M2O/Datetime | hr.group_hr_user | Tracks who/when last modified this version |

#### Personal Information (hr.group_hr_user)

| Field | Type | Notes |
|-------|------|-------|
| `country_id` | Many2one (`res.country`) | Nationality |
| `identification_id` | Char | National ID (government-issued) |
| `ssnid` | Char | Social Security Number |
| `passport_id` / `passport_expiration_date` | Char/Date | |
| `sex` | Selection | Legal gender: `male`, `female`, `other` |
| `private_street`, `private_street2`, `private_city`, `private_zip` | Char | Home address |
| `private_state_id` | Many2one | Domain-limited by `private_country_id` |
| `private_country_id` | Many2one | Controls state domain |
| `distance_home_work` / `distance_home_work_unit` | Integer/Selection | Raw value + unit (`kilometers`/`miles`) |
| `km_home_work` | Integer | Computed: miles × 1.609. Inverse writes back to `distance_home_work`. |
| `marital` | Selection | `single`, `married`, `cohabitant`, `widower`, `divorced` |
| `spouse_complete_name` / `spouse_birthdate` | Char/Date | |
| `children` | Integer | Dependent children |

#### Work Information (hr.group_hr_user)

| Field | Type | Notes |
|-------|------|-------|
| `employee_type` | Selection | `employee`, `worker`, `student`, `trainee`, `contractor`, `freelance` |
| `department_id` | Many2one (`hr.department`) | Current department |
| `member_of_department` | Boolean | `True` if `department_id` is in the current user's department hierarchy |
| `job_id` | Many2one (`hr.job`) | Current job position |
| `job_title` | Char | Custom job title (inverse sets `is_custom_job_title = True`) |
| `is_custom_job_title` | Boolean | `True` if manually overridden from `job_id.name` |
| `address_id` | Many2one (`res.partner`) | Work address. Default: company partner address. |
| `work_location_id` | Many2one (`hr.work.location`) | Domain: `address_id` of the version |
| `departure_reason_id` | Many2one (`hr.departure.reason`) | Set on archive. `ondelete='restrict'` — prevents deletion of reason in use. |
| `departure_description` | Html | Additional departure notes |
| `departure_date` | Date | Date of departure (archive date) |

#### Contract Information

| Field | Type | Groups | Notes |
|-------|------|--------|-------|
| `contract_date_start` / `contract_date_end` | Date | hr.group_hr_manager | Contract validity window. `contract_date_end = False` = indefinite. |
| `trial_date_end` | Date | hr.group_hr_manager | Trial period end |
| `date_start` / `date_end` | Date | hr.group_hr_manager | Computed: `max(date_version, contract_date_start)` / `min(next_version.date_version - 1, contract_date_end)` |
| `is_current` / `is_past` / `is_future` | Boolean | hr.group_hr_manager | Computed date-based flags |
| `is_in_contract` | Boolean | hr.group_hr_manager | `True` if today within contract period |
| `wage` | Monetary | hr.group_hr_manager | Monthly gross wage. `aggregator="avg"` for groupby views. |
| `contract_wage` | Monetary | hr.group_hr_manager | Computed via `_get_contract_wage()` |
| `structure_type_id` | Many2one (`hr.payroll.structure.type`) | hr.group_hr_manager | Auto-set from company country if not specified |
| `contract_type_id` | Many2one (`hr.contract.type`) | hr.group_hr_manager | Employment type |
| `contract_template_id` | Many2one (`hr.version`) | hr.group_hr_user | Self-referential link to another version used as a template |

#### Calendar & Flexibility

| Field | Type | Groups | Notes |
|-------|------|--------|-------|
| `resource_calendar_id` | Many2one (`resource.calendar`) | — | Working hours. Inverse writes to `employee.resource_id.calendar_id` when current. |
| `is_flexible` | Boolean | hr.group_hr_user | `True` if calendar has `flexible_hours = True` |
| `is_fully_flexible` | Boolean | hr.group_hr_user | `True` if no calendar at all (no fixed schedule) |
| `tz` | Selection | — | Related from `employee_id.tz` |

### Key Methods

**`_compute_is_current()`** — `date_start <= today` and (`date_end = False` or `date_end >= today`). Note: uses `date_start` (which is `max(date_version, contract_date_start)`), not `date_version` directly.

**`_is_in_contract(date=Today)`** — Returns `True` if `contract_date_start` is set and today is within `[contract_date_start, date_end]`.

**`_is_overlapping_period(date_from, date_to)`** — Returns `True` if the version overlaps the given period by at least one day. Used in `_get_unusual_days()`.

**`_inverse_resource_calendar_id()`** — When set on the current version, writes `calendar_id` to `employee.resource_id`. Other versions' calendar changes do NOT propagate to the resource (only current version matters).

**`_compute_structure_type_id()`** — Auto-sets structure type from company country:
1. Search for structure type with matching `country_id`
2. Fall back to structure type with `country_id = False` (generic)
3. Only recomputes if field is empty OR current structure's country doesn't match company country

**`_get_normalized_wage()`** — Normalizes wage to an hourly equivalent for comparison across schedules:
- If calendar exists and has `hours_per_week`: `wage * 12 / 52 / hours_per_week`
- If no calendar (fully flexible): returns hourly wage directly (`wage` field)

**`get_values_from_contract_template(template)`** — Copies whitelist fields from a template version to the new version. Used in `create()` when `contract_template_id` is provided.

**`check_contract_finished()`** — Raises `ValidationError` if attempting to create a new version when the employee has a running contract (no `contract_date_end`) for the same period.

### Constraints

```python
# End date requires start date
_CHECK(contract_date_end IS NULL OR contract_date_start IS NOT NULL)

# Unique active version per employee per date
_UNIQUE_INDEX (employee_id, date_version) WHERE active = TRUE AND employee_id IS NOT NULL
```

**L4 - Partial Unique Index:**
The unique constraint is a PostgreSQL partial index (`WHERE active = TRUE AND employee_id IS NOT NULL`). This means:
- Multiple inactive versions can share the same `date_version` for the same employee
- Contract templates (`employee_id IS NULL`) are exempt entirely
- This allows soft-delete of versions without violating uniqueness

### `write()` Override — `sync_contract_dates` Context

The `write()` override on `hr.version` has complex date-sync logic:

```python
# If sync_contract_dates context is set, write normally
if self.env.context.get('sync_contract_dates'):
    return super().write(vals)

# If writing contract dates on multiple versions at once (different dates), block it
# If writing contract_date_start on a single-version employee, also update date_version
# If writing on a version with existing contract dates, propagate to sibling versions
```

**L4 - Date Propagation:**
When `contract_date_start` is written on a version that is NOT the first version for an employee, the method searches for all versions with the same `contract_date_start` and updates them in batch via `sync_contract_dates=True`. This ensures contract date changes propagate correctly across overlapping version chains.

---

## 3. HR Department (`hr.department`)

**File:** `/Users/tri-mac/odoo/odoo19/odoo/addons/hr/models/hr_department.py`

### Basic Info

| Property | Value |
|----------|-------|
| `_name` | `hr.department` |
| `_inherit` | `mail.thread`, `mail.activity.mixin` |
| `_order` | name |
| `_rec_name` | `complete_name` |
| `_parent_store` | True |

### Key Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Required, translate. Used as display name by default but `complete_name` is used via `_rec_name`. |
| `complete_name` | Char | Recursive compute: `'Parent / Child'` format. `search='_search_complete_name'` enables searching by full path. |
| `parent_id` | Many2one (`hr.department`) | Self-referential parent. `_parent_store=True` enables efficient `child_of`/`parent_of` domain operators. |
| `child_ids` | One2many | Children |
| `parent_path` | Char | Materialized path: `'1/5/23/'`. Used for `master_department_id` compute and `child_of` domain. |
| `master_department_id` | Many2one | Root of the department tree. `store=True`. Computed: `int(parent_path.split('/')[0])`. |
| `manager_id` | Many2one (`hr.employee`) | Department head. `tracking=True` — changes logged. Domain: employees in allowed companies. |
| `member_ids` | One2many (`hr.employee`) | Department members. `readonly=True` — set via `department_id` on employee. |
| `total_employee` | Integer | Computed: count of active employees in department AND in current user's allowed companies. `sudo()` used. |
| `company_id` | Many2one (`res.company`) | Scoping company |
| `active` | Boolean | Allows soft-delete of departments |
| `color` | Integer | Kanban color |
| `note` | Text | Internal notes |
| `jobs_ids` | One2many (`hr.job`) | Jobs in this department |
| `plan_ids` / `plans_count` | One2many/Integer | Onboarding plans assigned to this department |
| `has_read_access` | Boolean | Search-only field. `_search_has_read_access()` returns all departments if user has HR access; returns only departments where user is manager if not. |

### Key Methods

**`_check_parent_id()`** — `constrains('parent_id')`. Calls `_has_cycle()` inherited from `parent_store`. Raises `ValidationError` if a department is its own ancestor.

**`write()` override — `_update_employee_manager(manager_id)`:**
When `manager_id` changes on a department:
1. Find all employees whose `parent_id` was the OLD manager and whose department is this department or its children
2. Set those employees' `parent_id` to the NEW manager
This cascades the org chart down the department hierarchy.

**`_compute_total_employee()`** — Uses `_read_group` with `sudo()`. Counts employees where `department_id in self.ids` AND `company_id in env.companies`. The `sudo()` is necessary because non-HR users can read the department but not all employees.

**`_search_has_read_access()`** — Custom search for `has_read_access` field:
- If user has HR access (`has_access('read')` on `hr.employee`): returns all departments (`[(1, '=', 1)]`)
- Otherwise: returns departments where the user is the manager (`manager_id in user.employee_ids`)
- Supports `IN` operator only

**`_search_complete_name()`** — Supports `=`, `!=`, `ilike`, `not ilike`, `in`, `not in`, `=ilike` operators. The `=ilike` operator converts `_` and `%` wildcards from the input to regex patterns for full wildcard matching.

**`get_formview_action()`** — If user is not HR and context has `open_employees_kanban=True`, redirects to `hr.employee.public` kanban with the department pre-filtered.

**`action_employee_from_department()`** — Opens the employee list (private or public model based on access). Pre-filters by department and sets `search_default_group_department=1` to show kanban grouped by department.

**`get_department_hierarchy()`** — Returns dict with `parent`, `self`, and `children`, each containing `id`, `name`, and `employees` count. Used by the org chart view.

**L4 - Manager Propagation Edge Case:**
When a department manager changes, `_update_employee_manager()` only updates employees whose `parent_id` was the OLD manager. If an employee was in the department but had a different manager (e.g., a skip-level), their `parent_id` is NOT updated. This is correct behavior — only direct reports to the previous manager are reassigned.

---

## 4. HR Job (`hr.job`)

**File:** `/Users/tri-mac/odoo/odoo19/odoo/addons/hr/models/hr_job.py`

### Basic Info

| Property | Value |
|----------|-------|
| `_name` | `hr.job` |
| `_inherit` | `mail.thread` |
| `_order` | `sequence` |

### Key Fields

| Field | Type | Groups | Notes |
|-------|------|--------|-------|
| `name` | Char | — | Job title. `required=True`, `index='trigram'`, `translate=True`. Trigram index enables fast `ilike` searches. |
| `sequence` | Integer | — | Sort order. Default: 10. |
| `active` | Boolean | — | |
| `department_id` | Many2one (`hr.department`) | — | `index='btree_not_null'` — improves `department_id` filter performance |
| `company_id` | Many2one (`res.company`) | — | Default: `self.env.company` |
| `description` | Html | — | Job description. Uses `handle_history_divergence()` for collaborative editing (shows "last saved" vs. current if divergent). |
| `requirements` | Text | hr.group_hr_user | Plain text requirements list |
| `contract_type_id` | Many2one (`hr.contract.type`) | — | Default employment type for this position |
| `user_id` | Many2one (`res.users`) | hr.group_hr_user | Recruiter. Default: current user. Added as follower to applicant records. |
| `allowed_user_ids` | Many2many (`res.users`) | — | Computed: all internal users in the job's company. **TODO**: Marked for removal in master. |
| `no_of_recruitment` | Integer | — | Target headcount for recruitment. Default: 1. Copy=False. **Must be >= 0** (DB constraint). |
| `employee_ids` | One2many (`hr.employee`) | base.group_user | All employees currently in this job (active and inactive) |
| `no_of_employee` | Integer | hr.group_hr_user | Computed: count of ACTIVE employees in this job |
| `expected_employees` | Integer | hr.group_hr_user | Computed: `no_of_employee + no_of_recruitment` |

### Key Methods

**`_compute_employees()`** — `_read_group` on `hr.employee` by `job_id`. Counts only `active=True` employees for `no_of_employee`. `expected_employees` is a simple sum of the count plus `no_of_recruitment`.

**`create()` override** — `with_context(mail_create_nosubscribe=True)` prevents the current user from being auto-added as a follower on all created job positions.

**`write()` override** — Calls `handle_history_divergence(self, 'description', vals)` when writing to a single record. This is an HTML editor integration that handles concurrent edits by different users.

**`copy_data()` override** — Appends `_(s (copy)")` to the job name using the translation-aware `_()` function. Safe for all languages.

### Constraints

```python
_name_company_uniq = models.Constraint(
    'unique(name, company_id, department_id)',
    'The name of the job position must be unique per department in company!')
_no_of_recruitment_positive = models.Constraint(
    'CHECK(no_of_recruitment >= 0)',
    'The expected number of new employees must be positive.')
```

---

## 5. HR Employee Category (`hr.employee.category`)

**File:** `/Users/tri-mac/odoo/odoo19/odoo/addons/hr/models/hr_employee_category.py`

### Basic Info

| Property | Value |
|----------|-------|
| `_name` | `hr.employee.category` |
| `_description` | Employee Category |

### Key Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Required. **Unique** (`_name_uniq` constraint). |
| `color` | Integer | Default: random 1-11 via `_get_default_color()`. Used as Kanban chip color. |
| `employee_ids` | Many2many (`hr.employee`) | Inverse of `category_ids` on employee |

### Key Methods

**`_get_default_color()`** — Returns `randint(1, 11)`. Called at record creation time, so each category gets a different random color.

**L4 - Color Randomization:**
Random color assignment means the same category can have different colors in different databases. For consistency in multi-instance deployments, explicitly set the color field in data files.

---

## 6. HR Work Location (`hr.work.location`)

**File:** `/Users/tri-mac/odoo/odoo19/odoo/addons/hr/models/hr_work_location.py`

### Basic Info

| Property | Value |
|----------|-------|
| `_name` | `hr.work.location` |
| `_order` | name |

### Key Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Required. Work location name (e.g., "Building A - Floor 3"). |
| `company_id` | Many2one (`res.company`) | Required. Default: `self.env.company`. Scoping for multi-company. |
| `location_type` | Selection | `home`, `office`, `other`. Default: `office`. |
| `address_id` | Many2one (`res.partner`) | Required. The work address/office address. Employees' `work_location_id` domain filters by `address_id`. |
| `location_number` | Char | Optional location identifier (room number, desk number, etc.). |

---

## 7. HR Contract Type (`hr.contract.type`)

**File:** `/Users/tri-mac/odoo/odoo19/odoo/addons/hr/models/hr_contract_type.py`

### Basic Info

| Property | Value |
|----------|-------|
| `_name` | `hr.contract.type` |
| `_description` | Contract Type |
| `_order` | `sequence` |

### Key Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Required, translate |
| `code` | Char | Computed from `name` if not set (`_compute_code`, `store=True, readonly=False`). Allows override for shorthand codes (e.g., "CDI" vs "Permanent"). |
| `sequence` | Integer | Sort order |
| `country_id` | Many2one (`res.country`) | Domain: current companies' countries. Used for localization — different contract types per jurisdiction. |

---

## 8. HR Payroll Structure Type (`hr.payroll.structure.type`)

**File:** `/Users/tri-mac/odoo/odoo19/odoo/addons/hr/models/hr_payroll_structure_type.py`

### Basic Info

| Property | Value |
|----------|-------|
| `_name` | `hr.payroll.structure.type` |

### Key Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Salary structure type name (e.g., "Monthly Salaried", "Hourly Workers") |
| `default_resource_calendar_id` | Many2one (`resource.calendar`) | Default working hours for this structure type. Default: `company.resource_calendar_id`. |
| `country_id` | Many2one (`res.country`) | Domain: current companies' countries. Drives auto-assignment on `hr.version`. |
| `country_code` | Char | Related to `country_id.code` |

---

## 9. HR Departure Reason (`hr.departure.reason`)

**File:** `/Users/tri-mac/odoo/odoo19/odoo/addons/hr/models/hr_departure_reason.py`

### Basic Info

| Property | Value |
|----------|-------|
| `_name` | `hr.departure.reason` |

### Key Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Required, translate |
| `sequence` | Integer | Sort order. Default: 10 |
| `country_id` | Many2one (`res.country`) | Default: `company.country_id`. Used for localization — different reason lists per country. |
| `country_code` | Char | Related to `country_id.code` |

### Key Methods

**`_get_default_departure_reasons()`** — Returns the set of internal XML IDs for the 3 default reasons: `departure_fired`, `departure_resigned`, `departure_retired`.

**`_unlink_except_default_departure_reasons()`** — `@api.ondelete(at_uninstall=False)`. Prevents deletion of any of the 3 default departure reasons. This protects referential integrity in audit trails.

---

## 10. Resource Calendar (`resource.calendar`)

**File:** `/Users/tri-mac/odoo/odoo19/odoo/addons/hr/models/resource_calendar.py`

### Key Methods

**`transfer_leaves_to(other_calendar, resources=None, from_date=None)`** — Moves `resource.calendar.leaves` from `self` to `other_calendar`:
- Filters: leaves on `self` calendars, starting from `from_date` (default: today midnight)
- Optionally filters to specific `resources`
- Writes `calendar_id = other_calendar.id` on matching leaves
- Used when an employee's working schedule changes (e.g., promotion, department transfer) to migrate time-off requests

---

## 11. Resource Resource (`resource.resource`)

**File:** `/Users/tri-mac/odoo/odoo19/odoo/addons/hr/models/resource.py`

### Additional Fields Added by hr Module

| Field | Type | Notes |
|-------|------|-------|
| `user_id` | Many2one | `copy=False` — user link doesn't copy on duplicate |
| `employee_id` | One2many (`hr.employee`) | `check_company=True`, context `active_test=False` — can find inactive employee |
| `job_title` | Char | Computed from `employee_id.job_title` |
| `department_id` | Many2one | Computed from `employee_id.department_id` |
| `work_location_id` | Many2one | Related from `employee_id` |
| `work_email` / `work_phone` | Char | Related |
| `show_hr_icon_display` / `hr_icon_display` | Boolean/Selection | Related from `employee_id` |
| `calendar_id` | Many2one | Inverse: `_inverse_calendar_id()` writes back to `employee.resource_calendar_id` |

### Key Methods

**`_inverse_calendar_id()`** — When `calendar_id` is set directly on `resource.resource`, this method syncs it back to the employee's current version's `resource_calendar_id`. This is the inverse of the `related` field on `hr.employee`.

**`_get_resource_without_contract()`** — Returns resources whose employees have NO active contract (no `hr.version` with `contract_date_start` set). Used by attendance/timesheet modules to identify employees not yet on payroll.

**`_get_contracts_valid_periods(start, end)`** — Returns `{resource_id: {calendar: Intervals}}` mapping for each resource's contract validity periods. Handles timezone conversion, date boundary clipping, and multiple calendar changes per employee.

**`_get_calendars_validity_within_period(start, end)`** — Returns which calendars are valid for each resource during a period. Distinguishes:
1. Resources without contracts: uses company default calendar
2. Resources with contracts: uses contract calendars with validity intervals

**`_get_flexible_resources_calendars_validity_within_period(start, end)`** — Similar to above but handles fully flexible resources (no fixed schedule). Computes intersection of default work intervals with contract periods.

**`_get_calendar_at(date_target, tz)`** — Returns the calendar effective for this resource on a specific date. Batch-overrides parent method: uses `employee._get_calendars()` instead of `resource.calendar` for resources with employees.

---

## 12. HR Employee Public (`hr.employee.public`)

**File:** `/Users/tri-mac/odoo/odoo19/odoo/addons/hr/models/hr_employee_public.py`

### Basic Info

| Property | Value |
|----------|-------|
| `_name` | `hr.employee.public` |
| `_auto` | False (SQL VIEW, not a table) |
| `_table` | `hr_employee_public` |
| `_log_access` | True (includes create_date, write_date, etc.) |

### Purpose

`hr.employee.public` is a **read-only SQL VIEW** that non-HR users (and public/portal users) can query without triggering AccessError on sensitive fields. It joins `hr_employee` with `hr_version` on `current_version_id`:

```sql
CREATE OR REPLACE VIEW hr_employee_public AS (
    SELECT
        e.id AS id,
        e.id AS employee_id,
        e.name AS name,
        e.active AS active,
        -- all stored columns from hr_employee and hr_version (conditional on field.store)
        v.*   -- version fields that are stored
    FROM hr_employee e
    JOIN hr_version v ON v.id = e.current_version_id
)
```

### Fields (All Read-Only)

All fields are `readonly=True`. Key additions vs. `hr.employee`:
- `is_manager` — `True` if the current user is this employee's manager (computed via `id child_of user.employee_id`)
- `is_user` — `True` if this is the current user's own record
- `child_ids` — One2many to `hr.employee.public` (org chart subordinates)
- `newly_hired` — Search-enabled computed field

### `_get_fields()` — Dynamic View Column Selection

The `init()` method builds the SQL view dynamically using `_get_fields()`, which:
1. Includes base fields (`id`, `employee_id`, `name`, `active`) explicitly
2. For each field on `hr.employee.public`, determines if it should come from `e.*` (employee table) or `v.*` (version table) based on whether the field is stored on `hr.version` and whether `hr.version` stores it
3. This ensures that `current_version_id`-linked data is always fresh

**L4 - Performance Implication:**
The view JOIN means every query on `hr.employee.public` is internally a JOIN between `hr_employee` and `hr_version`. For large datasets, ensure `hr_version.current_version_id` has a DB index (it does, as a stored Many2one).

---

## 13. Supporting Models

### hr.mixin (`hr.models.hr_mixin`)

Abstract model providing a context sentinel pattern for many2many fields pointing to `hr.employee`.

**Problem it solves:** Since Odoo 19, setting a many2many field requires read access to the target model. This blocks non-HR users from creating records that reference employees (e.g., a project task assigned to an employee). The `hr.mixin` override passes `_ALLOW_READ_HR_EMPLOYEE` in context, which tricks `_check_access()` into granting read access.

### res.company Fields (added by hr)

| Field | Type | Notes |
|-------|------|-------|
| `hr_presence_control_login` | Boolean | Default `True`. Enables "present/absent" based on user login. |
| `hr_presence_control_email` | Boolean | Presence based on email count (requires `hr_attendance`). |
| `hr_presence_control_ip` | Boolean | Presence based on IP allowlist (`hr_presence_control_ip_list`). |
| `hr_presence_control_attendance` | Boolean | Presence based on badge attendance. |
| `hr_presence_control_email_amount` | Integer | Threshold for email-based presence |
| `hr_presence_control_ip_list` | Char | Comma-separated IP addresses |
| `employee_properties_definition` | PropertiesDefinition | Company-specific employee custom field definitions |
| `contract_expiration_notice_period` | Integer | Days before contract end to trigger warning. Default: 7. |
| `work_permit_expiration_notice_period` | Integer | Days before work permit expiry. Default: 60. |

### res.partner Fields (added by hr)

| Field | Type | Groups | Notes |
|-------|------|--------|-------|
| `employee_ids` | One2many (`hr.employee`) | hr.group_hr_user | Based on `work_contact_id` link |
| `employees_count` | Integer | hr.group_hr_user | Count of employees linked via work contact |
| `employee` | Boolean | — | `True` if any employee links to this partner |

### res.users Fields (added by hr)

| Field | Type | Notes |
|-------|------|-------|
| `employee_ids` | One2many (`hr.employee`) | All employees linked to this user (potentially multiple in different companies) |
| `employee_id` | Many2one | Current company employee only (computed/search by current company) |
| `employee_resource_calendar_id` | Many2one | Related to `employee_id.resource_calendar_id` |
| `bank_account_ids` | Many2many | Related to `employee_id.bank_account_ids` |

**`SELF_READABLE_FIELDS` / `SELF_WRITEABLE_FIELDS` extensions:**
Users can read and write their own private HR fields (address, emergency contact, etc.) via the "My Preferences" form, even without `hr.group_hr_user`. The `hr.res_users_view_form_preferences` view uses `get_view()` override with `with_user(SUPERUSER_ID)` to expose all fields.

### res.partner.bank Fields (added by hr)

| Field | Type | Notes |
|-------|------|-------|
| `employee_id` | Many2many | Computed: the employee whose `work_contact_id` owns this account |
| `employee_salary_amount` | Float | Salary allocation for this account |
| `employee_salary_amount_is_percentage` | Boolean | Whether allocation is percentage vs. fixed |
| `employee_has_multiple_bank_accounts` | Boolean | Related from employee |

---

## Summary of Model Relationships

```
hr.employee (_inherits hr.version)
    |-- delegate --> hr.version (version_id, current_version_id, version_ids)
    |-- belongs to --> res.company (company_id)
    |-- belongs to --> res.users (user_id) --> res.partner (user_partner_id)
    |-- belongs to --> res.partner (work_contact_id)
    |-- belongs to --> hr.department (department_id — via version)
    |-- belongs to --> hr.job (job_id — via version)
    |-- belongs to --> hr.work.location (work_location_id — via version)
    |-- belongs to --> hr.contract.type (contract_type_id — via version)
    |-- belongs to --> hr.payroll.structure.type (structure_type_id — via version)
    |-- belongs to --> resource.resource (resource_id)
    |-- belongs to --> resource.calendar (resource_calendar_id — via version)
    |-- belongs to --> hr.employee (parent_id, coach_id)
    |-- has many --> hr.employee.category (category_ids)
    |-- has many --> res.partner.bank (bank_account_ids)
    |-- has many --> hr.version (version_ids)
    |-- triggers --> discuss.channel (auto-subscribe on department/user change)

hr.version
    |-- belongs to --> hr.employee (employee_id)
    |-- belongs to --> hr.department (department_id)
    |-- belongs to --> hr.job (job_id)
    |-- belongs to --> hr.work.location (work_location_id)
    |-- belongs to --> hr.contract.type (contract_type_id)
    |-- belongs to --> hr.payroll.structure.type (structure_type_id)
    |-- belongs to --> resource.calendar (resource_calendar_id)
    |-- belongs to --> hr.departure.reason (departure_reason_id)

hr.department
    |-- has many --> hr.employee (member_ids)
    |-- has many --> hr.job (jobs_ids)
    |-- parent/child --> hr.department (parent_id/child_ids)
    |-- has many --> mail.activity.plan (plan_ids)

resource.resource
    |-- has one --> hr.employee (employee_id)
    |-- belongs to --> res.users (user_id)
    |-- belongs to --> resource.calendar (calendar_id)

res.partner
    |-- has many --> hr.employee (employee_ids — via work_contact_id)

res.users
    |-- has many --> hr.employee (employee_ids)
```

---

## Important Constants and Selections

### Presence State (hr.employee)

```python
('present', 'Present')          # User online during working hours (presence control on)
('absent', 'Absent')            # User offline during working hours (presence control on)
('archive', 'Archived')          # Employee inactive
('out_of_working_hour', 'Off-Hours')  # Outside working schedule or presence control off
```

### HR Icon Display

```python
('presence_present', 'Present')
('presence_out_of_working_hour', 'Off-Hours')
('presence_absent', 'Absent')
('presence_archive', 'Archived')
('presence_undetermined', 'Undetermined')  # No user_id linked
```

### Work Location Type

```python
('home', 'Home')
('office', 'Office')
('other', 'Other')
```

### Certificate Levels

```python
('graduate', 'Graduate')
('bachelor', 'Bachelor')
('master', 'Master')
('doctor', 'Doctor')
('other', 'Other')
```

### Employee Type

```python
('employee', 'Employee')
('worker', 'Worker')
('student', 'Student')
('trainee', 'Trainee')
('contractor', 'Contractor')
('freelance', 'Freelancer')
```

### Marital Status

```python
('single', 'Single')
('married', 'Married')
('cohabitant', 'Legal Cohabitant')
('widower', 'Widower')
('divorced', 'Divorced')
```

### Gender

```python
('male', 'Male')
('female', 'Female')
('other', 'Other')
```

---

## Security Model (L4)

### Record Rules

| Model | Rule | Description |
|-------|------|-------------|
| `hr.employee` | `hr_employee_comp_rule` | Multi-company: can read if `company_id in user.companyies` OR `parent_id.user_id = user` OR `user is the manager` OR `user_id = user`. All internal users with `base.group_user` can read employees. |
| `hr.employee.public` | `hr_employee_public_comp_rule` | Same as `hr.employee` comp rule — public model mirrors private access. |
| `hr.department` | `hr_dept_comp_rule` | Multi-company: `company_id in user.company_ids OR company_id = False`. |
| `hr.job` | `hr_job_comp_rule` | Multi-company: `company_id in user.company_ids`. |
| `hr.version` (manager) | `ir_rule_hr_contract_manager` | Full access for `hr.group_hr_manager`. |
| `hr.version` (multi-company) | `ir_rule_hr_contract_multi_company` | `company_id in company_ids`. |
| `res.partner.bank` (non-HR) | `ir_rule_res_partner_bank_internal_users` | Block: `partner_id.employee_ids != False` — non-HR users cannot read employee bank accounts. |
| `res.partner.bank` (HR) | `ir_rule_res_partner_bank_employees` | Full access for `hr.group_hr_user`. |
| `hr.contract.type` | `ir_rule_hr_contract_type_multi_company` | Either no country restriction or country in user's companies. |
| `hr.departure.reason` | `ir_rule_hr_departure_reason_multi_company` | Either no country or country in user's companies' countries. |
| `hr.payroll.structure.type` | `ir_rule_hr_payroll_structure_type_multi_company` | Global rule: country in companies' countries or no country. |
| `mail.activity.plan` (manager) | `mail_plan_rule_group_hr_manager` | Only `hr.group_hr_manager` can edit plans. Read access is default (all internal users). |
| `mail.activity.plan.template` | `mail_plan_templates_rule_group_hr_manager` | Only managers can edit templates. |

### Field-Level Security Design Pattern

All sensitive fields on `hr.employee` and `hr.version` carry `groups="hr.group_hr_user"`. This:
1. Prevents prefetch errors for non-HR users (fields simply aren't loaded)
2. Raises `AccessError` on explicit read attempts
3. Is safe for users who ARE in the group

Contract-sensitive fields (`contract_date_start`, `wage`, etc.) use `groups="hr.group_hr_manager"` for additional restriction — only HR managers see compensation details.

### Bank Account Access Isolation

The `res.partner.bank` model is shared between employees (salary accounts) and regular contacts. The two-record rule pattern ensures:
- Non-HR internal users: can only see bank accounts where the partner is NOT an employee
- HR officers: can see all bank accounts (including salary accounts)
- This prevents non-HR staff from viewing payroll bank details via the partner or accounting views

---

## Error Scenarios

| Trigger | Error | Mechanism |
|---------|-------|-----------|
| Duplicate barcode | `ValidationError` | `_barcode_uniq = unique(barcode)` |
| User in same company twice | `ValidationError` | `_user_uniq = unique(user_id, company_id)` |
| Missing required field | `ValidationError` | ORM `required=True` |
| Overlapping contract dates | `ValidationError` | `hr.version._check_dates()` via `_constrains` |
| `contract_date_end` without `contract_date_start` | `ValidationError` | SQL `CHECK(contract_date_end IS NULL OR contract_date_start IS NOT NULL)` |
| Same date for two active versions | `ValidationError` | Partial unique index `(employee_id, date_version) WHERE active = TRUE` |
| Non-numeric PIN | `ValidationError` | `_verify_pin()` |
| Badge ID too long or non-alphanumeric | `ValidationError` | `_verify_barcode()` |
| Salary distribution percentages != 100% | `ValidationError` | `_check_salary_distribution()` |
| Percentage outside 0-100 | `ValidationError` | `_check_salary_distribution()` |
| Recursive department | `ValidationError` | `_check_parent_id()` via `_has_cycle()` |
| Work permit expiration date in past | Warning + activity scheduled | `_cron` + `notify_expiring_contract_work_permit()` |
| Contract template deleted while in use | `UserError` | `ondelete='restrict'` on `contract_template_id` |
| Default departure reason deleted | `UserError` | `_unlink_except_default_departure_reasons()` |

---

## Flows (Level 1 — Method Chains)

### Employee Creation Method Chain

```
hr.employee.create(vals_list)
  │
  ├─ [1] Batch by company
  │      super().create() with company context
  │
  ├─ [2] _inherits: hr.version record created and linked
  │      └─ _prepare_create_values() splits vals → employee vals + version vals
  │            └─ Fields inherited from hr.version written to version record
  │
  ├─ [3] _create() model method
  │      └─ Links version.employee_id = employee.id
  │      └─ Writes version fields from vals['stored']['hr.version']
  │
  ├─ [4] IF vals.get('user_id'):
  │      ├─ _sync_user(user, has_image)
  │      │    └─ Sets: work_contact_id, user_id, image_1920, tz
  │      └─ _remove_work_contact_id(user, company)
  │            └─ Nulls work_contact_id on old employees sharing same partner
  │
  ├─ [5] _create_work_contacts() [sudo]
  │      └─ Creates res.partner for each employee without one
  │            └─ Sets: name, email, phone, image_1920, company_id
  │
  ├─ [6] Avatar generation
  │      └─ If no image and has write access: _avatar_generate_svg()
  │            └─ Syncs SVG to work_contact_id.avatar
  │
  ├─ [7] Discuss channel auto-subscribe
  │      └─ Searches channels with subscription_department_ids matching employee dept
  │            └─ _subscribe_users_automatically()
  │
  ├─ [8] Onboarding plan notification
  │      └─ _message_log_batch() with URL to plan wizard
  │
  ├─ [9] _compute_current_version_id()
  │      └─ Sets current_version_id = the newly created version
  │            └─ (only version, so it's both current and first)
  │
  └─ [10] Returns employees batch (respects original vals order)
```

### Employee Archival Method Chain

```
hr.employee.action_archive()
  │
  ├─ super().action_archive() [from resource.mixin]
  │      ├─ write({'active': False}) on hr.employee
  │      │    └─ [A] is_past flag updated on current version
  │      │    └─ [B] hr_presence_state → 'archive'
  │      │    └─ [C] hr_icon_display → 'presence_archive'
  │      │    └─ [D] version_vals written to version_id:
  │      │            ├─ last_modified_date/uid
  │      │            └─ _track_set_log_message with version name
  │      └─ write({'active': False}) on resource.resource
  │            └─ Resource deactivated
  │
  ├─ _get_employee_m2o_to_empty_on_archived_employees()
  │      └─ Returns: ['parent_id', 'coach_id']
  │            └─ Subordinates: parent_id/coach_id nulled if in archived set
  │
  ├─ IF single employee AND no context.no_wizard:
  │      └─ Returns wizard action for hr.departure.wizard
  │            └─ Sets departure_date, departure_reason_id
  │            └─ Wizard write triggers: is_past, is_in_contract, departure fields
  │
  └─ Return res (None if wizard opened, dict otherwise)
```

### Version/Contract Creation Flow

```
employee.create_version({'date_version': '2025-01-01', 'wage': 5000})
  │
  ├─ _get_version('2025-01-01')
  │      └─ Returns version with max date_version <= 2025-01-01
  │
  ├─ IF same date already exists: return existing version
  │
  ├─ _get_contract_dates('2025-01-01')
  │      └─ Returns (date_from, date_to) of active contract
  │
  ├─ check_access('write') on employee AND version_to_copy
  │
  ├─ copy_data() from version_to_copy
  │      └─ Copies all non-O2M/M2M fields
  │
  ├─ Write with_context(sync_contract_dates=True):
  │      ├─ date_version = 2025-01-01
  │      ├─ employee_id = self.id
  │      └─ contract dates from _get_contract_dates
  │
  └─ write(new_version_vals)
        └─ Additional fields changed at version creation time
```

---

## Odoo 18 to 19 Major Architectural Changes

| Area | Odoo 18 | Odoo 19 |
|------|---------|---------|
| Contract model | `hr.contract` as separate model | `hr.version` via `_inherits` |
| Contract linking | `hr.contract.employee_id` Many2one | `hr.employee` inherits `hr.version` fields |
| Version tracking | No | `hr.version` with `date_version`, `is_current/past/future` |
| Salary fields | On `hr.contract` | On `hr.version` |
| Calendar linking | Via `resource.mixin` directly | Via `hr.version` (current version wins) |
| Presence state | Basic | Computed from user presence + calendar |
| Bank accounts | Single `bank_account_id` | `bank_account_ids` Many2many + `salary_distribution` Json |
| Salary distribution | Not available | New: multi-bank-account allocation with percentages |
| Department manager propagation | Not automatic | Automatic on manager change |
| Job description history | None | `handle_history_divergence()` for concurrent editing |
| Employee public model | `hr.employee.public` (simpler) | Enhanced with `is_manager`, `is_user`, `newly_hired` |
| Employee-category rel | Implicit | Explicit with color randomization |
| Work location | Not a separate model | `hr.work.location` with address and type |
| Coach field | Manual | Auto-synced from `parent_id` |

---

## Performance Considerations

1. **`current_version_id` recompute**: `_compute_current_version_id()` runs a `search()` + `order` on every employee. The `_cron_update_current_version_id()` exists to batch this daily. Consider adding an indexed DB trigger for high-volume deployments.

2. **`_inherits` JOIN overhead**: Every read of `hr.employee` JOINs `hr_version`. The `current_version_id` is stored to minimize this, but computed fields on `hr.version` that aren't stored still require the join.

3. **`hr_employee_public` view**: Every query on this model is a JOIN between `hr_employee` and `hr_version`. The `current_version_id` FK should have an index (it does as a stored Many2one).

4. **Trigram index on `hr.job.name`**: Enables fast `ilike` searches for job position autocomplete even in databases with thousands of jobs.

5. **`_parent_store` on `hr.department`**: Stores `parent_path` as a materialized path, enabling efficient `child_of`/`parent_of` domain operators without recursive CTEs.

6. **`_get_employee_working_now()` batch optimization**: Groups employees by timezone first, then by calendar, minimizing the number of `_work_intervals_batch` calls.

---

## Demo Data and Scenarios

The module loads demo data from `data/hr_demo.xml` and supports scenario loading:
- `_load_demo_data()` checks for `hr.dep_rd` reference; if missing, loads the full `hr_scenario.xml` from `data/scenarios/`
- If `hr_skills` is installed, also loads `hr_skills_scenario.xml`
- Demo tag (`employee_category_demo`) prevents double-loading

---

## Wizard Models

The module includes these wizard models (data files in `wizard/`):
- `hr.departure.wizard` — Collects departure date and reason on archive
- `hr.contract.template.wizard` — Creates employee from contract template
- `hr.bank.account.allocation.wizard` — Manages salary distribution across multiple bank accounts
- `hr.bank.account.allocation.wizard.line` — Line items for the allocation wizard
- `mail.activity.schedule` (from `mail` module) — Activity scheduling on employees

---

## Extension Points

### Adding Versioned Fields
To add a custom field that changes with each contract, add it to `hr.version` instead of `hr.employee`:

```python
# CORRECT
class HrVersion(models.Model):
    _inherit = 'hr.version'
    cost_center_id = fields.Many2one('account.analytic.account')

# The field is now accessible as employee.cost_center_id
# (uses current version's value)
```

### Overriding Presence State
Presence state is computed via `_compute_presence_state()`. To add `hr_attendance` or `hr_holidays` data:

```python
class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _compute_presence_state(self):
        super()._compute_presence_state()
        # Add attendance-based overrides here
        for employee in self:
            if employee.id in attendance_absentees:
                employee.hr_presence_state = 'absent'
```

### Overriding `_get_version()`
Used by `create_version()` to determine which version's data to copy. Override to customize which historical data is carried forward to a new contract period.
