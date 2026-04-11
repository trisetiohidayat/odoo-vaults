# Odoo 18 - hr Module

## Overview

Core Human Resources module. Defines the foundational employee model, departments, job positions, and work locations. This module provides the base HR data structures used by all other HR-related modules.

## Source Path

`~/odoo/odoo18/odoo/addons/hr/`

## Key Models

### hr.employee

The central HR model. Uses `hr.employee.base` mixin for shared fields and inherits from `mail.thread.main.attachment`, `mail.activity.mixin`, `resource.mixin`, and `avatar.mixin`.

**Key Fields:**
- `name`: Related to `resource_id.name` (stored, editable)
- `user_id`: Linked `res.users` record
- `resource_id`: Underlying `resource.resource` for scheduling/calendar
- `department_id`: Many2one to `hr.department`
- `job_id`: Many2one to `hr.job`
- `company_id`: Required company assignment
- `resource_calendar_id`: Working schedule (nullable)
- `work_contact_id`: Partner for work communications
- `work_phone`, `mobile_phone`, `work_email`: Contact details
- `employee_type`: Selection: `employee`, `worker`, `student`, `trainee`, `contractor`, `freelance`
- `parent_id`: Manager (computed from department)
- `coach_id`: Coach (computed from manager, or manual)
- `child_ids`: Direct subordinates (one2many)
- `category_ids`: Tags via `hr.employee.category`
- `pin`, `barcode`: Badge/PIN for attendance kiosk
- `departure_reason_id`, `departure_date`, `departure_description`: Archive handling
- `country_id`: Nationality
- `gender`: male/female/other
- `marital`: marital status with localized selection
- `birthday`: Date of birth
- `ssnid`, `sinid`, `identification_id`, `passport_id`: ID numbers
- `bank_account_id`: Payroll bank account
- `permit_no`, `visa_no`, `visa_expire`, `work_permit_expiration_date`: Work authorization
- `driving_license`, `id_card`: Document attachments
- `km_home_work`: Commute distance (computed from `distance_home_work`)
- `emergency_contact`, `emergency_phone`: Emergency contact info
- `private_*`: Private address fields (HR user only)
- `children`: Number of dependent children

**Computed Fields:**
- `km_home_work`: Converts miles/kilometers based on `distance_home_work_unit`
- `work_permit_name`: Generates filename-safe permit name
- `related_partners_count`: Count of linked partner records
- `is_flexible` / `is_fully_flexible`: From resource calendar

**Key Methods:**
- `_compute_km_home_work()` / `_inverse_km_home_work()`: Bidirectional distance conversion
- `_employee_attendance_intervals()`: Get attendance intervals (considers lunch if not flexible)
- `_get_expected_attendances()`: Work intervals for a date range
- `_get_calendar_attendances()`: Work duration data between dates
- `_get_unusual_days()`: Public holidays from calendar
- `_get_age()`: Calculate employee age
- `_get_tz()` / `_get_tz_batch()`: Resolve timezone priority
- `_cron_check_work_permit_validity()`: Schedule activities for expiring permits

**Access Control (L3):**
- Most sensitive fields (private_*, SSN, salary) have `groups="hr.group_hr_user"`
- Public model `hr.employee.public` provides read-only access to non-HR users
- `_check_private_fields()` raises `AccessError` if private fields accessed on public model
- `_search()` routes to `hr.employee.public` for non-HR users

**Critical Behaviors:**
- `create()`: Syncs user data, creates work contacts, subscribes to department channels, launches onboarding plans
- `write()`: Syncs work_contact_id, updates department channels
- `toggle_active()`: Archives employee, triggers departure wizard, empties manager/coach links
- `unlink()`: Also deletes associated `resource.resource`
- `action_create_user()`: Opens user creation wizard with employee data

**Private Field Access (L3):**
- Non-HR users see `hr.employee.public` view
- `search_fetch()` / `fetch()` implement fallback to public model
- `get_view()` / `get_views()` route based on access rights

---

### hr.department

Department hierarchy with mail tracking.

**Key Fields:**
- `name`: Department name (required, translated)
- `complete_name`: Computed recursive name (e.g., "Company / Engineering / Backend")
- `parent_id`: Parent department (nullable for root)
- `master_department_id`: Root department via `parent_path`
- `manager_id`: Department head (Many2one to `hr.employee`)
- `member_ids`: One2many to employees in department
- `total_employee`: Computed count via `_read_group`
- `child_ids`: Child departments
- `parent_path`: Materialized path for hierarchy queries
- `company_id`: Company assignment
- `jobs_ids`: Jobs in this department
- `plan_ids`: Activity plans for department
- `plans_count`: Computed plan count

**Key Methods:**
- `_compute_complete_name()`: Recursive name building
- `_compute_master_department_id()`: Parses `parent_path`
- `_check_parent_id()`: Validates no recursive hierarchy
- `_update_employee_manager()`: Cascades manager changes to subordinate employees
- `write()`: Auto-subscribes new manager to department chatter
- `get_department_hierarchy()`: Returns dict for child departments display

**Access Control (L3):**
- `_search_has_read_access()`: Returns domain based on HR access
- Users without HR access only see departments where they are manager

---

### hr.job

Job positions within departments.

**Key Fields:**
- `name`: Position name (unique per department+company)
- `expected_employees`: Computed: current + planned recruits
- `no_of_employee`: Current employee count
- `no_of_recruitment`: Target headcount
- `department_id`: Associated department
- `contract_type_id`: Default contract type
- `description`: HTML job description
- `requirements`: Plain text requirements
- `employee_ids`: One2many to employees in this position

**Key Methods:**
- `_compute_employees()`: Uses `_read_group` for efficient aggregation

---

### hr.employee.category

Simple tag model for employee categorization.

**Fields:**
- `name`: Tag name
- `color`: Display color
- `employee_ids`: Many2many to `hr.employee`

---

### hr.work.location

Work location definitions.

**Fields:**
- `name`: Location name
- `address_id`: Related company address
- `partner_id`: Contact partner (computed)
- `location_type`: Selection: `home`, `office`, `other`

---

### hr.employee.public

Read-only public view of employee data for non-HR users. Uses delegation inheritance via `_inherits = {'hr.employee': 'employee_id'}` with `_auto=False` (creates SQL VIEW, not table).

**Key Fields (mirrored from hr.employee):**
- `name`, `work_email`, `work_phone`, `mobile_phone`, `address_id`
- `department_id`, `job_id`, `parent_id` (manager), `coach_id`
- `resource_calendar_id`, `company_id`, `employee_type`
- `image_*` / `avatar_*`: Related to `employee_id.image_*` with `compute_sudo=True`

**Computed Fields:**
- `_compute_is_manager()`: Checks if current user is manager of employee (directly or via department chain).

**Critical Behaviors:**
- `init()`: Creates SQL VIEW from hr.employee table columns. All fields are `readonly=True`.
- `_check_private_fields()`: Raises `AccessError` if non-HR user tries to read fields gated by `hr.group_hr_user`.
- `get_view()`: Routes to `hr.employee.public` view for non-HR users, `hr.employee` for HR users.

**Access Routing:**
- `search_fetch()` / `fetch()`: When accessed by non-HR user, routes to `hr.employee.public`.
- `get_views()`: Replaces view IDs with public model equivalents for non-HR users.

---

### hr.employee.base

Abstract base mixin providing shared fields for both `hr.employee` and `hr.employee.public`. Not a standalone model.

**Fields provided:**
- `name`, `user_id`, `resource_id`
- `work_contact_id`, `work_email`, `work_phone`, `mobile_phone`
- `department_id`, `job_id`, `company_id`
- `resource_calendar_id`
- `parent_id` (manager, computed from department)
- `coach_id` (computed from manager)
- `child_ids`, `category_ids`
- `is_flexible` / `is_fully_flexible` (from resource calendar)
- `hr_presence_state` (computed from attendance/calendar)

---

## Cross-Model Relationships

| Model | Relationship | Purpose |
|-------|-------------|---------|
| `hr.employee` | Many2one `resource.resource` | Scheduling, calendar, time tracking |
| `hr.employee` | Many2one `res.partner` (work_contact_id) | Work email/phone source |
| `hr.employee` | Many2one `res.partner` (bank_account_id partner) | Payroll |
| `hr.department` | One2many `hr.employee` (member_ids) | Department membership |
| `hr.job` | One2many `hr.employee` (employee_ids) | Job occupancy |
| `hr.employee` | Many2many `hr.employee.category` | Tags |

## Edge Cases & Failure Modes

1. **Employee without user**: `user_id` nullable. Private fields access routed to `hr.employee.public` which may lack data.

2. **Archived employee**: `toggle_active()` empties `parent_id`, `coach_id`. Archive triggers departure wizard.

3. **Department deletion**: Cannot delete department with members (implicit cascade restrict).

4. **Recursive department**: `_check_parent_id()` raises `ValidationError` on cycle detection.

5. **Work permit expiry**: `_cron_check_work_permit_validity()` schedules activity 1 month before expiry. Requires `work_permit_scheduled_activity=False` trigger.

6. **Multi-company**: Employees scoped to single `company_id`. Department hierarchy independent per company.

7. **Private address fields**: Only visible to `hr.group_hr_user`. API access to `hr.employee.public` silently drops these fields.

8. **Birthday/age**: `_get_age()` returns 0 if birthday not set.

## Security Groups

- `hr.group_hr_user`: Full HR data access
- `base.group_user`: Basic employee record (public fields only)

## Workflow Triggers

- **Employee creation**: Subscribes employee to department discuss channels
- **Employee archive**: Opens departure wizard, empties manager/coach references
- **Department manager change**: Updates subordinate employees' `parent_id`, subscribes new manager
- **Work permit expiry**: Cron schedules activity on employee's manager

## Cron Jobs

- `hr/hr_contract`: `update_state()` - Auto-transitions contracts based on dates
- `hr`: `_cron_check_work_permit_validity()` - Work permit expiry reminder

## Demo Data

- Scenario file: `hr/data/scenarios/hr_scenario.xml` loaded via `_load_scenario()`
