---
type: flow
title: "Contract Lifecycle Flow"
primary_model: hr.contract
trigger: "User action — HR → Contracts → Create / Renew / Terminate"
cross_module: true
models_touched:
  - hr.contract
  - hr.employee
  - hr.version
  - resource.resource
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/HR/employee-creation-flow](Flows/HR/employee-creation-flow.md)"
  - "[Flows/HR/employee-archival-flow](Flows/HR/employee-archival-flow.md)"
related_guides:
  - "[Business/HR/quickstart-employee-setup](Business/HR/quickstart-employee-setup.md)"
source_module: hr_contract
source_path: ~/odoo/odoo19/odoo/addons/hr_contract/
created: 2026-04-07
updated: 2026-04-07
version: "1.0"
---

# Contract Lifecycle Flow

## Overview

Managing the full employee contract lifecycle — creation from template or manual entry, renewal with new dates, amendment via version tracking, and termination with offboarding. Each contract state transition triggers version history, calendar updates, and HR activity scheduling.

## Trigger Point

Three main entry points:
- **Create:** `hr.contract.create(vals)` — via form or employee wizard
- **Renew:** `hr.contract.action_renew()` — button on existing contract
- **Terminate:** `hr.contract.action_terminate()` — button on active contract

---

## Complete Method Chain

### CREATE Contract

```
1. hr.contract.create(vals)
   │
   ├─► 2. IF contract_template_id in vals:
   │      └─► 3. _onchange_contract_template_id()
   │            └─► 4. wage, benefits, type auto-filled from template
   │                  └─► 5. structure_type_id, contract_type_id set
   │
   ├─► 6. _onchange_employee_id()
   │      └─► 7. Fill department_id, job_id, resource_calendar_id from employee
   │            └─► 8. IF employee has existing contract:
   │                  └─► 9. Suggest default values from current version
   │
   ├─► 10. _onchange_structure_type()
   │       └─► 11. Fill default resource_calendar from structure type
   │
   ├─► 12. _onchange_resource_calendar()
   │       └─► 13. Working hours propagated to resource.resource
   │             └─► 14. employee.resource_calendar_id updated
   │
   ├─► 15. IF wage_type = 'monthly':
   │       └─► 16. wage field populated, hourly_wage computed
   │
   ├─► 17. IF wage_type = 'hourly':
   │       └─► 18. hourly_wage field populated, wage computed
   │
   └─► 19. Contract state = 'draft' (default on create)
         └─► 20. activity scheduled for trial end review
               └─► 21. IF trial_date_end set:
                     └─► mail.activity created for HR manager
               └─► 22. calendar event created for contract start date
                     └─► 23. activity scheduled for contract end review
                           └─► 24. IF date_end set:
                                 └─► mail.activity created N days before end
         └─► 25. hr.version created automatically (by employee model)
               └─► contract_date_start set on version
               └─► is_current = True (if first version)
```

### RENEW Contract (action_renew)

```
1. hr.contract.action_renew()
   │
   ├─► 2. Wizard opens (date_start, date_end for new contract)
   │      └─► 3. User fills new period dates
   │
   ├─► 4. hr.contract.create(vals)
   │      └─► same onchanges as CREATE (steps 2-25 above)
   │            └─► 5. New contract created with state = 'draft'
   │
   ├─► 6. old_contract.write({'state': 'close'})
   │      └─► 7. contract_date_end = new_start_date - 1 day
   │            └─► 8. old_version.is_past = True
   │            └─► 9. new_version created
   │                  └─► 10. new_version.is_current = True
   │                        └─► 11. new_version.contract_date_start = new_date_start
   │
   └─► 12. Activity created for new contract start
         └─► 13. HR manager notified of upcoming renewal
```

### TERMINATE Contract (action_terminate)

```
1. hr.contract.action_terminate()
   │
   ├─► 2. Wizard opens (termination_date, reason, offboarding checklist)
   │      └─► 3. User enters termination_date
   │
   ├─► 4. contract.write({
   │         'state': 'close',
   │         'date_end': termination_date
   │      })
   │      └─► 5. hr.version.contract_date_end updated
   │            └─► 6. hr.version.is_past = True
   │
   ├─► 7. IF employee has other active contracts:
   │      └─► 8. employee stays active with other contract
   │
   ├─► 9. ELSE (no other active contracts):
   │      └─► 10. hr.employee.action_archive() recommended
   │            └─► 11. offboarding activities triggered
   │                  └─► 12. exit interview scheduled
   │                  └─► 13. equipment return checklist
   │                  └─► 14. access revocation activity
   │
   └─► 15. Calendar event created for last working day
         └─► 16. HR notified of termination
```

---

## Decision Tree

```
Contract action initiated
│
├─► CREATE from template?
   ├─► YES → Auto-fill all fields from template
   │         └─► Employee linked, calendar updated, version created
   ├─► NO → CREATE manually
            └─► User enters all fields
            └─► Onchanges cascade to fill related fields
            └─► Version created on save
│
├─► RENEW contract?
   ├─► YES → New contract created from template
   │         └─► Old contract state → 'close'
   │         └─► New version is_current = True
   │         └─► Old version is_past = True
   ├─► NO → Continue
│
├─► AMEND contract (no new contract)?
   ├─► YES → New version created (amendment)
   │         └─► Contract remains same
   │         └─► is_past = True on old version
   │         └─► is_current = True on new version
   ├─► NO → Continue
│
├─► TERMINATE contract?
   ├─► YES → state = 'close'
   │         └─► date_end = termination_date
   │         └─► Check for other active contracts
   │              ├─► Has other contracts → employee stays active
   │              └─► No other contracts → recommend archival
   └─► NO → Save as draft or open
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `hr_contract` | Created (new) or Updated (renew/terminate) | name, employee_id, date_start, date_end, state, wage |
| `hr_version` | Created (new) or Updated (renew/amend) | is_current, is_past, contract_date_start, contract_date_end |
| `hr_employee` | Updated (calendar, version link) | resource_calendar_id, current_version_id |
| `resource_resource` | Updated (working hours) | calendar_id |
| `mail_activity` | Created (trial end, contract end reviews) | activity_type_id, user_id, date_deadline |
| `calendar_event` | Created (start/end calendar events) | name, start_date, partner_ids |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Overlapping contracts for same employee | `ValidationError` | Date range overlap check |
| Start date after end date | `ValidationError` | Contract date validation |
| Missing required employee_id | `ValidationError` | ORM `required=True` |
| Renew already-closed contract | `UserError` | "Cannot renew a closed contract" |
| Terminate already-closed contract | `UserError` | "Contract is already terminated" |
| Create contract for archived employee | `UserError` | "Employee is archived — unarchive first" |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Version created | `hr.version` | New version record with is_current=True |
| Old version marked past | `hr.version` | is_past=True, is_current=False |
| Calendar updated | `resource.resource` | Working hours synced to resource |
| Activity scheduled | `mail.activity` | Trial end review, contract end review |
| Employee state updated | `hr.employee` | Presence state may change on termination |
| Department headcount | `hr.department` | total_employee recomputed |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `hr.contract.create()` | Current user | `group_hr_manager` | HR manager creates contracts |
| `_onchange_*()` | Current user | Read ACL | Onchange runs as current user |
| `action_renew()` | Current user | `group_hr_manager` | Manager-level action |
| `action_terminate()` | Current user | `group_hr_manager` | Manager-level action |
| `hr.version.create()` | `sudo()` | System (internal) | Internal model write |
| `hr.employee.action_archive()` | Current user | `group_hr_manager` | Only if terminating sole contract |

**Key principle:** Contract creation and modification require `group_hr_manager`. Self-service employees cannot create their own contracts.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside.*

```
Steps 1-25 (Create)     ✅ INSIDE transaction  — atomic
Steps 1-13 (Renew)      ✅ INSIDE transaction  — atomic
Steps 1-16 (Terminate)  ✅ INSIDE transaction  — atomic
Activity scheduling     ✅ INSIDE transaction  — via ORM
Mail notifications      ❌ OUTSIDE transaction — via mail queue
Offboarding tasks       ❌ OUTSIDE transaction — via activity queue
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Contract create/write | ✅ Atomic | Rollback on any error |
| Version create/update | ✅ Atomic | Rolled back with contract |
| Activity creation | ✅ Within ORM | Rolled back with transaction |
| Mail notification | ❌ Async queue | Retried by `ir.mail.server` cron |
| Offboarding external tasks | ❌ Async | Handled separately |

**Rule of thumb:** All contract and version records are created atomically. Calendar events and notifications are queued asynchronously.

---

## Idempotency

> *What happens when this flow is executed multiple times.*

| Scenario | Behavior |
|----------|----------|
| Double-click Create button | Only one contract created — ORM deduplicates |
| Re-save contract with same values | `write()` re-runs, no error, version not recreated |
| Re-trigger renew on same contract | Error — contract already closed |
| Duplicate date range on renew | `ValidationError` — overlapping contract dates |
| Re-terminate already closed contract | Error — "Contract is already terminated" |

**Common patterns:**
- **Idempotent:** Create (only one record per vals), Write (re-runs without error)
- **Non-idempotent:** Version creation (each renewal creates a new version record), Activity creation (one per deadline)

---

## Extension Points

> *Where and how developers can override or extend this flow.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 4 | `_onchange_contract_template_id()` | Custom template field mapping | self | Add field sync after `super()` |
| Step 7 | `_onchange_employee_id()` | Sync additional fields from employee | self | Extend with `super()` call |
| Step 15-18 | Wage computation | Custom wage calculation (allowances, deductions) | vals | Override in `create()` before `super()` |
| Step 20 | Trial end activity | Custom activity type for trial review | self | Extend activity creation |
| Post-create | Post-contract hook | Custom logic after contract created | self | Extend via `create()` override |
| Renew | `action_renew()` | Custom renewal process (probation, approval) | self | Extend with `super()` call |

**Standard override pattern:**
```python
# CORRECT — extends with super()
def _onchange_contract_template_id(self):
    result = super()._onchange_contract_template_id()
    # custom field sync, additional benefits, etc.
    return result

# CORRECT — extend create
def create(self, vals):
    # pre-processing
    contract = super().create(vals)
    # post-processing (activities, custom fields)
    return contract
```

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct workflow calls (deprecated — use `action_*` methods)
- Overriding `write()` to bypass state machine — use `action_*` methods instead

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| Create contract | `unlink()` | `contract.unlink()` | Only if state='draft' and no version history |
| Renew (new contract) | `unlink()` new contract | `new_contract.unlink()` | Only if not yet open; old contract reactivated manually |
| Amendment version | Revert is_current | `old_version.action_activate()` | Current version can be switched back |
| Terminate | Reopen contract | `contract.write({'state': 'open'})` | HR manager only; audit trail preserved |
| Cancel termination | Cancel offboarding | Cancel activities, keep contract open | Depends on offboarding stage |

**Important:**
- Contracts can be set back to 'draft' from 'open' (not from 'close')
- Closing a contract is not fully reversible — termination_date and is_past flags remain in history
- Amendment versions can be swapped by setting `is_current=True` on a different version
- Full undo of termination requires HR manager with audit trail review

---

## Alternative Triggers

> *All the ways this flow can be initiated.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `hr.contract.create()` button | Interactive form | Manual |
| User action | `action_renew()` button | Contract form | Manual |
| User action | `action_terminate()` button | Contract form | Manual |
| Onchange cascade | `_onchange_*()` | Field change | On demand |
| Wizard | `hr.contract.sign.wizard` | Employee signing contract | Manual |
| Automated action | `base.automation` | Contract end approaching | Daily cron |
| Employee promotion | Promotion wizard | New contract with higher wage | Manual |

**For AI reasoning:** When asked "what happens to the employee when a contract is renewed?", trace through the version history and state transitions.

---

## Related

- [Modules/HR](Modules/HR.md) — HR module reference (includes hr_contract section)
- [Modules/resource](Modules/resource.md) — resource.resource, resource.calendar
- [Flows/HR/employee-creation-flow](Flows/HR/employee-creation-flow.md) — Employee creation
- [Flows/HR/employee-archival-flow](Flows/HR/employee-archival-flow.md) — Archival on termination
- [Patterns/Workflow Patterns](Patterns/Workflow-Patterns.md) — State machine pattern reference
- [Core/API](Core/API.md) — @api decorator patterns