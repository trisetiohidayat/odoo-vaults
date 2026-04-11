---
type: flow
title: "Attendance Check-In Flow"
primary_model: hr.attendance
trigger: "User action — Kiosk / Barcode scan / Mobile GPS / Portal"
cross_module: true
models_touched:
  - hr.attendance
  - hr.employee
  - resource.resource
  - resource.calendar
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[[Flows/HR/employee-creation-flow]]"
  - "[[Flows/Base/resource-attendance-flow]]"
related_guides:
  - "[[Business/HR/leave-management-guide]]"
source_module: hr_attendance
source_path: ~/odoo/odoo19/odoo/addons/hr_attendance/
created: 2026-04-07
updated: 2026-04-07
version: "1.0"
---

# Attendance Check-In Flow

## Overview

Employee checking in or out for attendance tracking — creates attendance records, calculates late hours, and updates real-time presence state. This flow handles four entry paths (kiosk, barcode, mobile GPS, manual portal) and ensures accurate worked hours computation and overtime tracking.

## Trigger Point

Four parallel entry paths all converge on the same core method:
- **Kiosk mode:** User selects employee from on-screen list or badge scan
- **Barcode/PIN scan:** Hardware scanner reads badge barcode or typed PIN → identifies employee
- **Mobile GPS:** Employee opens mobile app within geofence radius
- **Manual portal:** Employee manually presses Check In / Check Out via web or portal

---

## Complete Method Chain

```
1. hr.attendance._attendance_action_change()
   │
   ├─► 2. _find_current_employee()
   │      └─► identify employee from context (kiosk, user, barcode scan)
   │            └─► 3. IF kiosk mode:
   │                  └─► employee selected from list
   │            └─► 4. IF barcode scan:
   │                  └─► hr.employee.search([('barcode', '=', scanned_barcode)])
   │            └─► 5. IF PIN entry:
   │                  └─► hr.employee.search([('pin', '=', pin_code)])
   │            └─► 6. IF mobile GPS:
   │                  └─► employee_id from current user
   │
   ├─► 7. hr.attendance.search([
   │         ('employee_id', '=', emp.id),
   │         ('check_out', '=', False)
   │      ])
   │      └─► 8. IF open attendance found (check_in but no check_out):
   │            └─► 9. ACTION CHECK OUT:
   │                  ├─► 10. attendance.write({'check_out': now()})
   │                  │      └─► 11. worked_hours computed = check_out - check_in
   │                  │            └─► 12. hr.employee.hr_presence_state = 'out_of_working_hour'
   │                  │
   │                  ├─► 13. resource.resource._compute_hours()
   │                  │      └─► 14. resource hours updated for period
   │                  │
   │                  └─► 15. _update_overtime()
   │                        └─► 16. IF overtime configured:
   │                              └─► overtime entry created
   │
   ├─► 17. ELSE (no open attendance):
   │      └─► 18. ACTION CHECK IN:
   │            ├─► 19. hr.attendance.create({
   │            │      'employee_id': emp.id,
   │            │      'check_in': now()
   │            │   })
   │            │
   │            ├─► 20. IF check_in > resource_calendar.hours:
   │            │      └─► 21. late_hours recorded
   │            │            └─► 22. attendance marked as late
   │            │
   │            ├─► 23. hr.employee.hr_presence_state = 'present'
   │            │      └─► 24. hr_icon_display = 'presence_present'
   │            │
   │            └─► 25. _update_overtime()
   │
   ├─► (Post-action effects — same for check-in and check-out):
   │      └─► mail.message posted if notification enabled
   │      └─► IF kiosk: display next employee prompt
   │      └─► IF mobile: GPS coordinates recorded if geolocation enabled
   │      └─► activity scheduled for manager if overtime threshold exceeded
```

---

## Decision Tree

```
Attendance action triggered
│
├─► Has open attendance (check_in without check_out)?
   ├─► YES → action_check_out()
   │         └─► worked_hours computed
   │         └─► presence_state → 'out_of_working_hour'
   │         └─► overtime calculated
   │
   └─► NO → action_check_in()
            └─► attendance record created
            └─► Check if late arrival?
                 ├─► YES → late_hours recorded, attendance flagged
                 └─► NO → normal check-in
            └─► presence_state → 'present'
            └─► overtime calculated
            └─► Post-action: notification / GPS / kiosk prompt
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `hr_attendance` | Created (check-in) or Updated (check-out) | employee_id, check_in, check_out, worked_hours, late_hours |
| `hr_employee` | Updated (presence state) | hr_presence_state, hr_icon_display |
| `resource_resource` | Updated (hours tracked) | hours_total |
| `mail_message` | Created (if notifications on) | subtype, body |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Barcode not found | `ValidationError` | No employee with matching barcode |
| PIN code invalid | `ValidationError` | No employee with matching PIN |
| GPS outside geofence | `UserError` | "You must be within the allowed location to check in" |
| Mobile app offline | Retry on reconnect | Offline-first; synced on next connection |
| Double check-in (no open attendance) | `UserError` | "You are already checked in" — prevents duplicate |
| Late check-out after midnight | No error | Hours split across calendar days correctly |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Presence state updated | `hr.employee` | `hr_presence_state` and `hr_icon_display` change |
| Worked hours computed | `hr.attendance` | `worked_hours` stored on check-out |
| Late hours flagged | `hr.attendance` | `late_hours` recorded if late arrival |
| Overtime tracked | `hr.attendance` | Overtime entry created if threshold exceeded |
| Mail notification | `mail.message` | Follower notified if attendance notification enabled |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `_attendance_action_change()` | Current user | `group_hr_user` or self (own attendance) | Respects record rules |
| `_find_current_employee()` | Current user | Read on `hr.employee` | Uses barcode/PIN search |
| `hr.attendance.create()` | Current user | `group_hr_user` | Creates own record |
| `hr.attendance.write()` | Current user | `group_hr_user` | Updates own record |
| `_update_overtime()` | `sudo()` | System (internal) | Cross-model write |
| Kiosk mode | Supervisor | `group_hr_manager` | Can check in any employee |

**Key principle:** Self-service attendance (own check-in/out) does not require `group_hr_user`. Kiosk and manager overrides do.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside.*

```
Steps 1-6    ✅ INSIDE transaction  — atomic
Steps 7-16   ✅ INSIDE transaction  — atomic (create/write attendance)
Step 17+     ❌ OUTSIDE transaction — via mail queue (notification)
Steps 18-25  ✅ INSIDE transaction  — atomic (create/write attendance)
Post-actions (notifications, GPS log) ❌ OUTSIDE transaction — via queue
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Attendance create/write | ✅ Atomic | Rollback on any error |
| Mail notification | ❌ Async queue | Retried by `ir.mail.server` cron |
| GPS coordinate storage | ❌ Async | Stored in separate log table |
| Overtime calculation | ✅ Atomic | Rolled back with transaction |

**Rule of thumb:** Core attendance record creation is always inside the transaction. Notifications and GPS logging happen after commit.

---

## Idempotency

> *What happens when this flow is executed multiple times.*

| Scenario | Behavior |
|----------|----------|
| Double-click Check In button | Only one attendance record created |
| Rapid repeated check-in calls | `search()` for open attendance prevents duplicate |
| Re-trigger check-out on already checked-out record | `ValidationError` — "Already checked out" |
| Mobile offline sync on reconnect | Idempotent — same check-in time used |

**Common patterns:**
- **Idempotent:** Check-in on no-open-attendance (no-op if already checked in)
- **Non-idempotent:** Check-out creates worked_hours entry — can only happen once per open attendance

---

## Extension Points

> *Where and how developers can override or extend this flow.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 2 | `_find_current_employee()` | Custom employee identification | self | Extend with additional search criteria |
| Step 3-6 | Employee lookup paths | Support new ID mechanism (RFID, NFC) | barcode, pin | Add new search in `_find_current_employee()` |
| Step 21 | Late detection logic | Custom late policy (grace period config) | check_in, calendar | Override `_compute_late_hours()` |
| Step 25 | `_update_overtime()` | Custom overtime rules | self | Extend via `super()` |
| Post-create | Post-action hooks | GPS, notifications, KPIs | self | Extend via `create()` override |
| Validation | `_check_*()` | Custom attendance rules | self | Add `@api.constrains` |

**Standard override pattern:**
```python
# CORRECT — extends with super()
def _attendance_action_change(self):
    result = super()._attendance_action_change()
    # custom GPS logging, third-party sync, etc.
    return result
```

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct workflow calls (deprecated — use `action_*` methods)

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| Check In | Regularization request | `hr.attendance.regulate()` or manual correction | HR manager approves |
| Check Out | Edit check-out time | `hr.attendance.write({'check_out': new_time})` | Requires `group_hr_manager` |
| Late flag | Remove late flag | `write({'late_hours': 0.0})` | HR manager approval |
| Overtime entry | Delete overtime record | `hr.attendance.overtime.unlink()` | Only if not validated |

**Important:**
- Attendance records can be edited by HR manager (time corrections)
- Deleting an attendance record is possible but triggers re-computation of worked_hours
- Attendance regularization (HR request) creates a separate `hr.attendance.regularization` record
- The original check_in time is preserved in audit trail — only check_out can be edited

---

## Alternative Triggers

> *All the ways this flow can be initiated.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| Kiosk action | `_attendance_action_change()` | Kiosk device, badge scan | Manual |
| Barcode scanner | `_attendance_action_change()` | Hardware scanner | Manual |
| Mobile app | `_attendance_action_change()` | Mobile GPS | Manual |
| Manual portal | `_attendance_action_change()` | Web/portal UI | Manual |
| Cron scheduler | `_cron_*()` | Auto-check-out for forgotten sessions | Daily |
| Onchanges on related models | Cascade onchange | Related field change | On demand |
| API / external system | `external_endpoint()` | HR system integration | On demand |

**For AI reasoning:** When asked "what happens if an employee forgets to check out?", trace the cron-based auto check-out and regularization request flow.

---

## Related

- [[Modules/HR]] — HR module reference
- [[Modules/resource]] — resource.resource, resource.calendar
- [[Flows/HR/employee-creation-flow]] — Employee creation
- [[Flows/Base/resource-attendance-flow]] — Resource attendance base
- [[Patterns/Workflow Patterns]] — Workflow pattern reference
- [[Core/API]] — @api decorator patterns