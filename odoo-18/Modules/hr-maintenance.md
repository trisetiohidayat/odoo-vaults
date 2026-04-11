---
Module: hr_maintenance
Version: Odoo 18
Type: Integration
Tags: #hr #maintenance #equipment #integration
Related Modules: hr, maintenance
---

# hr_maintenance — Equipment Maintenance Linked to HR

**Addon Key:** `hr_maintenance`
**Depends:** `hr`, `maintenance`
**Auto-install:** `True`
**Category:** Human Resources
**License:** LGPL-3

## Purpose

`hr_maintenance` bridges the **HR** and **Maintenance** modules, enabling equipment to be tracked as assets assigned to employees or departments. Unlike standalone maintenance (which assigns equipment to users), HR-linked maintenance ties equipment to employee records, enabling equipment lifecycle tracking during employee onboarding and departure.

Key features:
- Equipment can be **assigned to an employee** (or a department), with ownership tracked via `owner_user_id`
- Maintenance **requests** can be created **by** an employee
- When an employee is marked as departed, a departure wizard can **unassign all equipment**
- HR officers automatically receive the `maintenance.group_equipment_manager` rights

---

## Models Extended

### `maintenance.equipment` — Equipment

**Inherited from:** `maintenance.equipment`
**File:** `models/equipment.py`

#### Fields Added

| Field | Type | Notes |
|-------|------|-------|
| `employee_id` | `Many2one(hr.employee)` | Compute-backed; employee responsible for the equipment |
| `department_id` | `Many2one(hr.department)` | Compute-backed; department responsible for equipment |
| `equipment_assign_to` | `Selection([department, employee, other])` | Radio selector; controls which of `employee_id` or `department_id` is active. Default: `employee` |
| `owner_user_id` | `Many2one(res.users)` | Computed from `employee_id` or `department_id`; determines message subscribers and access |
| `assign_date` | `Date` | Compute-backed; date equipment was assigned (set to today when assignment changes) |

#### Compute Methods

**`_compute_owner()`**
```python
@api.depends('employee_id', 'department_id', 'equipment_assign_to')
def _compute_owner(self)
```
Resolves `owner_user_id`:
- `equipment_assign_to = 'employee'`: `owner_user_id = employee_id.user_id`
- `equipment_assign_to = 'department'`: `owner_user_id = department_id.manager_id.user_id`
- `equipment_assign_to = 'other'`: `owner_user_id = self.env.user.id` (no automatic assignment)

**`_compute_equipment_assign()`**
```python
@api.depends('equipment_assign_to')
def _compute_equipment_assign(self)
```
Manages the visibility/reset logic of the assignment fields:
- `employee`: sets `employee_id` to current value, clears `department_id`
- `department`: sets `department_id` to current value, clears `employee_id`
- `other`: keeps both values as-is

Also sets `assign_date = fields.Date.context_today(self)` when assignment changes.

#### Lifecycle Methods

**`create(vals_list)`**
```python
@api.model_create_multi
def create(self, vals_list)
```
On creation, automatically **subscribes** the assignee (employee's user partner or department manager's user partner) to the equipment's mail thread, so they receive notifications about the equipment.

**`write(vals)`**
```python
def write(self, vals)
```
On `employee_id` or `department_id` change, subscribes the new assignee's partner to the mail thread. Old assignees are not unsubscribed.

**`_track_subtype(init_values)`**
```python
def _track_subtype(self, init_values)
```
Returns `maintenance.mt_mat_assign` (equipment assigned) subtype when `employee_id` or `department_id` changes.

#### Domain on Equipment in Maintenance Requests

```python
equipment_id = fields.Many2one(domain="['|',
    ('employee_id', '=', employee_id),
    ('employee_id', '=', False)]")
```

In `maintenance.request`, the equipment dropdown is filtered to show only equipment assigned to the requesting employee (or unassigned equipment). This prevents employees from seeing/accessing other employees' equipment in the maintenance request form.

---

### `maintenance.request` — Maintenance Request

**Inherited from:** `maintenance.request`
**File:** `models/equipment.py`

#### Fields Added

| Field | Type | Notes |
|-------|------|-------|
| `employee_id` | `Many2one(hr.employee)` | Defaults to `self.env.user.employee_id`; tracks who created the request |
| `owner_user_id` | `Many2one(res.users)` | Computed; set to `employee_id.user_id` if equipment is assigned to employee, else False |
| `equipment_id` | `Many2one` (override) | Domain narrowed to equipment belonging to the requesting employee |

#### Compute Methods

**`_compute_owner()`**
```python
@api.depends('employee_id')
def _compute_owner(self)
```
Sets `owner_user_id` to the employee's user only when `equipment_id.equipment_assign_to == 'employee'`. Otherwise, no single owner is determined.

#### Lifecycle Methods

**`create(vals_list)`**
Auto-subscribes the requesting employee's user partner to the maintenance request's mail thread.

**`write(vals)`**
On `employee_id` change, subscribes the new employee's user partner.

**`message_new(msg, custom_values=None)`** (email gateway hook)
```python
@api.model
def message_new(self, msg, custom_values=None)
```
When a maintenance request is created via **email gateway** (incoming email to the maintenance alias), this override extracts the sender's email address, finds the matching `res.users` by login, and sets `employee_id` from `self.env.user.employee_id`. This links the email sender to their employee record.

#### View Extensions (in `views/maintenance_views.xml`)

| View | Change |
|------|--------|
| `maintenance.hr_equipment_request_view_search` | Added `employee_id` field to filter/search; replaced `"My Maintenances"` filter with `employee_id.user_id = uid`; replaced `"Created By"` group_by from `owner_user_id` to `employee_id` |
| `maintenance.hr_equipment_request_view_form` | Replaced `owner_user_id` with `employee_id` (many2one_avatar_employee widget) |
| `maintenance.hr_equipment_request_view_kanban` | Replaced `owner_user_id` span with `employee_id` |
| `maintenance.hr_equipment_request_view_tree` | Replaced `owner_user_id` with `employee_id` |
| `maintenance.hr_equipment_view_search` | Modified filter domains for `assigned`/`available`; added employee/department groupby and fields |
| `maintenance.hr_equipment_view_form` | Replaced `owner_user_id` with radio `equipment_assign_to` + conditional `employee_id`/`department_id` |
| `maintenance.hr_equipment_view_kanban` | Replaced owner display with `employee_id` (with "Unassigned" label fallback) |
| `maintenance.hr_equipment_view_tree` | Replaced `owner_user_id` with `employee_id` and `department_id` columns |

---

### `hr.employee` — Employee

**Inherited from:** `hr.employee`
**File:** `models/res_users.py`

#### Fields Added

| Field | Type | Notes |
|-------|------|-------|
| `equipment_ids` | `One2many(maintenance.equipment, 'employee_id')` | All equipment assigned to this employee |
| `equipment_count` | `Integer` | Computed; count of `equipment_ids` |

#### Compute Methods

**`_compute_equipment_count()`**
```python
@api.depends('equipment_ids')
def _compute_equipment_count(self)
```
Counts `equipment_ids` for each employee.

#### View Extensions (in `views/hr_views.xml`)

- `hr.view_employee_form`: Adds a stat button (in `button_box`) linking to `maintenance.hr_equipment_action` with domain `search_default_employee_id: id`. Shows `equipment_count` as the stat info.
- `hr.res_users_view_form_profile`: Adds the same button to the user's preferences form.

---

### `res.users` — User

**Inherited from:** `res.users`
**File:** `models/res_users.py`

#### Fields Added

| Field | Type | Notes |
|-------|------|-------|
| `equipment_ids` | `One2many(maintenance.equipment, 'owner_user_id')` | All equipment owned by this user (through `maintenance.equipment.owner_user_id`) |
| `equipment_count` | `Integer` | Related to `employee_id.equipment_count` — shows equipment count in user preferences |

#### `SELF_READABLE_FIELDS`

`equipment_count` is added to `SELF_READABLE_FIELDS` so that users can see their own equipment count (but not modify it) without needing elevated permissions.

---

## Wizard: `hr.departure.wizard`

**Inherited from:** `hr.departure.wizard`
**File:** `wizard/hr_departure_wizard.py`

#### Field Added

| Field | Type | Notes |
|-------|------|-------|
| `unassign_equipment` | `Boolean` | Default `True`; shown in the departure wizard form as "Free Equipments" / "Equipment" row |

#### Action

```python
def action_register_departure(self):
    super().action_register_departure()
    if self.unassign_equipment:
        self.employee_id.update({
            'equipment_ids': [Command.unlink(equipment.id)
                               for equipment in self.employee_id.equipment_ids]
        })
```

When an HR officer processes an employee departure, they can check `unassign_equipment` to automatically unlink all equipment from the departing employee. The `Command.unlink` list removes each equipment from the employee's record (sets `employee_id = False` on those equipment records).

---

## Security

**File:** `security/equipment.xml`

```xml
<record id="hr.group_hr_user" model="res.groups">
    <field name="implied_ids" eval="[(4, ref('maintenance.group_equipment_manager'))]"/>
</record>
```

HR officers (`hr.group_hr_user`) are given `maintenance.group_equipment_manager` rights automatically via implied_ids. This means anyone in the HR Officer role can:
- Create/edit maintenance equipment
- Assign equipment to employees/departments
- Process maintenance requests

This is the mechanism that allows HR to manage equipment without explicitly being given `maintenance` rights.

---

## L4 — How This Differs from Standalone Maintenance

| Feature | Standalone `maintenance` | `hr_maintenance` bridge |
|---------|--------------------------|------------------------|
| Equipment assignment | `owner_user_id` set manually | `employee_id` or `department_id` → auto-computes `owner_user_id` |
| Equipment tracking | By user (res.users) | By employee (hr.employee) |
| Request creation | `owner_user_id` or any user | `employee_id` defaults to current user's employee |
| Departure handling | None | `unassign_equipment` in `hr.departure.wizard` clears assignments |
| Employee-view | None | `equipment_ids` on employee form; stat button |
| User-view | None | `equipment_count` stat button in user preferences |
| Domain filtering | None | Equipment dropdown in requests filtered by employee |
| HR rights | Requires `maintenance.group_equipment_manager` | HR officers auto-get it via implied_ids |

**The key difference:** Standalone `maintenance` is user-centric. `hr_maintenance` layers an employee-centric view on top, allowing equipment to be tied to employment records and automatically reassigned or cleared when employees leave.

---

## File Reference

| File | Purpose |
|------|---------|
| `__manifest__.py` | Module declaration; depends on `hr` + `maintenance`; auto_install |
| `models/__init__.py` | Imports `equipment`, `res_users` |
| `models/equipment.py` | `maintenance.equipment` + `maintenance.request` extensions |
| `models/res_users.py` | `hr.employee` + `res.users` extensions |
| `wizard/hr_departure_wizard.py` | `hr.departure.wizard` with `unassign_equipment` |
| `views/maintenance_views.xml` | All equipment + request view overrides |
| `views/hr_views.xml` | Employee + user form stat buttons |
| `views/hr_departure_wizard_views.xml` | Departure wizard extension |
| `security/equipment.xml` | HR officer implied_ids → maintenance rights |