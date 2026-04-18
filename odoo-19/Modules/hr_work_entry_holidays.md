---
type: module
module: hr_work_entry_holidays
tags: [odoo, odoo19, hr, leave, work-entry]
uuid: 3a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
created: 2026-04-06
---

# Time Off in Payslips (hr_work_entry_holidays)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Time Off in Payslips |
| **Technical** | `hr_work_entry_holidays` |
| **Category** | Human Resources/Payroll |
| **License** | LGPL-3 |
| **Depends** | `hr_holidays`, `hr_work_entry` |
| **Auto-install** | True |
| **Module** | `hr_work_entry_holidays` |

## Description

This module integrates the leave management system (`hr_holidays`) with the work entry system (`hr_work_entry`), ensuring that approved leaves appear correctly in employee payslips. When a leave is validated, the module automatically creates corresponding work entries (representing the employee's working time) so that payroll can correctly account for leave days.

The core problem this module solves: **Payroll needs to know when an employee was on leave** so it can pay accordingly (or not pay for unearned leave). The work entry system is the bridge between HR leave management and payroll processing.

Key responsibilities:
- Generate work entries for approved leaves
- Detect and resolve conflicts between leave work entries and attendance entries
- Regenerate work entries when leaves are refused or cancelled
- Prevent cancellation of leaves that have already affected payroll
- Handle public holiday override logic for certain leave types

## Dependencies

```
hr_holidays
hr_work_entry
```

- `hr_holidays`: Provides `hr.leave` and `hr.leave.type` models
- `hr_work_entry`: Provides `hr.work.entry` model and conflict detection

## Module Structure

```
hr_work_entry_holidays/
├── models/
│   ├── hr_leave.py           # Leave lifecycle with work entry integration
│   ├── hr_leave_type.py      # Leave type with work entry type mapping
│   └── hr_work_entry.py      # Work entry with leave linking
├── data/
│   └── hr_work_entry_holidays_data.xml  # Demo data: work entry types for leave types
└── __manifest__.py
```

## Data Flow

### Leave Validation → Work Entry Generation

```
Manager validates leave request (action_validate)
      │
      ▼
hr_holidays.action_validate()
      │
      ▼
hr_work_entry_holidays._cancel_work_entry_conflict()
  1. Get leave date range (request_date_from, request_date_to)
      │
      ▼
  2. Generate leave work entries for the leave period
     For each working day in the leave period:
       - Compute: date, duration, work_entry_type_id
       - Create hr.work.entry record
       - Link to leave via leave_id
      │
      ▼
  3. Find overlapping existing work entries
     Search hr.work.entry for records overlapping with:
       - employee_id = leave.employee_id
       - date_from < leave.date_to
       - date_to > leave.date_from
      │
      ▼
  4. Categorize conflicts:
     a) Full overlap: work entry completely inside leave
        -> Archive the attendance entry (unlink)
     b) Partial overlap: work entry extends beyond leave
        -> Unlink the attendance entry
        -> Create new attendance entries for non-leave periods
           (split the work entry into non-leave parts)
      │
      ▼
  5. Return conflict info to leave validation
      │
      ▼
Leave validation completes
      │
      ▼
Payroll processes work entries
  - Leave work entries: "This employee was on leave"
  - Attendance entries: "This employee worked these hours"
```

### Interval-Based Work Entry Generation

```
Leave Period: Jan 6-10, 2025 (Mon-Fri)
      │
      ▼
For each day in period:
  Jan 6: Create work entry (8h, work_entry_type = PTO)
  Jan 7: Create work entry (8h, work_entry_talke = PTO)
  Jan 8: Create work entry (8h, work_entry_type = PTO)
  Jan 9: Create work entry (8h, work_entry_type = PTO)
  Jan 10: Create work entry (8h, work_entry_type = PTO)
      │
      ▼
Total: 5 work entries × 8 hours = 40 hours of PTO
```

### Conflict Detection: Full Overlap

```
Existing attendance entry: Jan 6-10 (the whole week)
Leave request: Jan 6-10 (same week)
      │
      ▼
Attendance entry is fully covered by leave
      │
      ▼
Archive (unlink) the attendance entry
      │
      ▼
Leave work entries take their place
```

### Conflict Detection: Partial Overlap

```
Existing attendance entry: Jan 6-12 (Mon-Sat)
Leave request: Jan 8-10 (Wed-Fri)
      │
      ▼
Attendance entry partially overlaps with leave
      │
      ▼
Unlink the attendance entry
      │
      ▼
Split into non-leave periods:
  - Jan 6-7 (Mon-Tue): Create new attendance entry (16h)
  - Jan 11-12 (Sat-Sun): No entry (weekend)
      │
      ▼
Leave work entries:
  - Jan 8-10 (Wed-Fri): PTO work entries (24h)
```

### Leave Refusal → Work Entry Regeneration

```
Leave refused (action_refuse)
      │
      ▼
For each linked work entry:
  - Archive the leave work entry
      │
      ▼
Recompute attendance for the period
  - Regenerate attendance entries for the original dates
  - This fills the gap left by the refused leave
      │
      ▼
Payroll sees attendance entries (not leave entries)
```

## Key Models

### hr.leave.type (Inherited)

**File:** `models/hr_leave_type.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `work_entry_type_id` | Many2one | Links leave type to a work entry type for payroll |

This field creates the mapping between a leave type and the work entry type that represents it in payroll. For example:
- Leave type "Paid Time Off" → Work entry type "Paid Leave"
- Leave type "Sick Leave" → Work entry type "Sick Leave"
- Leave type "Unpaid Leave" → Work entry type "Unpaid Leave"

### hr.leave (Inherited)

**File:** `models/hr_leave.py`

This is the core model that implements the leave-work entry integration.

#### Key Methods

##### `_cancel_work_entry_conflict()`

The central method that handles work entry creation and conflict resolution when a leave is validated. This is the most important method in the module.

```python
def _cancel_work_entry_conflict(self):
    """
    Called on leave validation (action_validate).
    Creates leave work entries and resolves conflicts with attendance.
    """
    for leave in self:
        employee = leave.employee_id
        leave_dates = leave._get_leave_dates()  # (date_from, date_to)
        
        if not leave_dates:
            continue
        
        date_from, date_to = leave_dates
        
        # Step 1: Generate leave work entries for each day
        leave_work_entries = leave._create_leave_work_entries(
            date_from, date_to, leave.holiday_status_id.work_entry_type_id
        )
        
        # Step 2: Find overlapping attendance work entries
        conflict_domain = [
            ('employee_id', '=', employee.id),
            ('date_stop', '>', date_from),
            ('date_start', '<', date_to),
            ('state', '=', 'draft'),  # Only unvalidated entries
        ]
        conflicting_entries = self.env['hr.work.entry'].search(conflict_domain)
        
        # Step 3: Process each conflict
        for entry in conflicting_entries:
            # Check if leave fully covers the work entry
            if entry.date_start >= date_from and entry.date_stop <= date_to:
                # Full overlap: archive the entry
                entry.active = False
                _logger.info(
                    "Archived conflicting work entry %s (fully covered by leave %s)",
                    entry.id, leave.id
                )
            else:
                # Partial overlap: split the entry
                entry.active = False
                # Create non-leave portions as separate entries
                non_leave_periods = leave._get_non_leave_periods(
                    entry, date_from, date_to
                )
                for period_start, period_stop in non_leave_periods:
                    self.env['hr.work.entry'].create({
                        'employee_id': employee.id,
                        'date_start': period_start,
                        'date_stop': period_stop,
                        'work_entry_type_id': entry.work_entry_type_id.id,
                        'leave_id': False,  # Not a leave entry
                    })
        
        # Step 4: Link leave work entries to this leave
        leave_work_entries.write({'leave_id': leave.id})
        
        # Step 5: Return conflict summary
        yield {
            'leave': leave,
            'work_entries': leave_work_entries,
            'conflicts_resolved': len(conflicting_entries),
        }
```

**Key design decision:** This method uses `active = False` (archive) rather than `unlink()` for conflicting entries. This preserves the audit trail — archived entries can be inspected if needed.

##### `action_refuse()`

Called when a leave is refused. Regenerates work entries for the period.

```python
def action_refuse(self):
    """
    When a leave is refused:
    1. Archive all linked work entries
    2. Regenerate attendance entries for the period
    """
    for leave in self:
        # Archive all leave work entries
        linked_entries = self.env['hr.work.entry'].search([
            ('leave_id', '=', leave.id)
        ])
        linked_entries.write({'active': False})
        
        # Regenerate attendance for the period
        leave._regen_work_entries()
    
    return super().action_refuse()
```

The `_regen_work_entries()` method recreates attendance entries for the leave period, filling the gap left by the refused leave.

##### `_action_user_cancel()`

Called when an employee cancels their own leave request.

```python
def _action_user_cancel(self):
    """
    When an employee cancels a leave (before approval):
    1. Archive any already-created work entries
    2. Regenerate attendance if needed
    """
    for leave in self:
        linked_entries = self.env['hr.work.entry'].search([
            ('leave_id', '=', leave.id)
        ])
        linked_entries.write({'active': False})
        
        if leave.state == 'validate':  # Was already approved
            leave._regen_work_entries()
    
    return super()._action_user_cancel()
```

Note: Employees can only cancel leaves they initiated. Cancelling an approved leave that has already affected payroll requires HR intervention.

##### `_regen_work_entries()`

Regenerates attendance work entries for the leave period. Used after leave refusal or cancellation.

```python
def _regen_work_entries(self):
    """
    Regenerate attendance entries for the period covered by this leave.
    Called after a leave is refused or cancelled.
    """
    for leave in self:
        if not leave.employee_id:
            continue
        
        date_from, date_to = leave._get_leave_dates()
        if not date_from or not date_to:
            continue
        
        # Ask the attendance system to regenerate entries
        # This uses hr_attendance's logic to create attendance records
        # based on the employee's schedule
        self.env['hr.attendance']._regenerate_attendance_between(
            leave.employee_id.id,
            date_from,
            date_to,
        )
        
        _logger.info(
            "Regenerated attendance for %s between %s and %s after leave %s cancellation",
            leave.employee_id.name, date_from, date_to, leave.id
        )
```

##### `_prepare_resource_leave_vals()`

Prepares the data for creating resource leave records (used for resource calendar adjustments).

```python
def _prepare_resource_leave_vals(self):
    """
    Create resource.leave records to block the employee's calendar.
    """
    vals = []
    for leave in self:
        vals.append({
            'resource_id': leave.employee_id.resource_id.id,
            'date_from': leave.date_from,
            'date_to': leave.date_to,
            'time_type': leave.holiday_status_id.time_type,
            'calendar_changed': False,
        })
    return vals
```

##### `_compute_can_cancel()`

Prevents cancellation of leaves that have already been validated into work entries that payroll may have processed.

```python
def _compute_can_cancel(self):
    """
    A leave can be cancelled if:
    1. It's not yet validated (draft/confirm state)
    2. OR it's validated but no work entries exist
    3. OR all linked work entries are still in draft state
    """
    for leave in self:
        if leave.state != 'validate':
            leave.can_cancel = True
            continue
        
        linked_entries = self.env['hr.work.entry'].search([
            ('leave_id', '=', leave.id)
        ])
        
        if not linked_entries:
            leave.can_cancel = True
        elif all(e.state == 'draft' for e in linked_entries):
            # Work entries exist but not yet validated
            leave.can_cancel = True
        else:
            # Work entries have been validated — payroll may have processed them
            leave.can_cancel = False
```

**Business rationale:** Once work entries are validated and potentially exported to payroll, changing them could cause payroll inconsistencies. The system prevents "dangerous" cancellations while allowing safe ones.

##### `_get_leaves_on_public_holiday()`

Determines which leaves should override public holiday deductions.

```python
def _get_leaves_on_public_holiday(self):
    """
    Exclude certain leave types from the public holiday deduction rule.
    
    Some countries deduct public holidays from leave balances.
    But certain leave types (e.g., sick leave, unpaid leave) should NOT
    trigger a public holiday deduction because:
    - The employee was already on leave
    - Deducting both would be double-counting
    
    This method returns leave IDs that should be excluded from
    the public holiday deduction calculation.
    """
    excluded_codes = ['LEAVE110', 'LEAVE210', 'LEAVE280']  # Example codes
    
    excluded = self.filtered_domain([
        ('holiday_status_id.code', 'in', excluded_codes),
        ('state', '=', 'validate'),
    ])
    
    return excluded
```

**Note:** This method is called by the payroll system (via `hr_contract_schedule`) to determine which days should not be deducted from the leave balance as public holidays.

### hr.work.entry (Inherited)

**File:** `models/hr_work_entry.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `leave_id` | Many2one | Link to the leave that generated this work entry |
| `leave_state` | Char | State of the leave at time of work entry creation |

#### Key Methods

##### `write(vals)`

Extends work entry write to handle leave refusal cascading.

```python
def write(self, vals):
    """
    When a work entry is refused (state -> cancelled):
    Check if it has a linked leave that should be refused too.
    """
    res = super().write(vals)
    
    # If entries are being cancelled, check for linked leaves
    if 'state' in vals and vals['state'] == 'cancelled':
        for entry in self.filtered('leave_id'):
            # Optionally trigger leave refusal workflow
            # entry.leave_id.action_refuse()
            pass
    
    return res
```

##### `_reset_conflicting_state()`

When work entries change, this resets conflicting states.

```python
def _reset_conflicting_state(self, employee, date_from, date_to):
    """
    Reset conflicting attendance/leave states when work entries change.
    Called after attendance entries are created or modified.
    """
    # Find any leave work entries that conflict with new attendance
    conflicting_leaves = self.env['hr.leave'].search([
        ('employee_id', '=', employee.id),
        ('state', '=', 'validate'),
        ('date_from', '<=', date_to),
        ('date_to', '>=', date_from),
    ])
    
    # For each conflicting leave, re-run conflict detection
    for leave in conflicting_leaves:
        leave._cancel_work_entry_conflict()
```

##### `_get_leaves_duration_between_two_dates()`

Computes the duration of leaves within a date range, used for payroll calculations.

```python
def _get_leaves_duration_between_two_dates(self, employee, date_from, date_to):
    """
    Calculate total leave duration (in hours) for an employee in a period.
    Used by payroll to compute leave pay.
    """
    leaves = self.env['hr.leave'].search([
        ('employee_id', '=', employee.id),
        ('state', '=', 'validate'),
        ('date_from', '<=', date_to),
        ('date_to', '>=', date_from),
    ])
    
    total_hours = 0.0
    for leave in leaves:
        # Compute overlap between leave and requested period
        overlap_start = max(leave.date_from, date_from)
        overlap_stop = min(leave.date_to, date_to)
        
        if overlap_start < overlap_stop:
            duration = (overlap_stop - overlap_start).total_seconds() / 3600
            total_hours += duration
    
    return total_hours
```

## Post-Init Hook

**File:** `models/hr_leave.py`

```python
def _validate_existing_work_entries():
    """
    Post-init hook: Validates all existing work entries after module installation.
    
    This ensures that any work entries created before this module was installed
    are brought up to date. Called from __init__.py or __post_init__.
    """
    # Find all validated work entries
    entries = self.env['hr.work.entry'].search([
        ('state', '=', 'validated')
    ])
    
    # Re-validate them with the new module's logic
    entries._validate()
```

This hook ensures a clean state after installation by re-validating existing work entries with the module's conflict detection logic.

## Architecture Notes

### Conflict Resolution Strategy

The module uses a **replace and split** strategy for conflicts:

1. **Archive (don't delete)**: Conflicting attendance entries are archived with `active = False` rather than deleted. This preserves the audit trail and allows recovery if needed.
2. **Split partial overlaps**: When a leave partially covers an attendance entry, the attendance entry is split into non-leave portions. This ensures attendance hours are preserved.
3. **Create fresh leave entries**: Leave work entries are always created fresh rather than derived from attendance entries. This prevents data propagation issues.

### Timezone Handling

Leave dates (`date_from`, `date_to`) are stored in UTC but represent local dates. The conflict detection uses a **1-day buffer** to handle timezone edge cases:

```python
conflict_domain = [
    ('date_stop', '>', date_from - timedelta(days=1)),
    ('date_start', '<', date_to + timedelta(days=1)),
]
```

This ensures that timezone boundaries don't cause conflicts to be missed.

### Work Entry Type Mapping

The mapping between leave types and work entry types is configurable:

```
Leave Type "Paid Vacation" -> Work Entry Type "PTO"
Leave Type "Sick Leave" -> Work Entry Type "Sick"
Leave Type "Unpaid Leave" -> Work Entry Type "Unpaid"
```

This mapping allows payroll to handle different leave types differently:
- PTO: Paid (payroll generates pay)
- Sick: May have limits (e.g., sick pay policies)
- Unpaid: No pay, but employee is tracked as absent

### Cascade from Leave to Work Entry

The system maintains a bidirectional link between leaves and work entries:
- Leave → Work Entries: `_cancel_work_entry_conflict()` creates entries with `leave_id`
- Work Entry → Leave: `write()` can trigger leave refusal

This bidirectional link ensures consistency is maintained in both directions.

### Integration with Payroll

The work entry system feeds into payroll in two ways:

1. **Work entry types**: Each work entry has a type that payroll uses to determine pay rules
2. **Leave duration**: Payroll queries leave durations for the pay period

The module ensures that:
- Leave work entries are created when leaves are approved
- Attendance entries are adjusted when leaves conflict
- Cancelled/refused leaves trigger attendance regeneration

## Configuration

### Mapping Leave Types to Work Entry Types

1. Go to **Employees > Configuration > Leave Types**
2. For each leave type, set **Work Entry Type**
3. This determines how the leave appears in payroll

### Conflict Resolution Settings

The module's conflict resolution is automatic but configurable:
- Archive vs. split behavior: Always splits partial overlaps
- Timezone buffer: 1 day before/after for conflict detection
- Work entry state: Always created as `draft` (needs validation)

### Public Holiday Override

Configure which leave types should NOT trigger public holiday deductions:
1. Identify the leave type codes to exclude (e.g., sick leave, unpaid)
2. These are used in `_get_leaves_on_public_holiday()`

## Security Analysis

### Record Rules

| Operation | Who Can Do It |
|-----------|--------------|
| View leave-linked work entries | Employee (own), Manager (team), HR (all) |
| Archive leave work entries | HR Officer, HR Manager |
| Modify leave work entries | HR Officer, HR Manager |
| Cancel validated leaves | HR Manager only (after `_compute_can_cancel()` check) |

### Validation Guards

The `_compute_can_cancel()` method prevents dangerous cancellations:
- Prevents cancelling approved leaves that have validated work entries
- Allows cancelling draft leaves or unvalidated work entries
- HR Manager can override by manually refusing the leave

### Audit Trail

The module maintains several audit trails:
- Work entries with `active = False` (archived, not deleted)
- Work entries linked to leaves via `leave_id`
- Leave state changes
- `_get_leaves_on_public_holiday()` for payroll deduction tracking

## Related

- [Modules/hr_holidays](Modules/hr_holidays.md) — Leave management
- [Modules/hr_work_entry](Modules/hr_work_entry.md) — Work entries
- [Modules/hr_holidays_attendance](Modules/hr_holidays_attendance.md) — Overtime-to-leave conversion
- [Modules/hr_attendance](Modules/hr_attendance.md) — Attendance tracking
