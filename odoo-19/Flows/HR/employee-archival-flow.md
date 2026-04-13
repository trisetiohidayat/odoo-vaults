---
type: flow
title: "Employee Archival Flow"
primary_model: hr.employee
trigger: "User action — Employee form → Action → Archive"
cross_module: true
models_touched:
  - hr.employee
  - resource.resource
  - hr.department
  - mail.activity
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/HR/employee-creation-flow](employee-creation-flow.md)"
related_guides:
  - "[Business/HR/quickstart-employee-setup](quickstart-employee-setup.md)"
source_module: hr
source_path: ~/odoo/odoo19/odoo/addons/hr/
created: 2026-04-06
version: "1.0"
---

# Employee Archival Flow

## Overview

When an employee leaves the company or is temporarily inactive, the `action_archive()` method soft-deletes the employee record. This preserves the employee's history while removing them from active lists and workflows. The record itself is NOT deleted — only marked as `active = False`.

## Trigger Point

**User:** Opens **Employee form → Action → Archive** (or right-click → Archive)

**Method:** `hr.employee.action_archive()`

**Context:** Runs as the current logged-in user (HR Manager required).

---

## Complete Method Chain

```
1. hr.employee.action_archive()
   │
   ├─► 2. self.write({'active': False})
   │      ├─► 3. active = False
   │      ├─► 4. is_past = True
   │      ├─► 5. hr_presence_state → 'archive'
   │      ├─► 6. hr_icon_display → 'presence_archive'
   │      └─► 7. mail.thread notification
   │
   ├─► 8. resource.resource.write({'active': False})
   │      └─► 9. calendar access revoked
   │            └─► Employee no longer counted in attendance
   │
   ├─► 10. IF self.parent_id (is manager):
   │       └─► 11. Subordinate employees:
   │             ├─► parent_id = False
   │             └─► manager reassignment notification
   │
   ├─► 12. Department recompute
   │       └─► 13. total_employee decremented
   │
   └─► 14. mail.activity search for employee
          └─► 15. activity_ids.unlink()
                └─► All pending activities cancelled
```

---

## Decision Tree

```
action_archive() called
│
├─► Employee is a manager?
│  ├─ YES → Subordinates reassigned
│  │        └─► parent_id = False for all direct reports
│  │        └─► Notification sent to HR
│  └─ NO → Skip subordinate handling
│
├─► Has subordinates?
│  ├─ YES → Must reassign or archive subordinates first
│  │        └─► Warning shown: "Cannot archive manager with subordinates"
│  └─ NO → Proceed with archive
│
├─► Has pending activities?
│  ├─ YES → Activities cancelled automatically
│  └─ NO → Continue
│
└─► Archive complete
        └─► Employee hidden from active lists
        └─► Resource deactivated
        └─► Version marked as past
```

---

## Database State After Completion

| Table | Record Updated | Key Fields |
|-------|--------------|------------|
| `hr_employee` | Updated | active = False, is_past = True |
| `resource_resource` | Updated | active = False |
| `mail_activity` | Deleted | All employee activities removed |

---

## Error Scenarios

| Scenario | Error Raised | Reason |
|----------|-------------|--------|
| Archive manager with subordinates | `UserError` | Cannot leave subordinates without manager |
| No HR Manager rights | `AccessError` | Requires `group_hr_manager` |
| Employee already archived | Silent | No-op, already archived |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Resource deactivated | `resource.resource` | No longer in attendance counts |
| Subordinates orphaned | `hr.employee` | Parent_id cleared, need reassignment |
| Activities cancelled | `mail.activity` | All pending to-dos deleted |
| Presence archived | `hr_presence_state` | Set to 'archive' |

---

## Security Context

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `action_archive()` | Current user | `group_hr_manager` | Button-level security |
| `write({'active': False})` | Current user | `group_hr_manager` | Write access to employee |
| `resource.write()` | Internal | `sudo()` | System context |
| `activity.unlink()` | Internal | `sudo()` | System cleanup |

---

## Transaction Boundary

```
Steps 1-15  ✅ ALL INSIDE transaction  — atomic
```

| Step | Boundary | Behavior on Failure |
|------|----------|---------------------|
| Steps 1-15 | ✅ Atomic | Complete rollback if any error |

---

## Idempotency

| Scenario | Behavior |
|----------|----------|
| Archive already archived employee | Silent no-op |
| Double-click archive button | First call succeeds, second is no-op |
| Unarchive then re-archive | Works correctly — toggle supported |

---

## Extension Points

| Step | Hook Method | Purpose | Override Pattern |
|------|-------------|---------|-----------------|
| Pre-archive | `_check_before_archive()` | Custom validation | Extend with `super()` |
| Post-archive | `_post_archive_hook()` | Custom side effects | Extend with `super()` |

---

## Reverse / Undo Flow

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `action_archive()` | `action_unarchive()` | `record.action_unarchive()` | Restores active = True, resource reactivates |
| Unarchive | Also restores | subordinates NOT automatically restored | Must reassign managers manually |

**Unarchive Method Chain:**
```
action_unarchive()
  └─► write({'active': True})
        └─► is_past = False
        └─► resource.resource active restored
        └─► BUT: subordinate parent_id NOT restored
```

> **⚠️ Important:** Unarchiving an employee does NOT automatically restore the manager-subordinate relationship. HR Manager must manually reassign subordinates to the unarchived manager.

---

## Related

- [Modules/HR](HR.md) — Module reference
- [Flows/HR/employee-creation-flow](employee-creation-flow.md) — Creation flow (inverse of archive)
- [Business/HR/quickstart-employee-setup](quickstart-employee-setup.md) — Step-by-step guide
