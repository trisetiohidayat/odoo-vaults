---
type: module
module: hr_holidays_attendance
tags: [odoo, odoo19, hr, attendance, overtime]
uuid: 4a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d
created: 2026-04-06
---

# Overtime-Based Leave (hr_holidays_attendance)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Overtime-Based Leave |
| **Technical** | `hr_holidays_attendance` |
| **Category** | Human Resources/Attendance & Time Off |
| **License** | LGPL-3 |
| **Depends** | `hr_holidays`, `hr_attendance_overtime` |
| **Auto-install** | True |
| **Module** | `hr_holidays_attendance` |

## Description

This module bridges the attendance/overtime system with the time-off system, enabling employees to convert overtime hours into paid leave. It allows companies to define which leave types are "overtime-deductible" — meaning employees must have sufficient overtime balance before they can take that type of leave.

The module integrates with three systems:
1. **Attendance/Overtime**: Tracks employee overtime via `hr.attendance.overtime`
2. **Leave Allocation**: Assigns leave entitlements to employees
3. **Leave Requests**: Controls leave approval based on overtime balance

Key capabilities:
- Overtime-to-leave conversion for specific leave types
- Worked hours accrual plans (accrue leave based on hours worked)
- Overtime balance validation on leave approval
- Real-time overtime balance computation
- Time-off with overtime deduction tracking

## Dependencies

```
hr_holidays
hr_attendance_overtime
hr_work_entry
```

- `hr_holidays`: Provides the leave request (`hr.leave`) and leave type (`hr.leave.type`) models
- `hr_attendance_overtime`: Provides the overtime tracking models (`hr.attendance.overtime`, `hr.attendance.overtime.rule`)
- `hr_work_entry`: Provides work entry generation and conflict detection

## Module Structure

```
hr_holidays_attendance/
├── models/
│   ├── hr_leave_type.py           # Leave type with overtime deduction flag
│   ├── hr_leave.py                # Leave validation with overtime check
│   ├── hr_leave_allocation.py      # Allocation with overtime validation
│   ├── hr_attendance_overtime.py   # Compensable as leave flag
│   ├── hr_attendance_overtime_rule.py  # Rule with overtime-to-leave mapping
│   └── hr_leave_accrual_plan_level.py  # Worked hours accrual frequency
├── data/
│   └── hr_holidays_attendance_data.xml  # Demo data for overtime-deductible leave types
└── __manifest__.py
```

## Data Flow

### Overtime-Deductible Leave Request Flow

```
Employee requests leave (e.g., "Overtime Leave")
      │
      ▼
hr.leave._compute_overtime_deductible()
  - Checks if leave type has overtime_deductible=True
  - If yes: queries overtime balance from hr.attendance.overtime
      │
      ▼
Frontend: overtime_deductible flag shown
  - If insufficient overtime: warning message
  - Employee can still submit request
      │
      ▼
Manager approves leave (action_approve())
      │
      ▼
_check_overtime_deductible()
  1. If not overtime-deductible: approve normally
  2. If overtime-deductible:
     a. Compute current overtime balance
     b. Compute overtime needed for leave duration
     c. If balance < required: raise ValidationError
     d. If balance >= required: approve
  3. Record overtime deduction in hr.attendance.overtime
      │
      ├──► Approved:
      │         └── _update_leaves_overtime()
      │              - Deduct overtime from balance
      │              - Creates allocation reduction record
      │
      └──► Rejected (insufficient balance):
               ValidationError("Not enough overtime balance")
```

### Overtime Balance Computation

```
hr.attendance.overtime record per employee
      │
      ├──► compensable_as_leave = True:
      │         └── Overtime hours can be used for leave requests
      │
      └──► compensable_as_leave = False:
                └── Overtime is "banked" but not usable for leave
```

The balance is computed by aggregating overtime hours and subtracting leave consumption.

### Worked Hours Accrual Plan

```
Accrual plan with frequency = "worked_hours"
      │
      ▼
/hr_leave_accrual_plan_level._get_hourly_frequencies()
  - For each hour worked in the period
  - Calculate accrual proportionally
      │
      ▼
Example:
  - Level: 1 day off per 160 hours worked
  - Employee works 40 hours in a week
  - Accrual: 40/160 = 0.25 days added
```

## Key Models

### hr.leave.type (Inherited)

**File:** `models/hr_leave_type.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `overtime_deductible` | Boolean | If True, employee needs overtime balance to use this leave type |
| `overtime_recovery_term` | Integer | Days within which overtime must be used (default: 0 = no expiry) |

#### Key Methods

##### `_compute_display_name()`

Appends the employee's overtime balance to the leave type name in the dropdown.

```python
def _compute_display_name(self):
    # For each leave type, append overtime hours if applicable
    # e.g., "Overtime Leave (12h 30m available)"
    for leave_type in self:
        if leave_type.overtime_deductible:
            balance = leave_type._get_overtime_leave_balance()
            if balance > 0:
                leave_type.display_name = f"{leave_type.name} ({balance}h available)"
```

The displayed name helps employees know their balance before requesting leave.

##### `get_allocation_data()`

Extends the base allocation data to include overtime-related information.

```python
def get_allocation_data(self, employees, date_from):
    # Add overtime balance to allocation data
    allocation_data = super().get_allocation_data(employees, date_from)
    
    for data in allocation_data:
        if data['holiday_status_id'].overtime_deductible:
            data['overtime_balance'] = overtime_balance
    
    return allocation_data
```

### hr.leave (Inherited)

**File:** `models/hr_leave.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `overtime_id` | Many2one | Linked overtime record used for this leave |
| `overtime_hours_used` | Float | Overtime hours consumed by this leave |

#### Key Methods

##### `_compute_overtime_deductible()`

Determines if a leave request is overtime-deductible.

```python
def _compute_overtime_deductible(self):
    for leave in self:
        leave.overtime_deductible = (
            leave.holiday_status_id.overtime_deductible
            and leave.employee_id
            and leave.holiday_status_id.employee_ids
        )
```

This is a computed field that checks the leave type's setting and employee assignment.

##### `_check_overtime_deductible()`

Core validation method called during leave approval. This is the gatekeeper for overtime-deductible leave.

```python
def _check_overtime_deductible(self):
    overtime_deductible_leaves = self.filtered_domain([
        ('overtime_deductible', '=', True),
        ('state', '=', 'confirm'),  # Only pending leaves
    ])
    
    for leave in overtime_deductible_leaves:
        # Compute overtime balance for the employee
        overtime_record = self.env['hr.attendance.overtime'].sudo().search([
            ('employee_id', '=', leave.employee_id.id),
            ('compensable_as_leave', '=', True),
        ])
        
        if not overtime_record:
            raise ValidationError(_(
                "No overtime record found for %s. "
                "Please contact your HR manager."
            ) % leave.employee_id.name)
        
        # Calculate overtime needed
        overtime_needed = leave.number_of_hours_temp
        
        # Check if overtime balance covers the leave duration
        if overtime_record.overtime_hours < overtime_needed:
            raise ValidationError(_(
                "%s does not have enough overtime hours to take this leave. "
                "Required: %sh, Available: %sh"
            ) % (
                leave.employee_id.name,
                overtime_needed,
                overtime_record.overtime_hours,
            ))
        
        # Verify overtime hasn't expired
        if leave.holiday_status_id.overtime_recovery_term > 0:
            overtime_date = leave.request_date_from - timedelta(
                days=leave.holiday_status_id.overtime_recovery_term
            )
            # Only count overtime earned after the cutoff date
            valid_overtime = overtime_record._get_valid_overtime(overtime_date)
            if valid_overtime < overtime_needed:
                raise ValidationError(_(
                    "Not enough recent overtime hours. "
                    "Overtime older than %d days cannot be used."
                ) % leave.holiday_status_id.overtime_recovery_term)
```

**Key validation logic:**
1. Check that an overtime record exists for the employee
2. Check that `compensable_as_leave = True`
3. Compare overtime balance against leave duration (in hours)
4. Optionally enforce an expiry window (`overtime_recovery_term`)

##### `action_approve()`

Approval method extended to include overtime deduction.

```python
def action_approve(self):
    # First: check overtime deduction for eligible leaves
    self._check_overtime_deductible()
    
    # Proceed with normal approval
    res = super().action_approve()
    
    # Post-approval: deduct overtime from balance
    self._update_leaves_overtime()
    
    return res
```

The overtime deduction happens **after** approval. This allows managers to approve first and let the system handle the deduction.

##### `_update_leaves_overtime()`

Deducts overtime from the employee's balance after leave approval.

```python
def _update_leaves_overtime(self):
    overtime_deductible = self.filtered('overtime_deductible')
    
    for leave in overtime_deductible:
        overtime_record = self.env['hr.attendance.overtime'].sudo().search([
            ('employee_id', '=', leave.employee_id.id),
            ('compensable_as_leave', '=', True),
        ])
        
        if overtime_record:
            # Deduct overtime hours
            overtime_record.overtime_hours -= leave.number_of_hours_temp
            
            # Link the overtime record to the leave
            leave.overtime_id = overtime_record.id
            leave.overtime_hours_used = leave.number_of_hours_temp
            
            # Create a log entry for audit trail
            self.env['hr.attendance.overtime.log'].create({
                'overtime_id': overtime_record.id,
                'leave_id': leave.id,
                'hours_deducted': leave.number_of_hours_temp,
                'date': fields.Date.today(),
            })
```

The deduction is recorded as a linked log entry for the audit trail. This allows HR to trace which leaves consumed which overtime hours.

### hr.leave.allocation (Inherited)

**File:** `models/hr_leave_allocation.py`

#### Key Methods

##### `default_get()`

Extends the default values for allocation creation to include overtime-related fields.

```python
def default_get(self, fields):
    res = super().default_get(fields)
    if 'overtime_deductible' in fields:
        # If creating allocation for an overtime-deductible leave type,
        # pre-populate overtime-related fields
        pass
    return res
```

##### `create(vals_list)` / `write(vals)`

Validates that overtime allocation is not granted for overtime-deductible leave types.

```python
def _check_allocation_overtime_constraints(self):
    for allocation in self:
        if allocation.holiday_status_id.overtime_deductible:
            # Overtime-deductible leave types should not have manual allocations
            # (they are managed automatically via overtime conversion)
            if allocation.type == 'regular':
                raise ValidationError(_(
                    "Cannot manually allocate overtime-deductible leave types. "
                    "These leaves are granted by converting overtime hours."
                ))
```

This prevents HR from manually assigning leave days for overtime-deductible types — the only way to earn this leave is by working overtime.

##### `_get_accrual_plan_level_work_entry_prorata()`

Hook for accrual plans to compute work-entry-based accrual.

```python
def _get_accrual_plan_level_work_entry_prorata(self, start, end):
    # Called by accrual plan to compute worked hours in the period
    # Returns number of hours worked for the employee
    return self.employee_id._get_work_hours_in_period(start, end)
```

### hr.attendance.overtime (Inherited)

**File:** `models/hr_attendance_overtime.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `compensable_as_leave` | Boolean | Whether overtime can be converted to leave |

#### Behavior

When `compensable_as_leave = True`, the overtime hours in this record are eligible for conversion to overtime-deductible leave. If `False`, the overtime is "banked" for overtime pay but cannot be used for time off.

### hr.attendance.overtime.rule (Inherited)

**File:** `models/hr_attendance_overtime_rule.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `leave_type_id` | Many2one | Which leave type this overtime converts to |
| `rate_combination_mode` | Selection | How to combine overtime rates |

#### Key Methods

##### `_extra_overtime_vals()`

Adds overtime-to-leave mapping to the overtime computation result.

```python
def _extra_overtime_vals(self, overtime_hours):
    vals = super()._extra_overtime_vals(overtime_hours)
    
    if self.leave_type_id and self.rate_combination_mode == 'multiply':
        # Convert overtime hours to leave days based on rate
        # e.g., 1.5x overtime = 1.5 hours of overtime per hour worked
        vals['compensable_as_leave'] = True
        vals['leave_type_id'] = self.leave_type_id.id
    else:
        vals['compensable_as_leave'] = True  # Or based on configuration
    
    return vals
```

### hr.leave.accrual.plan.level (Extended)

**File:** `models/hr_leave_accrual_plan_level.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `frequency` | Selection | Extended with `worked_hours` option |

**New frequency option:** `worked_hours` — accrual is based on hours actually worked, not calendar time.

#### Key Methods

##### `_check_worked_hours()`

Validates that worked hours frequency is properly configured.

```python
def _check_worked_hours(self):
    if self.frequency == 'worked_hours':
        if not self.hours_multiplier:
            raise ValidationError(_(
                "Hours Multiplier is required for worked_hours accrual frequency."
            ))
```

##### `_get_hourly_frequencies()`

Computes the accrual rate based on hours worked.

```python
def _get_hourly_frequencies(self, start, end,强大的_leaves_taken):
    """
    For worked_hours frequency, accrual is proportional to hours worked.
    Example:
      - Employee works 160 hours in a month
      - Accrual plan: 1 day per 160 hours worked
      - Result: 1 day accrued for the month
    """
    employee = self.leave_allocation_id.employee_id
    worked_hours = employee._get_worked_hours_in_period(start, end)
    
    # Calculate accrual based on worked hours
    hours_per_unit = self.max_leave_increment * self.hours_multiplier
    accrual = worked_hours / hours_per_unit
    
    return [accrual]
```

This enables leave accrual policies like:
- "1 day off per 160 hours worked"
- "1 hour of leave per 8 hours of overtime"
- "1.5 days per 120 hours worked"

## Architecture Notes

### Overtime Balance Calculation

The overtime balance is stored in `hr.attendance.overtime.overtime_hours`. The balance is updated by:
1. **Attendance system**: When employees work beyond their schedule, overtime hours are accumulated
2. **Leave requests**: When overtime-deductible leaves are approved, hours are deducted
3. **Manual adjustments**: HR can manually adjust overtime records

```
Overtime Balance = Accumulated Overtime Hours - Overtime Hours Used for Leave
```

### Overtime-to-Leave Conversion Rules

Different companies have different conversion rules. The module supports:

| Rule | Description | Configuration |
|------|-------------|---------------|
| 1:1 Conversion | 1 hour overtime = 1 hour leave | `rate_combination_mode = 'add'` |
| Multiplied Conversion | 1 overtime hour (1.5x) = 1.5h leave | `rate_combination_mode = 'multiply'` |
| Fixed Ratio | Configurable ratio (e.g., 2 overtime = 1 leave day) | `leave_type_id.overtime_conversion_ratio` |

### Leave Duration vs. Calendar Days

Overtime is measured in **hours**, but leave requests have both:
- `number_of_days_temp`: Leave duration in working days
- `number_of_hours_temp`: Leave duration in hours

The conversion uses `number_of_hours_temp` to ensure accurate overtime deduction.

### Work Entry Integration

When overtime-deductible leaves are approved, they integrate with the work entry system:

```
Leave Approved
      │
      ▼
hr_work_entry_holidays creates work entries for the leave period
      │
      ▼
Work entry has `leave_id` linking back to the leave
      │
      ▼
Leave Type -> Work Entry Type mapping
      │
      ▼
Payroll processes work entries (leave = no pay, but overtime was consumed)
```

The key insight is that overtime-deductible leaves **consume overtime** but still generate work entries that tell payroll "this employee was on leave" — without double-counting as overtime pay + leave pay.

### Accrual Plan: Worked Hours Frequency

This is a powerful feature for companies that want leave to accrue based on actual work performed, not calendar time:

```
Traditional accrual: 1 day/month (regardless of attendance)
Worked hours accrual: 1 day/160 hours worked (proportional)
```

This is especially useful for:
- Part-time employees who work variable hours
- Companies with seasonal work patterns
- Leave that should only accrue when the employee is actively working

## Configuration

### Setting Up Overtime-Deductible Leave Types

1. Go to **Employees > Configuration > Leave Types**
2. Create or edit a leave type (e.g., "Overtime Leave")
3. Enable **Overtime Deductible**
4. Optionally set **Overtime Recovery Term** (days before unused overtime expires)
5. Assign the leave type to relevant employees

### Configuring Overtime-to-Leave Conversion

1. Go to **Employees > Configuration > Overtime Rules**
2. Create or edit an overtime rule
3. Set **Leave Type**: Which leave type this overtime converts to
4. Set **Rate Combination Mode**: How to handle overtime rate multipliers
5. Enable **Compensable as Leave**

### Worked Hours Accrual Plan

1. Go to **Employees > Configuration > Leave Accrual Plans**
2. Create a new accrual plan
3. Add a level with **Frequency = Worked Hours**
4. Set **Hours Multiplier**: How many worked hours per unit of leave
   - Example: 160 hours per 1 day of leave

## Security Analysis

### Record Rules

- Employees can view their own overtime balance
- Managers can view and adjust overtime for their team
- HR Officer can manage all overtime records
- Only HR Manager can create overtime-deductible leave type allocations

### Field Groups

| Field | Groups |
|-------|--------|
| `overtime_deductible` | `hr_holidays.group_hr_holidays_manager` |
| `compensable_as_leave` | `hr_attendance.group_hr_attendance` |
| `overtime_hours` | `hr_attendance.group_hr_attendance` |

### Best Practices

1. **Clear communication**: Employees should understand how overtime converts to leave
2. **Fair conversion rates**: Ensure conversion rates are documented and applied consistently
3. **Audit trail**: The log entries in `hr.attendance.overtime.log` provide an audit trail
4. **Policy enforcement**: Use `overtime_recovery_term` to prevent indefinite accumulation

## Related

- [Modules/hr_holidays](Modules/hr_holidays.md) — Leave management
- [Modules/hr_attendance](Modules/hr_attendance.md) — Attendance tracking
- [Modules/hr_work_entry](Modules/hr_work_entry.md) — Work entry system
- [Modules/hr_work_entry_holidays](Modules/hr_work_entry_holidays.md) — Leave and work entry integration
- [Modules/hr_attendance_overtime](hr_attendance_overtime.md) — Overtime tracking
