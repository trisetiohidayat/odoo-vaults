---
type: flow
title: "Employee Transfer Flow"
primary_model: hr.employee
trigger: "User action — Employee → Change Department"
cross_module: true
models_touched:
  - hr.employee
  - hr.department
  - resource.resource
  - res.users
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/HR/employee-creation-flow](employee-creation-flow.md)"
  - "[Flows/HR/employee-archival-flow](employee-archival-flow.md)"
source_module: hr
created: 2026-04-07
version: "1.0"
---

# Employee Transfer Flow

## Overview

The employee transfer flow moves an employee from one department to another, cascading that change through the resource calendar, system user account, project memberships, and timesheet history. If a transfer approval policy is configured via `hr.transfer.model`, the flow gates the actual department change behind a multi-level approval process. The flow ensures referential integrity across `hr.employee`, `resource.resource`, `res.users`, and `account.analytic.line` by propagating the `department_id` write through all related records.

## Trigger Point

**User action:** An HR Manager navigates to *Employees*, opens an employee form, clicks the **Department** smart button or edits `department_id` directly on the form.

Alternative triggers:
- **Bulk action:** *HR > Employees > Actions > Transfer Employees* — batch transfer of multiple employees via `hr.employee.transfer()` wizard.
- **Approval workflow:** `hr.transfer.request.action_validate()` — approved transfer request writes the actual department change.
- **Contract state change:** A contract activation that references a new department auto-suggests a transfer.
- **Department merge/close:** Closing a department triggers `hr.employee._change_department()` for all members.

---

## Complete Method Chain

```
1. hr.employee.write({'department_id': new_dept_id})
   │
   ├─► 2. @api.onchange('department_id')  [form-level, optional]
   │     └─► 3. hr.employee._get_user_employee()
   │           └─► Validates employee linked to current user context
   │
   ├─► 4. hr.employee._change_department()
   │     ├─► 5. IF hr.transfer.model exists:
   │     │      └─► 6. hr.transfer.request.create({
   │     │              employee_id: self.id,
   │     │              department_id: new_dept_id,
   │     │              state: 'draft'
   │     │            })
   │     │            └─► 7. mail.mail sent to manager for approval
   │     │                  └─► hr.transfer.request notified
   │     │
   │     └─► 8. ELSE (no transfer model):
   │            └─► 9. Immediate transfer — direct write()
   │                  └─► 10. resource.resource.write({'department_id': new_dept_id})
   │                        └─► 11. res.users.write({'department_id': new_dept_id})
   │                              via employee_id.user_id
   │
   ├─► 12. hr.department.manager_id recalculation
   │     └─► OLD dept: manager_id recomputed (old manager removed)
   │     └─► NEW dept: manager_id recomputed (new manager added)
   │           └─► 13. hr.job._compute_employee_count()
   │                 └─► hr.job.department_id  → opening count updated
   │
   ├─► 14. IF auto_assign_by_department is True:
   │      └─► 15. project.project.write({'member_ids': [...]})
   │            └─► Employee added to department-linked projects
   │
   └─► 16. account.analytic.line.write({'department_id': new_dept_id})
         └─► 17. Timesheet history retroactively tagged with new dept

18. hr.transfer.request.action_validate()  [approval path only]
    └─► 19. hr.employee.write({'department_id': new_dept_id})
          └─► Steps 10-17 re-executed
                └─► 20. Transfer history logged in hr.employee.history_ids

21. hr.transfer.request.action_reject()  [rejection path]
    └─► Transfer cancelled, employee remains in original department
```

---

## Decision Tree

```
Transfer initiated (department_id changed)
│
├─► Same department selected?
│  ├─► YES  →  Error: "Employee is already in this department"
│  └─► NO ↓
│
├─► hr.transfer.model configured for this company?
│  │
│  ├─► YES  →  hr.transfer.request.create()  →  draft request created
│  │    └─► 21. Approval workflow triggered
│  │         ├─► APPROVED  →  action_validate()  →  department written
│  │         └─► REJECTED  →  action_reject()  →  transfer cancelled
│  │
│  └─► NO  (direct transfer)
│       └─► Immediate department write
│            │
│            ├─► User/Partner cascade:
│            │    └─► res.users.write({'department_id': new_dept_id})
│            │         └─► res.partner cascades via _inherits
│            │
│            ├─► Resource calendar:
│            │    └─► resource.resource.write({'department_id': new_dept_id})
│            │
│            ├─► Department manager update:
│            │    └─► hr.department.manager_id recomputed
│            │         └─► hr.job._compute_employee_count()
│            │
│            ├─► Project membership?
│            │    └─► YES  →  project.project member_ids updated
│            │         └─► Employee added to new dept's projects
│            │
│            └─► Timesheet history:
│                 └─► account.analytic.line.write() retroactively tagged
│                      └─► Done  →  Transfer complete
│
└─► Active contract in original department?
     ├─► YES  →  Warning: "Active contract belongs to another department"
     │         └─► Contract change recommended before or after transfer
     └─► NO ↓
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `hr_employee` | Updated | department_id, department_changed_date, active |
| `hr_transfer_request` | Created (approval path) | employee_id, department_id, state, approver_id |
| `resource_resource` | Updated | department_id (mirrors employee) |
| `res_users` | Updated | department_id (via employee_id.user_id) |
| `hr_department` | Recomputed | manager_id recalculated for old + new dept |
| `hr_job` | Recomputed | employee_count, no_of_employee updated |
| `project_project` | Updated (if auto-assign) | member_ids added/removed |
| `account_analytic_line` | Updated (timesheet history) | department_id retroactively tagged |
| `hr_employee_history` | Created | transfer date, old dept, new dept, user who initiated |
| `mail_mail` | Created | notification to old + new department managers |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| No department selected | `ValidationError` | `required=True` on `department_id` in transfer wizard |
| Same department as current | `UserError` | `_check_department_change()` validation |
| User not linked to employee | `UserError` | `employee_id.user_id` is False — cannot cascade write |
| Active contract belongs to another dept | `UserError` | Contract's `department_id` conflicts with transfer |
| Project access revoked after transfer | `AccessError` | Employee loses access to old project timesheets |
| Transfer request already pending | `UserError` | Duplicate `hr.transfer.request` with state='draft' blocked |
| No manager in new department | `Warning` (soft) | New dept has no manager_id — notification skipped |
| Approval rejected | `UserError` | `action_reject()` raises with rejection reason |
| HR Manager ACL missing | `AccessError` | `group_hr_manager` required for direct transfer |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Department manager recomputed | `hr.department` | `manager_id` recalculated via `_compute_manager_id` for both old and new dept |
| Job headcount updated | `hr.job` | `no_of_employee` and `employee_count` recomputed per department |
| Employee history logged | `hr.employee.history` | Transfer date, old/new dept, initiator, reason recorded |
| User department updated | `res.users` | Cascaded write via `employee_id.user_id` — user's department context changes |
| Project membership adjusted | `project.project` | If `auto_assign_by_department` on project: member added/removed |
| Timesheet history tagged | `account.analytic.line` | Retroactively written `department_id` for reporting accuracy |
| Manager notification sent | `mail.mail` | Old manager notified of departure; new manager notified of arrival |
| Approval request created | `hr.transfer.request` | Multi-level approvers notified via `mail.mail` |
| Resource calendar unchanged | `resource.resource` | Calendar (working hours) does NOT change — only department tag |
| Payroll impact | `hr.payslip` | Future payslips use new department cost center if configured |

---

## Security Context

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `hr.employee.write({'department_id': ...})` | Current user | `group_hr_manager` | Only HR managers can transfer |
| `_change_department()` | `sudo()` internally | System (cross-model writes) | Writes to resource.resource, res.users |
| `hr.transfer.request.create()` | Current user | `group_hr_manager` | Creates draft request |
| `action_validate()` | Current user | `group_hr_manager` or approver | Approval-level security |
| `res.users.write()` | `sudo()` via _inherits | System (bypasses ACL) | Cascaded from employee transfer |
| `account.analytic.line.write()` | Current user | `group_hr_user` or `group_project_user` | Bulk update on timesheet lines |
| `project.project.write({'member_ids': ...})` | Current user | `group_project_manager` | Project-level security |
| `mail.mail` notification | `mail.group` | Public | Follower-based; manager subscribed to dept |
| `hr.job._compute_employee_count()` | `sudo()` internally | System (read-only department access) | Computed field recalc |

**Key principle:** The transfer write (`_change_department()`) uses `sudo()` internally for the resource and user cascade because an HR manager writing an employee transfer may not have direct write access to `res.users` records. The `account_analytic_line` bulk write runs under the current user's ACL — if the user lacks access to some historical timesheets, those lines are silently skipped via record rule filtering.

---

## Transaction Boundary

```
Steps 1-3   ✅ INSIDE transaction  — initial write / onchange
Steps 4-11  ✅ INSIDE transaction  — _change_department cascade
Steps 12-17 ✅ INSIDE transaction  — dept manager, job, project, timesheet bulk write
Steps 18-20 ✅ INSIDE transaction  — approval validation + final write
Step 7      ❌ OUTSIDE transaction — mail.mail notification (async queue)
Step 21     ❌ OUTSIDE transaction — mail.mail rejection notification
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| `hr.employee.write()` + cascade | ✅ Atomic | Full rollback on any error (department, user, resource) |
| `hr.job._compute_employee_count()` | ✅ Atomic | Computed field recomputed within tx |
| `project.project.write()` | ✅ Atomic | Project membership updated or rolled back |
| `account.analytic.line.write()` (bulk) | ✅ Atomic | All lines updated or all rolled back |
| `hr.transfer.request.create()` | ✅ Atomic | Request created within same tx |
| `mail.mail` notification | ❌ Async queue | Mail queued; transfer still committed even if mail fails |
| `mail.mail` approval notification | ❌ Async queue | Approval email sent separately; rejection does not block |

**Rule of thumb:** All ORM writes in `_change_department()` are inside the same DB transaction — the employee, resource, and user all update atomically. The `mail.mail` queue is the only true outside-of-tx effect. If the approval request validation fails, the entire transfer (including the initial request creation) rolls back.

---

## Idempotency

| Scenario | Behavior |
|----------|----------|
| Double-click Transfer button | Two `write()` calls with same `department_id` — second is a no-op (no error, no change) |
| Re-approve already approved transfer | `action_validate()` checks `state != 'approved'` — raises `UserError` |
| Transfer same employee twice in quick succession | First transfer completes; second raises "Employee already transferred" |
| Approve a rejected request | `action_validate()` checks `state == 'approved'` — no-op or raise depending on code path |
| Bulk transfer: one fails mid-batch | Full rollback of entire batch (atomic write across recordset) |
| `account.analytic.line.write()` re-run on already-updated lines | `write()` re-runs with same values — no-op at DB level |
| HR Manager edits employee dept while transfer request pending | Raises `UserError` — pending request blocks concurrent edits |

**Common patterns:**
- **Idempotent:** `write()` with same `department_id`, `action_reject()`, `action_validate()` (with state guard)
- **Non-idempotent:** `hr.transfer.request.create()` (new record each time), `mail.mail` notifications, `hr.employee.history` log entries
- **Deduplication strategy:** Implement a state check in `_change_department()` or use a lock on `hr.transfer.request` to prevent concurrent transfer requests for the same employee.

---

## Extension Points

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 4 | `_change_department()` | Custom transfer logic before write | self, new_dept_id | Extend with `super()`, add pre-write logic |
| Step 5 | `hr.transfer.model` policy | Custom approval routing | self | Override to add multi-level approval rules |
| Step 10 | `resource.resource.write()` | Custom resource update | vals | Extend via `_change_department()` override |
| Step 11 | `res.users.write()` | Custom user update | vals | Extend via `_change_department()` override |
| Step 15 | `project.project` member logic | Auto-assign project rules | self, employee | Override to add custom project assignment |
| Step 16 | `account.analytic.line.write()` | Custom timesheet tagging | vals | Extend via `_change_department()` override |
| Step 20 | `hr.employee.history` logging | Custom history fields | self, old_dept, new_dept | Override `action_validate()` to inject history |
| Validation | `_check_department_change()` | Block invalid transfers | self | Add `@api.constrains('department_id')` |

**Standard override pattern:**
```python
# WRONG — replaces entire method
def _change_department(self):
    # your code

# CORRECT — extends with super()
def _change_department(self, new_dept_id):
    res = super()._change_department(new_dept_id)
    # your additional logic (project re-assignment, custom logging)
    self._update_custom_cost_center(new_dept_id)
    return res
```

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct `_workflow` calls (deprecated — use `action_*` methods)
- Overriding `write()` without calling `super()` first (breaks cascade)

---

## Reverse / Undo Flow

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `write({'department_id': new})` | `write({'department_id': old})` | Re-run transfer back to original dept | Creates another transfer history entry; both transfers logged |
| `hr.transfer.request` approved | `action_cancel()` | Cancels active request only | Cannot cancel an already-validated transfer |
| Transfer history entry | NOT reversible | Created automatically | Audit trail is append-only |
| Project membership added | `project.project.write({'member_ids': [(3, employee_id)]})` | Remove member manually | Must be done separately from employee transfer |
| Timesheet department retro-tag | `write({'department_id': old_dept})` | Restore old dept on timesheets | Manual write on `account_analytic_line` |
| `res.users` dept updated | `write({'department_id': old})` | Restore via `res.users` form | Cascaded from employee re-transfer |

**Important:** The transfer history (`hr.employee.history`) is **append-only** — transfer records cannot be deleted. Re-transferring an employee back to the original department creates a second history entry. The timesheet retro-tagging (`account.analytic.line.write()`) is also a forward-only update — there is no automatic rollback of historical timesheets on reverse transfer.

---

## Alternative Triggers

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | Employee form `department_id` edit | Interactive | Manual |
| User action | Transfer wizard | Interactive batch | Manual |
| Approval workflow | `action_validate()` button | HR Manager approval | On demand |
| Department close | `hr.department.action_close()` | Closure of department | Manual |
| Department merge | `hr.department.merge()` | Merge two departments | Manual |
| Contract activation | `hr.contract.actionactivate()` | Contract references new dept | On contract state change |
| API / External | `hr.employee.write()` via XML-RPC | External HRIS sync | On demand |
| Automated action | `base.automation` | Rule triggered (e.g., end of project) | On rule match |

**For AI reasoning:** The transfer flow is fundamentally a `write()` on `department_id`, but the `_change_department()` method is the critical extension point. Always check for an active `hr.transfer.request` in state='draft' before allowing a direct write — the approval model gates writes for companies that enforce it. Also note that `account.analytic.line` updates are a **bulk retroactive tag** and do NOT trigger timesheet re-validation.

---

## Related

- [Modules/HR](HR.md) — HR module reference
- [Modules/Project](Project.md) — Project module reference
- [Modules/Account](Account.md) — Account module reference
- [Flows/HR/employee-creation-flow](employee-creation-flow.md) — Employee creation flow
- [Flows/HR/employee-archival-flow](employee-archival-flow.md) — Employee archival flow
- [Patterns/Workflow Patterns](Workflow Patterns.md) — Workflow pattern reference
- [Core/API](API.md) — @api decorator patterns
