---
type: flow
title: "Recruitment Applicant Flow"
primary_model: hr.applicant
trigger: "User action — Recruitment → Create Applicant"
cross_module: true
models_touched:
  - hr.applicant
  - hr.employee
  - res.partner
  - hr.job
  - calendar.event
  - mail.template
  - utm.source
  - utm.campaign
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/HR/employee-creation-flow](Flows/HR/employee-creation-flow.md)"
  - "[Flows/HR/contract-lifecycle-flow](Flows/HR/contract-lifecycle-flow.md)"
related_guides:
  - "[Modules/HR](Modules/HR.md)"
source_module: hr_recruitment
source_path: ~/odoo/odoo19/odoo/addons/hr_recruitment/
created: 2026-04-07
version: "1.0"
---

# Recruitment Applicant Flow

## Overview

An applicant is created in the HR Recruitment module, either manually by a recruiter or automatically from a website form submission. The applicant progresses through recruitment stages (New, Qualification, Interview, Offer, Hired, or Refused). UTM source and campaign are captured on creation for analytics. When a candidate is hired, an employee record is automatically created from the applicant data. The flow spans res.partner, hr.job, hr.applicant, hr.employee, calendar.event, and mail.template.

## Trigger Point

**User (Recruiter/HR Officer):** Opens **Recruitment → Applications → Create**, fills applicant form (partner, job, email, phone), clicks **Save**.
**Method:** `hr.applicant.create(vals)` + optional `action_apply()` or website form auto-submit via `hr.applicant.portal_create()`

---

## Complete Method Chain

### Applicant Creation

```
1. hr.applicant.create(vals)
   ├─► 2. _onchange_partner_id()
   │      ├─► 3. email_from = partner.email
   │      ├─► 4. phone = partner.phone
   │      └─► 5. partner_phone / partner_mobile synced
   │
   ├─► 6. _onchange_job_id()
   │      ├─► 7. department_id = job.department_id
   │      ├─► 8. manager_id = job.manager_id (department manager)
   │      ├─► 9. stage_id = job.stage_ids[0] (initial stage)
   │      └─► 10. company_id = job.company_id
   │
   ├─► 11. utm.mixin._track_subtype()
   │       ├─► 12. source_id captured from utm_source_id in vals
   │       ├─► 13. campaign_id captured from utm_campaign_id in vals
   │       └─► 14. medium_id captured from utm_medium_id in vals
   │
   ├─► 15. _compute_department_id() — fallback to job department
   └─► 16. message_subscribe([partner.user_ids[0].partner_id.id]) if applicable
```

### Stage Progression — Apply / Qualification

```
17. hr.applicant.action_apply()
    ├─► 18. stage = 'qualification' (via stage_id write)
    ├─► 19. mail.template.send_mail() — email_template_to_validate
    │       └─► 20. email sent to applicant (via mail.mail queue)
    │
    ├─► 21. calendar.event.create() — interview calendar event
    │       └─► 22. attendees = [applicant.partner_id, user_ids]
    │
    └─► 23. activity_schedule() — recruiter follow-up activity
            └─► 24. mail.activity for recruiter (date_deadline = today + 3)
```

```
25. hr.applicant.action_set_qualification()
    ├─► 26. _checkqualification() — required fields present
    ├─► 27. stage = 'qualification' (second explicit call)
    └─► 28. message_post "Application Qualified"
```

### Stage Progression — Interview Scheduling

```
29. hr.applicant.action_make_meeting()
    ├─► 30. calendar.event.create({
    │            'name': 'Interview: ' + applicant.name,
    │            'partner_ids': [(6, 0, [applicant.partner_id.id, ...])],
    │            'start': scheduled datetime,
    │            'stop': end datetime,
    │            'resource_id': meeting_room or False
    │       })
    │       └─► 31. mail.mail notifications sent to attendees
    │
    └─► 32. mail.activity.schedule() for recruiter
            └─► 33. reminder activity created before interview
```

### Stage Progression — Offer

```
34. hr.applicant.action_set_offer()
    ├─► 35. stage = 'offer' — offer extended to candidate
    ├─► 36. mail.template.send_mail() — offer letter template
    └─► 37. activity_schedule() for HR manager
```

### Stage Progression — Hired (Employee Creation)

```
38. hr.applicant.action_set_hired()
    ├─► 39. _check_hired() — required fields validated (partner_id, job_id)
    ├─► 40. stage = 'hired'
    │
    ├─► 41. create_employee_from_applicant()
    │       ├─► 42. hr.employee.create({
    │       │           'name': applicant.partner_id.name,
    │       │           'job_id': applicant.job_id.id,
    │       │           'department_id': applicant.department_id.id,
    │       │           'address_home_id': applicant.partner_id.id,
    │       │           'work_email': applicant.email_from,
    │       │           'work_phone': applicant.partner_phone,
    │       │           'job_title': applicant.job_id.name,
    │       │           'resource_calendar_id': applicant.department_id.resource_calendar_id.id
    │       │       })
    │       │       └─► 43. resource.resource created via delegation (_inherits)
    │       │              └─► 44. calendar.attendance from working hours
    │       │
    │       └─► 45. applicant.emp_id = employee.id (Many2one inverse)
    │
    └─► 46. message_post "Applicant hired — Employee created"
            └─► 47. recruiter notified via mail
```

### Stage Progression — Refused

```
48. hr.applicant.action_set_refuse()
    ├─► 49. stage = 'refused'
    ├─► 50. reason captured in refuse_reason field
    └─► 51. mail.activity unlink() — all pending activities cleared
```

---

## Decision Tree

```
Application Received (hr.applicant created)
│
├─► partner_id set?
│  ├─► YES → email_from, phone populated from partner
│  └─► NO → manual email/phone entry
│
├─► job_id selected?
│  ├─► YES → department_id, manager_id, stage_id from job
│  └─► NO → defaults only
│
├─► UTM data captured (source, campaign, medium) — always
│
├─► Recruiter action: Initial Review
│  ├─► QUALIFY → action_set_qualification() → qualification stage
│  ├─► REFUSE → action_set_refuse() → refused stage
│  └─► SCHEDULE INTERVIEW → action_make_meeting() → calendar.event created
│
├─► Interview conducted
│  └─► OUTCOME decision:
│       ├─► OFFER → action_set_offer() → offer stage → email sent
│       └─► REJECT → action_set_refuse() → refused stage
│
└─► Offer accepted?
   ├─► YES → action_set_hired()
   │          └─► hr.employee created from applicant data
   │                 └─► Proceed to [Flows/HR/contract-lifecycle-flow](Flows/HR/contract-lifecycle-flow.md)
   │
   └─► NO → action_set_refuse() → refused stage
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `hr_applicant` | Created | name, partner_id, job_id, stage_id, email_from, phone, department_id, user_id, source_id, campaign_id, emp_id |
| `res_partner` | Created (from website) or existing | Applicant partner record |
| `hr_job` | Updated | applicant_count incremented |
| `hr_employee` | Created (on hire) | name, job_id, department_id, address_home_id, work_email |
| `resource_resource` | Created (via delegation _inherits) | resource_calendar_id, name |
| `calendar_event` | Created (on interview) | name, start, stop, partner_ids, applicant_id |
| `mail_activity` | Created | activity for recruiter/manager |
| `mail_mail` | Created | email notifications queued |
| `mail_message` | Created | stage change chatter messages |
| `utm_source_rel` | Created | UTM tracking link for applicant |
| `utm_campaign` | Updated | applicant_count on campaign |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Prevention |
|----------|-------------|------------------------|
| Duplicate applicant email (same partner + job) | `ValidationError` or warning | Unique constraint on partner_id + job_id per stage — optional via `is_applicant_multicompany` |
| Job position closed / inactive | `UserError` | "Cannot create applicant for closed job" — `job.state != 'recruit'` check |
| Partner not found | Silent or `ValidationError` | Partner must exist if partner_id provided |
| Stage transition invalid | `UserError` | Stage sequence enforced — cannot skip stages |
| Hired without required fields | `ValidationError` | `partner_id` and `job_id` required for `action_set_hired()` |
| Hired without department_id | Soft error | Employee created with missing department |
| Refuse without reason | Silent | refuse_reason can be empty |
| Calendar event without datetime | `ValidationError` | start/stop required on calendar.event.create() |
| User without HR rights | `AccessError` | `group_hr_recruiter` required for most actions |
| Portal applicant on closed job | `ValidationError` | Portal `create()` checks job state |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Partner followed | `mail.followers` | Partner subscribed to applicant record |
| UTM tracked | `utm.source` / `utm.campaign` | Source, campaign, medium linked to applicant |
| Job applicant count | `hr.job` | applicant_count incremented |
| Resource created | `resource.resource` | Employee linked to working calendar |
| Interview scheduled | `calendar.event` | Attendees notified via email |
| Recruiter notified | `mail.activity` | To-do activity for follow-up |
| Email sent | `mail.mail` | Template email to applicant (offer/qualification) |
| Employee linked | `hr.applicant.emp_id` | Applicant → Employee bidirectional link |

---

## Security Context

| Step | Security Mode | Access Required | Notes |
|------|--------------|----------------|-------|
| `create()` | Current user | `group_hr_recruiter` | HR officer can create |
| `_onchange_partner_id()` | Current user | Read on res.partner | No write |
| `_onchange_job_id()` | Current user | Read on hr.job | No write |
| `action_apply()` | Current user | `group_hr_recruiter` | Triggers email |
| `action_make_meeting()` | Current user | Write on calendar.event | Attendee access |
| `action_set_hired()` | Current user + `sudo()` for employee | `group_hr_manager` | Creates employee via sudo |
| `action_set_refuse()` | Current user | `group_hr_recruiter` | Clears activities |
| `action_set_qualification()` | Current user | `group_hr_recruiter` | Stage transition |
| `create_employee_from_applicant()` | `sudo()` internally | System | Employee creation bypasses ACL |
| `calendar.event.create()` | `sudo()` for attendee write | System | Calendar write bypasses ACL |

**Key principle:** Applicant creation and stage actions run as the current logged-in recruiter user. Employee creation runs under `sudo()` internally to bypass record rules on `hr.employee`. Email sending uses the `mail.mail` async queue.

---

## Transaction Boundary

```
Steps 1-16   ✅ INSIDE transaction  — create() atomic
Steps 17-24  ✅ INSIDE transaction  — action_apply() atomic
Steps 25-28  ✅ INSIDE transaction  — action_set_qualification() atomic
Steps 29-33  ✅ INSIDE transaction  — action_make_meeting() atomic
Steps 38-47  ✅ INSIDE transaction  — action_set_hired() + employee create() atomic
Steps 48-51  ✅ INSIDE transaction  — action_set_refuse() atomic
Email send    ❌ OUTSIDE transaction — via mail.mail queue (ir.mail.server)
Calendar notif ❌ OUTSIDE transaction — mail.mail attendee notification
Activity      ✅ INSIDE transaction  — activity_schedule() inside ORM
```

| Step | Boundary | Behavior on Failure |
|------|----------|---------------------|
| `create()` / `write()` | ✅ Atomic | Rollback on any error |
| `create_employee_from_applicant()` | ✅ Atomic | Rolled back with parent transaction |
| `calendar.event.create()` | ✅ Atomic | Rolled back with transaction |
| Email notification | ❌ Async queue | Retried by `ir.mail.server` cron |
| UTM tracking | ✅ Atomic | Rolled back with transaction |

**Rule of thumb:** All ORM `create()`/`write()`/`action_*()` calls are atomic. Email delivery is fire-and-forget via `mail.mail` queue. Calendar attendee notifications are also queued. If applicant `create()` fails, no employee or calendar event is created.

---

## Idempotency

| Scenario | Behavior |
|----------|----------|
| Double-click Save on applicant form | ORM deduplicates — only one record created |
| Re-call `action_apply()` on already-applied applicant | Stage already 'qualification' or beyond — no-op; no duplicate email |
| Re-call `action_set_hired()` on already-hired applicant | Raises `UserError("Applicant already hired")` — emp_id already set |
| Re-call `action_set_refuse()` on already-refused applicant | Raises `UserError("Applicant already refused")` |
| Re-create calendar event for same interview | Creates duplicate events — implement idempotency via `existing event check` |
| Re-trigger `action_make_meeting()` | Creates new calendar.event each time — consider checking existing |
| Network timeout + retry on hire | `create_employee_from_applicant()` is idempotent per applicant |

**Non-idempotent operations:**
- `create_employee_from_applicant()` — creates one hr.employee record (protected by `emp_id` check in `action_set_hired()`)
- `calendar.event.create()` — no built-in duplicate check (creates new event each time)
- `mail.template.send_mail()` — may send duplicate emails (mail.mail queue deduplication by `mail_message_id`)
- Stage transition methods — protected by state checks (already 'hired', 'refused')

---

## Extension Points

| Step | Hook Method | Purpose | Override Pattern |
|------|-------------|---------|-----------------|
| Step 2 | `_onchange_partner_id()` | Auto-fill email/phone from partner | Extend with `super()` + field sync |
| Step 6 | `_onchange_job_id()` | Auto-fill department/manager/stage | Extend with `super()` + new defaults |
| Step 11 | `utm.mixin._track_subtype()` | UTM tracking customization | Override in utm.mixin |
| Step 17 | `action_apply()` | Custom apply behavior | Extend with `super()` |
| Step 29 | `action_make_meeting()` | Custom meeting creation | Extend with `super()` |
| Step 41 | `create_employee_from_applicant()` | Custom employee field mapping | Override for extra fields |
| Step 34 | `action_set_offer()` | Custom offer behavior | Extend with `super()` |
| Pre-38 | `_check_hired()` | Pre-hire validation | Add `@api.constrains` or override |
| Post-41 | Post-employee creation | Custom post-hire steps | Extend `action_set_hired()` |

```python
# Correct override pattern for hire action
def action_set_hired(self):
    self.ensure_one()
    res = super().action_set_hired()
    # custom post-hire: create user, assign group, etc.
    self.emp_id.sudo().write({'some_field': 'value'})
    return res

# Correct override for employee creation
def create_employee_from_applicant(self):
    self.ensure_one()
    employee_vals = {
        'name': self.partner_id.name,
        'job_id': self.job_id.id,
        'department_id': self.department_id.id,
        'address_home_id': self.partner_id.id,
        # extend with super() call:
    }
    return super().create_employee_from_applicant()  # delegates to base impl
```

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct XML workflow engine calls (deprecated — use `action_*` methods)
- `_古典_workflow()` calls (removed)

---

## Reverse / Undo Flow

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `create()` | `unlink()` | `record.unlink()` | Only in draft; cascades to calendar events |
| `action_apply()` | NOT directly reversible | Reset stage manually | Stage is editable |
| `action_set_qualification()` | NOT automatically reversible | Manual stage reset | No automated reverse |
| `action_make_meeting()` | `calendar.event.unlink()` | Unlink event | Removes from calendars |
| `action_set_offer()` | NOT automatically reversible | Manual stage reset | Offer letter already sent |
| `create_employee_from_applicant()` | `hr.employee.unlink()` | Unlink employee | Does NOT unlink applicant; manual |
| `action_set_hired()` | NOT automatically reversible | Manual: unlink employee, reset stage | Employee stays; applicant stage editable |
| `action_set_refuse()` | Reset stage manually | Write new stage_id | Activities already cleared |

**Important:** Hired applicants cannot be automatically "unhired". The employee record must be manually unlinked, and the applicant stage manually reset. This is intentional — the applicant pipeline is separate from the employee registry. Consider: `applicant.emp_id = False` + `applicant.stage_id = new_stage` for soft reversal.

---

## Alternative Triggers

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `action_apply()` button | Interactive | Manual |
| User action | `action_set_qualification()` button | Interactive | Manual |
| User action | `action_make_meeting()` button | Interactive | Manual |
| User action | `action_set_hired()` button | Interactive | Manual |
| User action | `action_set_refuse()` button | Interactive | Manual |
| Website form | `portal_create()` | Applicant via website | On submission |
| Website form (auto-apply) | `website_form_filter()` | Auto-stage and UTM | On submission |
| Cron scheduler | `_cron_auto_close_stale_applicants()` | Auto-refuse old applications | Daily |
| Import | `import_batch()` | CSV/XLS import | Bulk |
| Onchanges on related models | Cascade onchange | Partner or job field change | On demand |
| Recruitment campaign | `recruitment.apply()` | Batch stage update | Campaign trigger |

**For AI reasoning:** When applicant flow fails mid-way, check: (1) partner exists and has email, (2) job is in 'recruit' state, (3) current user has `group_hr_recruiter`, (4) required fields present for hire action, (5) UTM source/campaign IDs are valid.

---

## Related

- [Modules/HR](Modules/HR.md) — HR module reference
- [Flows/HR/employee-creation-flow](Flows/HR/employee-creation-flow.md) — Employee creation (called from hire action)
- [Flows/HR/contract-lifecycle-flow](Flows/HR/contract-lifecycle-flow.md) — Contract creation after hire
- [Flows/Base/mail-notification-flow](Flows/Base/mail-notification-flow.md) — Email notification mechanics
- [Core/API](Core/API.md) — @api.depends, @api.onchange decorator patterns
- [Patterns/Workflow Patterns](Patterns/Workflow-Patterns.md) — State machine pattern via hr.recruitment.stage
