---
type: flow
title: "Leave Request Flow"
primary_model: hr.leave
trigger: "User action — Time Off → Request Leave → Submit"
cross_module: true
models_touched:
  - hr.leave
  - hr.leave.allocation
  - resource.resource
  - resource.calendar.leaves
  - mail.activity
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/HR/employee-creation-flow](Flows/HR/employee-creation-flow.md)"
  - "[Flows/Base/resource-attendance-flow](Flows/Base/resource-attendance-flow.md)"
source_module: hr_holidays
source_path: ~/odoo/odoo19/odoo/addons/hr_holidays/
created: 2026-04-06
version: "1.0"
---

# Leave Request Flow

## Overview

Employee submits a leave request through the HR Holidays module. The request goes through validation, balance checking, and manager approval before being confirmed and reflected in the attendance calendar.

## Trigger Point

**User (Employee):** Opens **Time Off → Request Leave**, fills form, clicks **Submit**
**Method:** `hr.leave.create()` + `action_submit()`

---

## Complete Method Chain

```
1. hr.leave.create(vals)
   ├─► 2. _onchange_employee_id()
   │      ├─► 3. department_id from employee
   │      ├─► 4. holiday_status_id = default leave type
   │      └─► 5. manager_id from department
   │
   ├─► 6. _onchange_date_from()
   │      ├─► 7. number_of_days computed
   │      ├─► 8. _adjust_date_for_working_days()
   │      └─► 9. working_days count from calendar
   │
   ├─► 10. _onchange_date_to()
   │      └─► 11. number_of_days_days recomputed
   │
   └─► 12. action_submit()
          ├─► 13. state = 'confirm'
          ├─► 14. _check_date_security() — no past dates
          ├─► 15. _check_double_conflict() — no overlapping leaves
          │      └─► 16. IF conflict found:
          │             └─► 17. raise ValidationError
          │
          ├─► 18. activity_schedule() for manager
          │      └─► 19. mail.activity created with due date
          │
          └─► 20. message_post "Leave Requested"
```

---

## Approval Chain

```
REQUEST SUBMITTED (state = 'confirm')
  │
  ├─► Manager receives notification
  │
  ├─► IF hr_leave_manager_override = True (officer):
  │      └─► action_validate() → state = 'validate' → DONE
  │
  └─► ELSE (manager approval):
         ├─► action_approve()
         │      ├─► 21. _check_approval_config()
         │      ├─► 22. state = 'validate'
         │      ├─► 23. allocation deducted: allocation_id.qty_taken += days
         │      ├─► 24. _create_resource_leave()
         │      │      └─► 25. resource.calendar.leaves created
         │      │             └─► 26. Calendar blocked for leave period
         │      ├─► 27. _compute_number_of_days()
         │      └─► 28. activity unlink()
         │
         └─► ELSE: action_refuse()
                ├─► state = 'refuse'
                └─► message_post "Leave Refused"
```

---

## Decision Tree

```
Leave Request Submitted
│
├─► Conflict check: overlapping leaves?
│  ├─► YES → raise ValidationError("Leave overlaps with existing request")
│  └─► NO → continue
│
├─► Balance check: sufficient allocation?
│  ├─► NO (insufficient) → warning shown (can still submit if allowed)
│  └─► YES → continue
│
├─► Manager override (officer)?
│  ├─► YES → validate directly
│  └─► NO → send to manager
│
└─► Manager decision:
   ├─► Approve → validate → calendar blocked
   └─► Refuse → refused → no calendar block
```

---

## Database State

| Table | Created/Updated | Fields |
|-------|----------------|--------|
| `hr_leave` | Created | employee_id, holiday_status_id, date_from, date_to, state |
| `mail.activity` | Created | manager notified |
| `resource_calendar_leaves` | Created | Calendar blocked |
| `hr_leave_allocation` | Updated | qty_taken incremented (on validate) |

---

## Error Scenarios

| Scenario | Error | Prevention |
|----------|-------|------------|
| Overlapping dates | `ValidationError` | Cannot submit overlapping leaves |
| Past dates | `ValidationError` | Cannot request leave in the past |
| Insufficient balance | Warning (soft) | Check allocation before submitting |
| Employee not allocated | `ValidationError` | Must have allocation for leave type |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Manager notified | `mail.activity` | Activity created for manager |
| Calendar blocked | `resource.calendar.leaves` | Working days reduced |
| Allocation deducted | `hr.leave.allocation` | Available balance decreased |

---

## Extension Points

| Hook | Purpose | Override |
|------|---------|---------|
| `_check_holidays()` | Custom validation | Extend |
| `_create_resource_leave()` | Calendar blocking | Extend |

---

## Related

- [Modules/HR](Modules/HR.md) — HR module reference
- [Flows/HR/employee-creation-flow](Flows/HR/employee-creation-flow.md) — Employee setup
