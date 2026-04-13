---
Module: hr_fleet
Version: Odoo 18
Type: Integration
Tags: #hr, #fleet, #integration, #company-cars, #hr-fleet
---

# hr_fleet — Fleet HR Integration

## Overview

**Module:** `hr_fleet`
**Category:** Human Resources / Fleet
**Depends:** `hr`, `fleet`
**Auto-installs:** Yes (`auto_install: True`)
**License:** LGPL-3
**Canonical path:** `~/odoo/odoo18/odoo/addons/hr_fleet/`

`hr_fleet` bridges the **Fleet** and **HR** apps, linking company vehicles to employees. It extends `fleet.vehicle` with employee-awareness fields, extends `hr.employee` with car counts and plates, and wires `fleet.vehicle.assignation.log` to the employee driver record. The integration allows HR managers to see employee car history, auto-syncs partner contacts on vehicle drivers, and drives mail activity plans with fleet managers.

---

## Model Map

| Extended Model | File | Key Addition |
|---|---|---|
| `fleet.vehicle` | `fleet_vehicle.py` | `driver_employee_id`, `future_driver_employee_id`, `mobility_card` |
| `fleet.vehicle.assignation.log` | `fleet_vehicle_assignation_log.py` | `driver_employee_id` |
| `fleet.vehicle.odometer` | `fleet_vehicle_odometer.py` | `driver_employee_id` (related) |
| `fleet.vehicle.log.contract` | `fleet_vehicle_log_contract.py` | `purchaser_employee_id` (related) |
| `fleet.vehicle.log.services` | `fleet_vehicle_log_services.py` | `purchaser_employee_id` |
| `hr.employee` | `employee.py` | `car_ids`, `employee_cars_count`, `license_plate`, `mobility_card` |
| `hr.employee.public` | `employee.py` | `mobility_card` (readonly) |
| `mail.activity.plan.template` | `mail_activity_plan_template.py` | `fleet_manager` responsible type |
| `res.users` | `res_users.py` | `employee_cars_count` (related) |

---

## `fleet.vehicle` — EXTENDED

Inherited from `fleet.fleet`. See also: [Modules/Fleet](Modules/Fleet.md).

### Fields

| Field | Type | Notes |
|---|---|---|
| `driver_employee_id` | `Many2one(hr.employee)` | Computed from `driver_id` via `work_contact_id`. Tracked. Domain restricts to same company as vehicle. |
| `driver_employee_name` | `Char` (related) | Alias for `driver_employee_id.name` |
| `future_driver_employee_id` | `Many2one(hr.employee)` | Computed from `future_driver_id` via `work_contact_id`. Tracked. |
| `mobility_card` | `Char` | Computed (`store=True`) from the current driver's `employee_id.mobility_card`. Derives the card number from whoever is the active driver. |

### Key Methods

#### `_compute_driver_employee_id()`
```python
@api.depends('driver_id')
def _compute_driver_employee_id(self):
    employees_by_partner_id_and_company_id = self.env['hr.employee']._read_group(
        domain=[('work_contact_id', 'in', self.driver_id.ids)],
        groupby=['work_contact_id', 'company_id'],
        aggregates=['id:recordset']
    )
    employees_by_partner_id_and_company_id = {
        (partner, company): employee
        for partner, company, employee in employees_by_partner_id_and_company_id
    }
    for vehicle in self:
        employees = employees_by_partner_id_and_company_id.get(
            (vehicle.driver_id, vehicle.company_id)
        )
        vehicle.driver_employee_id = employees[0] if employees else False
```

The link is **dual-keyed**: `(driver_id, company_id)`. This allows the same partner to be linked to different employees in different companies. If the partner maps to multiple employees in the same company, no employee is set (expects exactly one match).

#### `_compute_mobility_card()`
```python
@api.depends('driver_id')
def _compute_mobility_card(self):
    for vehicle in self:
        employee = self.env['hr.employee']
        if vehicle.driver_id:
            employee = employee.search(
                [('work_contact_id', '=', vehicle.driver_id.id)], limit=1
            )
            if not employee:
                employee = employee.search(
                    [('user_id.partner_id', '=', vehicle.driver_id.id)], limit=1
                )
        vehicle.mobility_card = employee.mobility_card
```

Falls back to searching by `user_id.partner_id` if `work_contact_id` is not set. This covers cases where the partner record on the employee is stored through the user account.

#### `_update_create_write_vals(vals)` — critical bidirectional sync
This is the heart of the integration. It is called in both `create()` and `write()`.

**When `driver_employee_id` is set directly:**
```
driver_employee_id → work_contact_id → driver_id
```
The employee's `work_contact_id` is written to `driver_id`.

**When `driver_id` is set directly:**
```
driver_id → work_contact_id match → driver_employee_id (if exactly 1 employee found)
```
The reverse mapping is applied only when exactly one employee in the system has that partner as `work_contact_id`. If multiple matches exist, `driver_employee_id` is cleared (ambiguous).

The same logic applies for `future_driver_employee_id` / `future_driver_id`.

#### `write()` — partner unsubscribe on driver change
```python
def write(self, vals):
    self._update_create_write_vals(vals)
    if 'driver_employee_id' in vals:
        for vehicle in self:
            if vehicle.driver_employee_id and vehicle.driver_employee_id.id != vals['driver_employee_id']:
                partners_to_unsubscribe = vehicle.driver_id.ids
                employee = vehicle.driver_employee_id
                if employee and employee.user_id.partner_id:
                    partners_to_unsubscribe.append(employee.user_id.partner_id.id)
                vehicle.message_unsubscribe(partner_ids=partners_to_unsubscribe)
    return super().write(vals)
```
When the employee driver changes, the old driver (partner) and the old employee's user-partner are both unsubscribed from fleet chatter messages.

#### `action_open_employee()`
Opens the form view of `driver_employee_id`.

#### `open_assignation_logs()`
Overrides the parent action to open assignation logs in **list view** (vs. default kanban).

---

## `hr.employee` — EXTENDED

Inherited from `hr.employee`. See also: [Modules/HR](Modules/HR.md).

### Fields

| Field | Type | Notes |
|---|---|---|
| `employee_cars_count` | `Integer` (computed) | Count of `fleet.vehicle.assignation.log` records where employee is the driver. Grouped by both `driver_employee_id` and `driver_id` (partner). Requires `fleet_group_manager`. |
| `car_ids` | `One2many(fleet.vehicle, driver_employee_id)` | All vehicles where this employee is the `driver_employee_id`. Label shows as "Vehicles (private)". Requires `fleet_group_manager` or `hr_group_hr_user`. |
| `license_plate` | `Char` (computed, searchable) | Concatenation of all `car_ids.license_plate` plus the employee's `private_car_plate` field. Computed, not stored. Searchable via `_search_license_plate`. |
| `mobility_card` | `Char` | Standard employee field (read through to vehicles). Requires `fleet_fleet_user`. |

### Key Methods

#### `_compute_employee_cars_count()`
```python
def _compute_employee_cars_count(self):
    rg = self.env['fleet.vehicle.assignation.log']._read_group([
        ('driver_employee_id', 'in', self.ids),
        ('driver_id', 'in', self.work_contact_id.ids),
    ], ['driver_employee_id'], ['__count'])
    cars_count = {driver_employee.id: count for driver_employee, count in rg}
    for employee in self:
        employee.employee_cars_count = cars_count.get(employee.id, 0)
```
Note: The groupby matches on **both** `driver_employee_id` and `driver_id` (via `work_contact_id`). This is a broader count than simply grouping by `driver_employee_id`.

#### `action_open_employee_cars()`
Opens the assignation log list filtered to this employee:
```python
domain: [("driver_employee_id", "in", self.ids), ("driver_id", "in", self.work_contact_id.ids)]
context: {default_driver_id: self.user_id.partner_id.id, default_driver_employee_id: self.id}
```
The dual-domain means it shows all historical cars for this employee regardless of whether the vehicle record stores the employee or the partner directly.

### Constraints

#### `_check_work_contact_id()`
```python
@api.constrains('work_contact_id')
def _check_work_contact_id(self):
    no_address = self.filtered(lambda r: not r.work_contact_id)
    car_ids = self.env['fleet.vehicle'].sudo().search([
        ('driver_employee_id', 'in', no_address.ids),
    ])
    if car_ids:
        raise ValidationError(_('Cannot remove address from employees with linked cars.'))
```
Prevents clearing `work_contact_id` on any employee who is currently assigned as `driver_employee_id` on a vehicle. This protects the fleet→employee link from accidental data loss.

### `write()` — sync partner changes to vehicles

```python
def write(self, vals):
    res = super().write(vals)
    if 'work_contact_id' in vals:
        car_ids = self.env['fleet.vehicle'].sudo().search([
            '|',
                ('driver_employee_id', 'in', self.ids),
                ('future_driver_employee_id', 'in', self.ids),
        ])
        if car_ids:
            car_ids.filtered(lambda c: c.driver_employee_id.id in self.ids).write({
                'driver_id': vals['work_contact_id'],
            })
            car_ids.filtered(lambda c: c.future_driver_employee_id.id in self.ids).write({
                'future_driver_id': vals['work_contact_id'],
            })
    if 'mobility_card' in vals:
        car_ids = self.env['fleet.vehicle'].sudo().search([('driver_employee_id', 'in', self.ids)])
        car_ids._compute_mobility_card()
    return res
```

When an employee's `work_contact_id` changes:
1. All vehicles where this employee is the **current** driver get their `driver_id` updated to the new partner.
2. All vehicles where this employee is the **future** driver get their `future_driver_id` updated.
3. When `mobility_card` changes on the employee, all vehicles with this employee as driver recompute their `mobility_card` field.

This ensures the `work_contact_id` <-> `driver_id` <-> `driver_employee_id` triangle stays consistent.

---

## `fleet.vehicle.assignation.log` — EXTENDED

Inherited from `fleet.vehicle.assignation.log` (base Fleet). Tracks when vehicles are assigned to drivers.

### Fields

| Field | Type | Notes |
|---|---|---|
| `driver_employee_id` | `Many2one(hr.employee)` | Computed from `driver_id` via `work_contact_id` (same dual-key pattern as `fleet.vehicle`). `store=True, readonly=False` so it can be overridden manually. |
| `attachment_number` | `Integer` (computed) | Count of `ir.attachment` records linked to this log entry. |

### Key Methods

#### `_compute_driver_employee_id()`
Same dual-key `(driver_id, vehicle_id.company_id)` lookup as the vehicle model.

#### `action_get_attachment_view()`
Opens the attachment kanban view filtered to this log entry.

---

## `fleet.vehicle.odometer` — EXTENDED

| Field | Type | Notes |
|---|---|---|
| `driver_employee_id` | `Many2one(hr.employee)` | Related field: `vehicle_id.driver_employee_id`. Readonly. |

## `fleet.vehicle.log.contract` — EXTENDED

| Field | Type | Notes |
|---|---|---|
| `purchaser_employee_id` | `Many2one(hr.employee)` | Related: `vehicle_id.driver_employee_id`. |

#### `action_open_employee()`
Opens the employee form of `purchaser_employee_id`.

## `fleet.vehicle.log.services` — EXTENDED

| Field | Type | Notes |
|---|---|---|
| `purchaser_employee_id` | `Many2one(hr.employee)` | Compute+store. Auto-populated from `vehicle_id.driver_employee_id`. |

#### `_compute_purchaser_employee_id()`
Sets `purchaser_employee_id` from the vehicle's current driver employee.

#### `_compute_purchaser_id()`
When `purchaser_employee_id` is set, overrides `purchaser_id` (the partner) to be the employee's `work_contact_id`. This ensures service records show the correct contact person.

---

## `mail.activity.plan.template` — EXTENDED

### New Selection Value

`responsible_type` gains a new value:
```
fleet_manager → "Fleet Manager"
```

### Constraint: `_check_responsible_hr_fleet()`
Raises `ValidationError` if `responsible_type == 'fleet_manager'` is used on any model other than `hr.employee`.

### `_determine_responsible()`
When the plan template is applied to an `hr.employee` with `responsible_type == 'fleet_manager'`:
1. Gets the first vehicle from `employee_id.car_ids[:1]`.
2. If no vehicle: returns error.
3. If vehicle has no `manager_id`: returns error.
4. Returns `vehicle.manager_id` as the responsible user.

This allows HR managers to attach onboarding/rotation activity plans to employees and have the fleet manager auto-assigned.

---

## `res.users` — EXTENDED

| Field | Type | Notes |
|---|---|---|
| `employee_cars_count` | `Integer` (related) | Related to `employee_id.employee_cars_count`. In `SELF_READABLE_FIELDS`. |

`action_open_employee_cars()` delegates to `self.employee_id.action_open_employee_cars()`.

---

## L4: How Fleet Integrates with HR for Company Car Management

### The Core Data Model Triangle

```
hr.employee.work_contact_id (res.partner)
        ↕ (bidirectional sync via _update_create_write_vals / write hooks)
fleet.vehicle.driver_id (res.partner)   ←→   fleet.vehicle.driver_employee_id (hr.employee)
```

**Synchronization rules:**
1. Setting `driver_employee_id` on a vehicle → auto-sets `driver_id` to the employee's `work_contact_id`.
2. Setting `driver_id` on a vehicle → auto-computes `driver_employee_id` if exactly one employee matches that partner as `work_contact_id` in the same company.
3. Changing `work_contact_id` on an employee → auto-updates both `driver_id` and `future_driver_id` on all vehicles where this employee is the current or future driver.
4. Cannot remove `work_contact_id` from an employee who has cars assigned.

### Assignation Log — The Assignment History

The `fleet.vehicle.assignation.log` model (from base Fleet, extended here) records vehicle handovers. The `hr_fleet` extension links each log entry to an `hr.employee` via `driver_employee_id`. The employee kanban/list view shows all cars ever assigned via `action_open_employee_cars()`, which queries by both `driver_employee_id` and `driver_id` (partner) — so historical records are found even if the vehicle's employee link was later cleared.

### Mobility Card Derivation

When `hr_fleet` is installed, the `mobility_card` field on `fleet.vehicle` is computed from the **currently assigned driver's** `hr.employee.mobility_card`. This means:
- As employees are reassigned between cars, each car automatically picks up the new driver's card.
- When a driver leaves the company (and `work_contact_id` is cleared), cars they drove lose their `mobility_card` value.

### Integration Points

| Feature | How it Works |
|---|---|
| **Vehicle assignment** | Employee → vehicle via `driver_employee_id` / `car_ids` O2M |
| **Contract/Service records** | Auto-link to employee driver via `purchaser_employee_id` |
| **Odometer tracking** | Odometer records get `driver_employee_id` for HR reporting |
| **Mail activities** | Fleet Manager can be assigned as activity responsible for employee plans |
| **Departure wizard** | `hr_fleet` data includes `wizard/hr_departure_wizard_views.xml` — handles car return when employee departs |
| **Company multi-tenancy** | All employee lookups are scoped by `company_id` via the `_read_group` dual-key pattern |

### Security

- `car_ids` on `hr.employee`: requires `fleet.fleet_group_manager` or `hr.group_hr_user`
- `employee_cars_count`: requires `fleet.fleet_group_manager`
- `license_plate` search: requires `hr.group_hr_user`
- `mobility_card` on employee: requires `fleet.fleet_group_user`
- Assignation log access: inherits fleet permissions
