---
type: flow
title: "Resource Attendance Flow"
primary_model: resource.mixin
trigger: "System — Calendar-based attendance computation / User — Check-in"
cross_module: true
models_touched:
  - resource.resource
  - resource.calendar
  - resource.calendar.attendances
  - resource.calendar.leaves
  - hr.attendance
  - hr.employee
  - hr.payroll.overtime
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/HR/attendance-checkin-flow](flows/hr/attendance-checkin-flow.md)"
  - "[Flows/HR/leave-request-flow](flows/hr/leave-request-flow.md)"
  - "[Flows/HR/employee-creation-flow](flows/hr/employee-creation-flow.md)"
related_guides:
  - "[Business/HR/quickstart-employee-setup](business/hr/quickstart-employee-setup.md)"
source_module: resource
source_path: ~/odoo/odoo19/odoo/addons/resource/
created: 2026-04-07
updated: 2026-04-07
version: "1.0"
---

# Resource Attendance Flow

## Overview

This flow covers two related concerns: (1) the automatic computation of working days, working hours, and leave exclusions based on a `resource.calendar` attached to a `resource.resource` (and by extension, an `hr.employee` via `_inherits`), and (2) the manual check-in/check-out attendance recording via `hr.attendance`. The calendar model drives leave accrual, capacity planning, and payroll computation; the attendance model tracks actual time worked. Both systems share the same `resource.resource` record as their anchor.

## Trigger Point

Two independent triggers:

**Trigger A (Calendar computation):** System-initiated via Odoo's scheduler or any model that calls `resource.resource._get_work_days_data_batch()` (used in project planning, leave request approval, payroll computation). This is passive — the calendar is consulted whenever working-time data is needed.

**Trigger B (Check-in):** User action — employee uses the attendance kiosk, badge scan, or Odoo mobile app to check in via `hr.attendance.attendance_action_change()`. Also triggered by cron for auto-check-out of employees who forgot to check out.

Alternative triggers include:
- **Leave request approval:** `hr.leave._compute_number_of_days()` calls `_adjust_date_for_working_days()` to convert calendar days to working days.
- **Project planning:** `project.allocation.compute_allocations()` calls `_get_work_days_data_batch()` for resource-based scheduling.
- **Payroll batch:** `hr.payslip` cron calls `_get_work_days_data_batch()` to compute worked days for salary computation.
- **Auto check-out cron:** `hr.attendance._cron_check_in_complete()` runs daily to close open attendance records.

---

## Complete Method Chain

```
=== HR.EMPLOYEE CREATION (creates resource.resource via _inherits) ===

1. hr.employee.create({'name': 'John Doe', 'resource_type': 'user', ...})
   └─► 2. _inherits = {'resource.resource': 'resource_id'}  [ORM delegation]
         └─► 3. resource.resource.create({
                'name': 'John Doe',
                'resource_type': 'human',
                'calendar_id': company.resource_calendar_id,  [from company if not set]
                'tz': user.tz or calendar.tz,
                'company_id': values.get('company_id')
              })
              └─► 4. @api.onchange('company_id') → auto-fill calendar_id from company
              └─► 5. @api.onchange('user_id') → auto-fill tz from user

=== RESOURCE.CALENDAR CREATION ===

6. resource.calendar.create({
     'name': 'Standard 40h Week',
     'tz': 'Asia/Jakarta',
     'hours_per_day': 8.0,
     'attendance_ids': [(0,0,{
       'name': 'Monday',
       'dayofweek': '0',
       'hour_from': 8.0,   # 08:00
       'hour_to': 17.0,    # 17:00
       'day_period': 'morning'   # or 'afternoon'
     }), ...]  # Tuesday–Friday same pattern
   })
   └─► 7. resource.calendar.attendances created per line
         └─► 8. @api.constrains('hour_from', 'hour_to') — validates hour_from < hour_to

=== WORKING DAYS COMPUTATION (leave request / payroll) ===

9. hr.leave._compute_number_of_days()
   └─► 10. resource.resource._get_work_days_data_batch(
           self.mapped('employee_id.resource_id'),
           start_date,
           end_date,
           calendar=self.mapped('employee_id.resource_calendar_id'),
         )
         ├─► 11. _adjust_date_for_working_days(start_date, start_date, calendar)
         │      └─► 12. _get_calendar_leaves(start_date, end_date, calendar)
         │            ├─► 13. resource.calendar.leaves.search([
         │            │      ('calendar_id', '=', calendar.id),
         │            │      ('date_from', '<=', end_date),
         │            │      ('date_to', '>=', start_date),
         │            │      ('resource_id', '=', False)  # public/global leave
         │            │    ])
         │            │      └─► 14. ir.holidays.status entries for public holidays
         │            │      └─► 15. (If resource_id set) individual leave records
         │            │
         │            └─► 16. _interval_schedule_get() — subtract leave intervals from work intervals
         │
         └─► 17. For each day in date range:
                ├─► Check dayofweek (0=Mon, 4=Fri)
                ├─► Look up resource.calendar.attendances for that weekday
                ├─► Subtract resource.calendar.leaves (public holidays)
                └─► Sum hours_per_day for working periods

         └─► 18. Returns: {
                  'days': total_working_days (float),
                  'hours': total_working_hours (float),
                  'leaves': {
                    0: {'name': 'New Year', 'hours': 8.0},  # by leave type
                  }
                }

19. hr.leave.write({'number_of_days': computed_days})

=== ATTENDANCE CHECK-IN (user action) ===

20. hr.attendance.attendance_action_change()  [kiosk / badge / mobile]
   ├─► IF no open attendance record:
   │      └─► 21. hr.attendance.create({'employee_id': emp.id, 'check_in': now()})
   │            └─► 22. _compute_worked_hours() — set to 0 initially
   │
   └─► IF open attendance record exists (no check_out):
          └─► 23. attendance.write({'check_out': now()})
                └─► 24. _compute_worked_hours()
                      └─► 25. hours = check_out - check_in
                            └─► 26. Subtract break hours from calendar if configured
                            └─► 27. worked_hours = total_interval_hours - break_hours

=== ATTENDANCE COMPUTATION ===

28. hr.attendance._compute_worked_hours()
   └─► 29. resource.resource._adjust_to_calendar(check_in, check_out)
         ├─► 30. Find matching attendance interval for check_in's weekday
         ├─► 31. Find matching attendance interval for check_out's weekday
         └─► 32. Returns adjusted_start, adjusted_end clipped to calendar hours

33. _action_overtime_validation()  [cron or manual]
   └─► 34. For each attendance record with check_out:
          ├─► 35. IF worked_hours > calendar.hours_per_day:
          │      └─► 36. overtime_hours = worked_hours - hours_per_day
          │      └─► 37. hr.payroll.overtime.create({
          │            'name': 'Overtime',
          │            'employee_id': emp.id,
          │            'date': check_in.date(),
          │            'duration': overtime_hours,
          │            'state': 'draft'
          │          })
          │
          └─► 38. overtime_hours < threshold → skip

=== RESOURCE PLANNING (project capacity) ===

39. project.allocation._compute_resource_allocations()  [or via gantt]
   └─► 40. resource.resource._get_work_days_data_batch()
         ├─► 41. For each resource and date range:
         │      ├─► 42. Sum hours from calendar attendances per working day
         │      ├─► 43. Subtract existing allocations (booked hours)
         │      └─► 44. Returns available capacity per day
         └─► 45. project.gantt updated with capacity data
```

---

## Decision Tree

```
Event occurs: leave request / payroll run / project planning
│
├─► Get employee's resource.resource record
│      └─► Get resource.calendar attached to resource
│
├─► Working days computation:
│  ├─► For each day in date range:
│  │  ├─► Is it a weekday (Mon–Fri)?
│  │  ├─► Is there a matching attendance interval for that dayofweek?
│  │  └─► Is that day excluded by a calendar leave (public holiday)?
│  │     ├─► YES → skip this day
│  │     └─► NO  → count as working day, add hours_per_day
│  └─► Sum all working days → return 'days' and 'hours'
│
├─► Overtime detection (attendance check-out):
│  ├─► Did employee work past end of calendar hours?
│  ├─► IF worked_hours > hours_per_day:
│  │      └─► Create hr.payroll.overtime record
│  └─► ELSE → no overtime
│
└─► Capacity planning (project scheduling):
   ├─► Get total available hours in period
   ├─► Subtract existing bookings/allocations
   └─► Return available capacity
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `resource_resource` | Created | `name`, `resource_type = 'human'`, `calendar_id`, `tz`, `company_id` |
| `resource_calendar` | Created/Referenced | `name`, `hours_per_day = 8.0`, `tz`, `attendance_ids` |
| `resource_calendar_attendance` | Created | `calendar_id`, `dayofweek`, `hour_from`, `hour_to`, `day_period` |
| `resource_calendar_leaves` | Created | `calendar_id`, `resource_id` (optional), `date_from`, `date_to`, `time_type` |
| `hr_attendance` | Created/Updated | `employee_id`, `check_in`, `check_out`, `worked_hours` |
| `hr_payroll_overtime` | Created | `employee_id`, `date`, `duration`, `state = 'draft'` |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Calendar with no attendances | No error; 0 working days returned | `_get_work_days_data_batch()` returns `{'days': 0}` silently |
| Employee without calendar | Falls back to company calendar | `calendar_id` defaults to `company.resource_calendar_id` |
| Invalid hour range (hour_from > hour_to) | `ValidationError` | `@api.constrains('hour_from', 'hour_to')` on `resource.calendar.attendances` |
| Overlapping attendance intervals | Warning or no error | Odoo does not enforce non-overlap — intervals are summed |
| Open attendance record (no check-out) | Left open; auto-checkout cron handles | `attendance_action_change()` returns open record; `_cron_check_in_complete()` closes it |
| Double check-in (two consecutive without check-out) | Error: "Attendance is not closed" | `attendance_action_change()` detects open record |
| Leave request on weekend | 0 days allocated | `_get_work_days_data_batch()` excludes non-working days |
| Timezone mismatch | Working hours shifted | `tz` on `resource.calendar` and `resource.resource` must be consistent |
| Missing tz on user and calendar | `ValidationError` or wrong hours | `create()` on `resource.resource` tries to resolve from user or calendar |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Employee's resource created | `resource.resource` | `_inherits` delegates fields to `hr.employee` view |
| Working hours schedule set | `resource.calendar.attendances` | Defines `hours_per_day = sum(hour_to - hour_from)` |
| Public holidays excluded | `resource.calendar.leaves` | Leaves filtered in `_get_calendar_leaves()` |
| Attendance check-in recorded | `hr_attendance` | `check_in` timestamp set; `worked_hours = 0` initially |
| Worked hours computed | `hr_attendance` | `worked_hours = adjusted_end - adjusted_start - breaks` |
| Overtime detected | `hr_payroll_overtime` | Created when `worked_hours > hours_per_day` |
| Leave days computed | `hr_leave` | `number_of_days` recalculated from calendar data |
| Capacity data available | `project.allocation` | `_get_work_days_data_batch()` feeds into project gantt |
| Company timezone applied | `resource.resource.tz` | Falls back to `company.resource_calendar_id.tz` |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `hr.employee.create()` | Current user | `group_hr_user` or `group_hr_manager` | Also creates `resource.resource` via `_inherits` |
| `resource.calendar.create()` | Current user | `group_resource_calendar` | Usually admin or HR manager |
| `resource.calendar.attendances` write | Current user | `group_resource_calendar` | Calendar-level access |
| `_get_work_days_data_batch()` | `sudo()` | System | Called by payroll, projects — bypasses ACL |
| `hr.attendance.attendance_action_change()` | Current user | `group_hr_user` or own record | Employees can check in/out their own attendance |
| `hr.attendance.create()` | `sudo()` internally | Self-service (own employee) | `_check_in` / `_check_out` field access via sudo |
| `hr.attendance._compute_worked_hours()` | Current user | Read on `resource.calendar` | Uses calendar for break adjustment |
| `_action_overtime_validation()` | Cron (superuser) | `group_hr_manager` | Runs as superuser; creates overtime records |
| `hr.payroll.overtime.create()` | `sudo()` | System | Cron-run overtime computation |
| `hr.leave._compute_number_of_days()` | Current user | Read on `resource.calendar` | Used in leave request form display |

**Key principle:** Attendance check-in is deliberately allowed without `group_hr_user` — employees can record their own attendance via self-service. The `_inherits` delegation means `resource.resource` is always created alongside `hr.employee` even if the user lacks direct `resource.resource` ACL.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside.*

```
Steps 1–5   ✅ INSIDE transaction  — hr.employee + resource.resource created atomically
Steps 6–8   ✅ INSIDE transaction  — calendar + attendances created atomically
Steps 9–18  ✅ INSIDE transaction  — leave days computation; read-only on calendar
Steps 20–27 ✅ INSIDE transaction  — check-in/check-out + worked_hours written
Steps 33–37 ❌ OUTSIDE transaction — via cron scheduler; separate transaction
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| `hr.employee.create()` | ✅ Atomic | Rollback; no orphan `resource.resource` |
| `resource.calendar.create()` | ✅ Atomic | Rollback on constraint violation |
| `_get_work_days_data_batch()` | ✅ Read-only | No write; always within calling transaction |
| `hr.attendance.create()` | ✅ Atomic | Rollback on double-check-in error |
| `_compute_worked_hours()` | ✅ Atomic | Write; rolled back on transaction failure |
| `_action_overtime_validation()` | ❌ Separate cron transaction | Retried by cron; creates new overtime records each run |
| `hr.payroll.overtime.create()` | ❌ Separate cron transaction | Idempotent check prevents duplicates |

**Rule of thumb:** Everything inside `hr.attendance.create()` / `write()` is within the same HTTP request transaction. The overtime cron runs independently — it creates `hr.payroll.overtime` records in a separate database transaction.

---

## Idempotency

> *What happens when this flow is executed multiple times.*

| Scenario | Behavior |
|----------|----------|
| Double-click check-in button | First call creates record; second call detects open record with no check-out, returns error or closes it |
| Re-submit leave request | Leave is re-computed each time `_compute_number_of_days()` is called — no duplicate records created |
| `_action_overtime_validation()` re-run | Checks `if not overtime_id` before creating; idempotent per attendance record |
| `_get_work_days_data_batch()` called twice | Pure read operation — no side effects |
| Calendar attendance updated mid-computation | Computation reads the updated calendar (no locking) — may return different result |
| Auto-checkout cron runs on already-closed attendance | `if not attendance.check_out` guard — skips already closed records |

**Common patterns:**
- **Idempotent:** `_get_work_days_data_batch()` (read-only), `_action_overtime_validation()` (idempotency guard), `attendance_action_change()` (state machine)
- **Non-idempotent:** `hr.employee.create()` (new record), `resource.calendar.create()` (new record), `hr.attendance.create()` (new record)
- **Partially idempotent:** `hr.payroll.overtime.create()` — idempotent within same cron run (check per attendance), but re-running cron on same day creates duplicate overtime

---

## Extension Points

> *Where and how developers can override or extend this flow.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 3 | `resource.resource.create()` | Custom resource creation | vals_list | Extend via `super()` + custom vals |
| Step 4 | `_onchange_company_id()` | Auto-fill calendar from company | self | Add field sync for custom fields |
| Step 5 | `_onchange_user_id()` | Auto-fill tz from user | self | Add custom tz logic |
| Step 9 | `_get_work_days_data_batch()` | Custom working day computation | `resources, start, end, calendar` | Override to add custom day types |
| Step 12 | `_get_calendar_leaves()` | Customize leave exclusions | `start, end, calendar` | Extend to add custom leave types |
| Step 17 | `_interval_schedule_get()` | Interval subtraction for leaves | `start, end, intervals` | Override for custom interval handling |
| Step 20 | `attendance_action_change()` | Custom check-in logic | self | Extend with `super()` + side effects |
| Step 24 | `_compute_worked_hours()` | Custom worked hours calculation | self | Override for break deduction logic |
| Step 28 | `_adjust_to_calendar()` | Clip attendance to work hours | `start, end, compute_leaves` | Override for flex-time support |
| Step 33 | `_action_overtime_validation()` | Custom overtime rules | self | Extend with `super()` + new overtime types |
| Post-create | `_compute_days_get()` | Post-computation hook | `self, days` | Add custom day-type calculations |

**Standard override pattern:**
```python
# WRONG — replaces entire method
def _compute_worked_hours(self):
    # your code

# CORRECT — extends with super()
def _compute_worked_hours(self):
    res = super()._compute_worked_hours()
    # your additional code
    return res
```

**Odoo 19 specific hooks:**
- `resource.mixin` model provides `_get_calendar_leaves()` as the primary hook for customizing which days are excluded from working time
- `resource.calendar._get_global_attendances()` can be overridden to change default attendance intervals
- `hr.attendance._action_overtime_validation()` is the hook for custom overtime computation rules
- The `hours_per_day` field on `resource.calendar` is used as the daily benchmark for overtime threshold

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct `_workflow` calls (deprecated)
- Overriding `attendance_action_change()` without calling `super()` — breaks self-service check-in

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `hr.employee.create()` | `unlink()` | `hr.employee.unlink()` | Cascade deletes `resource.resource` |
| `resource.calendar.create()` | `unlink()` | `resource.calendar.unlink()` | Breaks calendar assignment for employees |
| `hr.attendance.create()` (check-in) | Delete attendance record | `unlink()` | Only if check-in was a mistake |
| `hr.attendance.check_out` written | Cannot undo check-out | Manual re-check-in | Creates new attendance record |
| `hr.payroll.overtime` created | Delete overtime | `unlink()` | Only before payroll locks the record |
| Leave days computed | Recompute | Re-save leave request | `number_of_days` is a computed field |
| Calendar attendance updated | Edit calendar | Write new hour_from/hour_to | Does not retroactively update attendance |

**Important:** This flow is **partially reversible**:
- Attendance records should generally not be deleted — they represent legal records of work time
- Editing a calendar does NOT retroactively change past attendance records
- Overtime records can be deleted before payroll locks them
- Check-in/check-out times cannot be easily edited — use "Edit check-in/check-out" button on attendance form

---

## Alternative Triggers

> *All the ways this flow can be initiated.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `attendance_action_change()` button | Employee kiosk / badge | Manual per check-in |
| User action | `hr.attendance` form write | Manager edits attendance | Manual |
| Cron scheduler | `_cron_check_in_complete()` | Server | Daily at configured time (auto-checkout) |
| Cron scheduler | `_action_overtime_validation()` | Server | Daily or per payroll run |
| Leave request | `hr.leave._compute_number_of_days()` | Employee submits leave | On leave draft save |
| Payroll run | `hr.payslip._compute_worked_days()` | Payroll officer | Per payslip batch |
| Project planning | `project.allocation._compute_allocations()` | Project manager | On allocation change |
| API / external | `hr.attendance.create()` via RPC | External badge system | On external event |
| Mobile app | `attendance_action_change()` via JSON-RPC | Employee mobile | Manual |

---

## Related

- [Modules/resource](modules/resource.md) — Resource module reference
- [Modules/hr_attendance](modules/hr_attendance.md) — HR attendance module reference
- [Flows/HR/attendance-checkin-flow](flows/hr/attendance-checkin-flow.md) — Check-in flow details
- [Flows/HR/leave-request-flow](flows/hr/leave-request-flow.md) — Leave request flow using calendar
- [Business/HR/quickstart-employee-setup](business/hr/quickstart-employee-setup.md) — Employee onboarding including resource setup
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) — Workflow pattern reference
- [Core/API](core/api.md) — @api decorator patterns
