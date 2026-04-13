---
type: flow
title: "Employee Creation Flow"
primary_model: hr.employee
trigger: "User action — HR → Employees → Create → Save"
cross_module: true
models_touched:
  - hr.employee
  - hr.version
  - resource.resource
  - res.partner
  - mail.thread
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/HR/employee-archival-flow](odoo-19/Flows/HR/employee-archival-flow.md)"
  - "[Flows/Base/resource-attendance-flow](odoo-19/Flows/Base/resource-attendance-flow.md)"
related_guides:
  - "[Business/HR/quickstart-employee-setup](odoo-19/Business/HR/quickstart-employee-setup.md)"
source_module: hr
source_path: ~/odoo/odoo19/odoo/addons/hr/
created: 2026-04-06
version: "1.0"
---

# Employee Creation Flow

## Overview

Complete end-to-end method chain when a new employee record is created through the Odoo UI. Covers all cross-module triggers, branching logic, and side effects. The employee model uses delegation inheritance via `_inherits` to `hr.version`, making the creation flow involve multiple related records simultaneously.

## Trigger Point

**User:** Opens **HR → Employees → Create**, fills the form, clicks **Save**.

**Method:** `hr.employee.create(vals)`

**Context:** Runs as the current logged-in user (HR Manager or HR Officer), with full ACL checks.

---

## Complete Method Chain

```
1. hr.employee.create(vals)
   │
   ├─► 2. _compute_version_id()      [@api.depends]
   │      └─► context version_id synced to vals
   │
   ├─► 3. resource.resource.create()  [via _inherits]
   │      └─► 4. resource_id set (inverse of _inherits)
   │            └─► 5. _inverse_calendar_id()
   │                  └─► 6. resource_calendar_id synced
   │
   ├─► 7. _create_work_contacts()
   │      └─► 8. res.partner.create({
   │            name: employee.name,
   │            email: employee.work_email,
   │            company_id: employee.company_id,
   │            employee_id: employee.id
   │          })
   │            └─► 9. work_contact_id = this partner
   │
   ├─► 10. hr.version.create({
   │        employee_id: self.id,
   │        date_version: vals.get('date_start', today),
   │        contract_date_start: vals.get('contract_date_start'),
   │        contract_wage: vals.get('wage'),
   │        ...
   │      })
   │        └─► 11. current_version_id = this record
   │              └─► 12. _compute_current_version_id()
   │
   ├─► 13. IF vals.get('user_id'):
   │      └─► 14. _onchange_user()
   │            ├─► name = user.name
   │            ├─► work_email = user.email
   │            ├─► tz = user.tz
   │            └─► mobile_phone = user.mobile
   │
   ├─► 15. IF vals.get('contract_template_id'):
   │      └─► 16. _onchange_contract_template_id()
   │            ├─► contract_type_id = template.type_id
   │            ├─► structure_type_id = template.structure_type_id
   │            ├─► resource_calendar_id = template.calendar_id
   │            └─► wage = template.wage
   │
   ├─► 17. _sync_salary_distribution()
   │      └─► 18. salary_distribution JSON updated
   │
   ├─► 19. _compute_presence_icon()
   │      └─► 20. _compute_presence_state()
   │            └─► 21. _get_employee_working_now()
   │                  └─► 22. hr_presence_state set
   │
   ├─► 23. mail.thread:
   │      ├─► 24. partner_ids subscribed (work_contact_id)
   │      └─► 25. Message posted: "Employee Created"
   │
   └─► 26. IF vals.get('job_id'):
          └─► 27. hr.job._compute_employees()  [@api.depends]
                └─► 28. no_of_employee updated
```

---

## Decision Tree

```
Employee Created
│
├─ user_id provided?
│  ├─ YES → _onchange_user() fires
│  │        └─ name, work_email, tz, mobile synced from user
│  └─ NO → manual entry, no auto-sync
│
├─ contract_template_id provided?
│  ├─ YES → _onchange_contract_template_id() fires
│  │        └─ contract_type, structure_type, calendar, wage auto-filled
│  └─ NO → start from blank contract (manual setup)
│
├─ bank_account_ids have allow_out_payment?
│  ├─ YES → is_trusted_bank_account = False (warning flag)
│  └─ NO → is_trusted_bank_account = True
│
└─ timezone (tz) set?
   ├─ YES → used for attendance / presence calculation
   └─ NO → fallback to company's timezone
```

---

## Branching Matrix

| Condition | Path | Side Effect |
|-----------|------|-------------|
| `user_id` provided | A → `_onchange_user()` | name, email, tz, mobile auto-filled |
| `user_id` empty | A → skipped | manual entry required |
| `contract_template_id` set | B → `_onchange_contract_template_id()` | wage, type, calendar auto-filled |
| `contract_template_id` empty | B → skipped | manual contract setup |
| `job_id` provided | C → `hr.job._compute_employees()` | no_of_employee incremented |
| `job_id` empty | C → skipped | job count unchanged |

---

## Database State After Completion

| Table | Record Created | Key Fields |
|-------|--------------|------------|
| `hr_employee` | 1 | name, company_id, resource_id, work_contact_id |
| `hr_version` | 1 | employee_id, contract_date_start, contract_wage |
| `resource_resource` | 1 | name, type, company_id, user_id |
| `res_partner` | 1 | name, email, company_id, employee_id |
| `mail_followers` | 1+ | follower added (work_contact_id) |
| `mail_message` | 1 | creation notification |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Barcode already exists | `ValidationError: Badge ID already exists` | `_barcode_uniq = unique(barcode)` |
| Same user + same company | `ValidationError: User already linked` | `_user_uniq = unique(user_id, company_id)` |
| Missing name | `ValidationError: Field 'Name' is required` | ORM `required=True` on name |
| Missing company_id | `ValidationError: Field 'Company' is required` | ORM `required=True` on company_id |
| Work email not unique | Warning (not blocking) | Soft validation |
| Barcode empty | Check-in may fail | Attendance requires barcode or PIN |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Resource created | `resource.resource` | Employee linked to resource planning |
| Work contact created | `res.partner` | Partner for email notifications |
| Version created | `hr.version` | Current contract version established |
| Presence initialized | `hr_presence_state` | Set to 'present' or 'out_of_working_hour' |
| Follower subscribed | `mail.followers` | Work contact receives notifications |

---

## Security Context

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `create()` | Current user | `group_hr_user` | Respects record rules |
| `resource.resource.create()` | Internal (via _inherits) | `sudo()` | No direct ACL needed |
| `res.partner.create()` | Internal | `sudo()` | Work contact creation |
| `hr.version.create()` | Internal | `sudo()` | Version management |
| `mail.thread` | Follower-based | Public | Followers get notification |

---

## Transaction Boundary

```
Steps 1-28  ✅ INSIDE transaction  — atomic (all or nothing)
Step 24     ✅ INSIDE transaction — mail.message created inline
Step 25     ✅ INSIDE transaction — follower subscribed inline
```

| Step | Boundary | Behavior on Failure |
|------|----------|---------------------|
| Steps 1-22 | ✅ Atomic | Rollback on any error |
| mail.message | ✅ Within transaction | Rolled back with employee |
| mail.followers | ✅ Within transaction | Rolled back with employee |

> **Note:** Unlike some Odoo flows that queue mail asynchronously, employee creation does NOT use `queue_job` or `mail.mail` for the creation message — it uses inline `mail.message.create()`, so it IS inside the transaction.

---

## Idempotency

| Scenario | Behavior |
|----------|----------|
| Double-click save button | ORM deduplicates — only one record created |
| Re-save with same values | `write()` re-runs, no new version created |
| Re-trigger on existing record | Updates existing, does not duplicate |
| Network timeout + retry | Browser should check if record exists before retry |

**Non-idempotent element:**
- `ir.sequence` is NOT consumed on employee create (no auto-numbering by default)
- If using barcode generation: `generate_random_barcode()` is called once on create

---

## Extension Points

| Step | Hook Method | Purpose | Override Pattern |
|------|-------------|---------|-----------------|
| Pre-create | `_init()` | Pre-creation validation | Extend `create()` with vals |
| Post-create | `_post_create_hook()` | Post-creation side effects | Extend via `create()` override |
| Version creation | `_create_version()` | Custom version logic | Override `create_version()` |
| Work contact | `_create_work_contacts()` | Custom contact creation | Extend with `super()` |
| Onchange user | `_onchange_user()` | User sync logic | Extend with `super()` |

```python
# Standard extension pattern
class HrEmployeeExtended(models.Model):
    _inherit = 'hr.employee'

    def _post_create_hook(self):
        # Run Odoo standard
        super()._post_create_hook()
        # Add custom: create ERP user account
        self._create_user_account()
```

---

## Reverse / Undo Flow

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `create()` | `unlink()` | `record.unlink()` | Cascade deletes version, partner |
| `create()` | `action_archive()` | `record.action_archive()` | Record preserved, hidden from active lists |
| Version created | Cannot delete version | Create new version instead | Version history preserved |

**Archival (Soft Delete):**
```
action_archive()
  └─► write({'active': False})
        └─► Employee hidden from active list
        └─► Resource deactivated
        └─► Presence set to 'archive'
        └─► Pending activities cancelled
              └─► Employee record NOT deleted
```

---

## Alternative Triggers

| Trigger Type | Method | Context | Frequency |
|-------------|--------|---------|-----------|
| User action | `create()` | Form save | Manual |
| Import | `import()` | CSV/XLS import | Bulk |
| Onchange from user form | `_onchange_user()` | Field change | On demand |
| Contract template | `_onchange_contract_template_id()` | Field change | On demand |

---

## Related

- [Modules/HR](odoo-18/Modules/hr.md) — Module reference (includes method chain summary)
- [Business/HR/quickstart-employee-setup](odoo-19/Business/HR/quickstart-employee-setup.md) — Step-by-step guide
- [Flows/HR/employee-archival-flow](odoo-19/Flows/HR/employee-archival-flow.md) — Archive/unarchive flow
- [Modules/resource](odoo-18/Modules/resource.md) — resource.resource model
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — State machine patterns
