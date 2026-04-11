---
Module: hr_hourly_cost
Version: Odoo 18
Type: Core
Tags: #hr #payroll #timesheet #project
Related Modules: hr, project, hr_timesheet
---

# hr_hourly_cost — Employee Hourly Cost

**Addon Key:** `hr_hourly_cost`
**Depends:** `hr`
**Auto-install:** `False` (no `auto_install` key)
**Category:** Services/Employee Hourly Cost
**License:** LGPL-3

## Purpose

`hr_hourly_cost` adds a single monetary field to `hr.employee` and installs the base infrastructure needed by other modules (like `project`, `hr_timesheet`, `planning`) to fetch an employee's labor cost for timesheet accounting, project profitability, and resource planning.

This is a **pure data field** — no methods, no computed logic. Other modules read `hourly_cost` from `hr.employee` and apply it for billing/payroll calculations.

---

## Models Extended

### `hr.employee` — Employee

**Inherited from:** `hr.employee` (base)
**File:** `models/hr_employee.py`

```python
class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    hourly_cost = fields.Monetary(
        'Hourly Cost',
        currency_field='currency_id',
        groups="hr.group_hr_user",
        default=0.0
    )
```

#### Field Definition

| Attribute | Value | Notes |
|-----------|-------|-------|
| `currency_field` | `'currency_id'` | Inherited from `hr.employee` — employee's company currency |
| `groups` | `"hr.group_hr_user"` | Only HR officers and managers can view/edit. Regular employees cannot see this field |
| `default` | `0.0` | New employees have no default hourly cost |
| `type` | `fields.Monetary` | Uses company currency; accepts negative values |

#### View Extension

Installed in `views/hr_employee_views.xml` — extends `hr.view_employee_form`:

```
application_group (invisible attribute removed)
  → inside application_group:
      label for "hourly_cost"
      div: field "hourly_cost" (class oe_inline)
           field "currency_id" (invisible)
```

The `hourly_cost` field is placed in the **"Application"** section of the employee form, alongside `department_id`, `job_id`, `parent_id` (the `application_group` group was previously hidden; this view makes it visible).

---

## L4 — How Hourly Cost Affects Payroll and Project Costing

### Primary Use Case: Timesheet Cost Accounting

```
timesheet.entry (hr_timesheet)
    → analytic_account_id, employee_id, unit_amount
    → project / task linked via analytic line
```

In `hr_timesheet`, timesheet lines are linked to employees. The `hourly_cost` is read from the employee's record and multiplied by `unit_amount` (hours) to compute the **cost** of a timesheet line for a project.

```
timesheet_cost = employee.hourly_cost * unit_amount
```

This feeds into:
- **Project profitability**: Revenue vs. cost per task/project
- **Cost control reports**: Labor cost vs. billing rate
- **Payroll reconciliation**: Timesheets validated against payroll

### Integration Points

| Module | How it uses `hourly_cost` |
|--------|--------------------------|
| `project` | Reads `employee.hourly_cost` to compute planned labor cost in task planning |
| `hr_timesheet` | Multiplies by `unit_amount` on analytic lines for project cost |
| `planning` | Uses `hourly_cost` to compute planned labor cost for shift scheduling |
| `hr_payroll` | Reads `hourly_cost` as the rate for payslip computation (if configured) |

### Design Notes

- The field defaults to `0.0` — employees with no hourly cost set contribute zero labor cost to projects. This is intentional: it allows the field to be left blank for employees who should not be tracked in projects.
- `groups="hr.group_hr_user"` means the field is **invisible to non-HR users**. Employees themselves cannot see their own hourly cost — this is typical for payroll data. Implement `hr_payroll` to expose cost-to-company figures to HR.
- Currency is tied to the **employee's company** (via `currency_id` inherited from the employee record), ensuring multi-company setups handle currency correctly.
- No `track_visibility` — changes to `hourly_cost` are not logged as mail chatters by default.

---

## Demo Data

The module includes demo data (`data/hr_hourly_cost_demo.xml`) that creates sample employees with pre-populated `hourly_cost` values.

---

## File Reference

| File | Purpose |
|------|---------|
| `__manifest__.py` | Module declaration; depends on `hr`; no auto_install |
| `__init__.py` | Imports `models` |
| `models/__init__.py` | Imports `hr_employee` |
| `models/hr_employee.py` | Single field extension of `hr.employee` |
| `views/hr_employee_views.xml` | Form view extension — makes `application_group` visible and adds `hourly_cost` |
| `data/hr_hourly_cost_demo.xml` | Demo employees with hourly costs |
| `security/` | Directory present but empty in this module — relies on `hr` security |