---
type: flow
title: "Timesheet Submission Flow"
primary_model: account.analytic.line
trigger: "User action — Timesheet → Add Line"
cross_module: true
models_touched:
  - account.analytic.line
  - project.project
  - project.task
  - sale.order.line
  - hr.employee
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Cross-Module/employee-projects-timesheet-flow](Flows/Cross-Module/employee-projects-timesheet-flow.md)"
  - "[Flows/Project/task-lifecycle-flow](Flows/Project/task-lifecycle-flow.md)"
source_module: hr_timesheet
created: 2026-04-07
version: "1.0"
---

# Timesheet Submission Flow

## Overview

The timesheet submission flow captures time spent by employees on projects and tasks, linking those entries to billing, payroll, and invoicing systems. Each `account.analytic.line` record represents a discrete time slice with a date, duration, and project/task assignment. The flow branches at billing type — manual, milestone-based, or fixed price — to determine whether and how the timesheet is linked to a sale order line for downstream invoice generation.

## Trigger Point

**User action:** A user navigates to *Timesheet* (or *Project > Timesheets*) and clicks **Add Line** or edits a grid cell. This opens a form populated with the current employee's default values and the current week's dates.

Alternative triggers:
- **Auto-entry cron** (`account.analytic.line._cron_sync_timesheets`): Syncs external timers (e.g., imported from a third-party app).
- **Project/task onchange cascade**: Changing the project or task auto-populates product_id, employee_id, and billing fields.
- **API/External sync**: `account.analytic.line.create()` called via XML-RPC from an external system.

---

## Complete Method Chain

```
1. account.analytic.line.create(vals)
   │
   ├─► 2. @api.model_create_multi
   │     └─► record written to account_analytic_line
   │           └─► 3. _onchange_project_id()  [onchange, step 1]
   │                 ├─► project_id.project_task_ids  → suggested task list
   │                 ├─► project_id.billing_type  → determines billing branch
   │                 └─► project_id.timesheet_product_id  → product_id pre-filled
   │                       └─► 4. _onchange_task_id()  [onchange, step 2]
   │                             ├─► task_id.user_id  → employee linked
   │                             ├─► task_id.product_id  → product_id override
   │                             └─► 5. _timesheet_determine_values()  [sale.order.line]
   │
   ├─► 6. IF billing_type == 'manual':
   │      └─► 7. account.analytic.line.write({'so_line': False})
   │            └─► 8. allow_billable project → line stays unbilled
   │
   ├─► 9. ELIF billing_type == 'milestone':
   │      └─► 10. sale.order.line.set_timesheet_line_ids()
   │            └─► 11. sale.order.line._timesheet_determine_values()
   │                  ├─► milestone_id set from SOL
   │                  └─► 12. _update_sale_line()  [self]
   │
   ├─► 13. ELIF billing_type == 'fixed':
   │      └─► 14. sale.order.line.set_timesheet_line_ids()
   │            └─► 15. _update_sale_line()
   │                  ├─► so_line.so_amount  recalculated
   │                  └─► 16. project_id._get_analytic_account()
   │
   └─► 17. hr.employee._get_user_employee()
         └─► 18. employee_id.linked to line
               └─► 19. _validate_timesheet()
                     ├─► no overlapping entries for same employee+date
                     └─► hours within configured working_hours per day

20. account.analytic.line.write({'amount': updated_amount})
    └─► 21. _update_sale_line()
          └─► 22. IF so_line: so_line.write({'qty_delivered': qty_delivered})

23. sale.order._create_invoices()
    └─► 24. account.move created from SOL (billed from timesheet qty)
```

---

## Decision Tree

```
Timesheet line entered (Add Line)
│
├─► project_id selected?
│  ├─► NO  →  Error: "A project is required to submit a timesheet"
│  └─► YES ↓
│
├─► task_id selected?
│  ├─► NO  →  task_ids suggested from project  (optional step)
│  └─► YES ↓
│
├─► employee_id linked?
│  ├─► NO  →  hr.employee._get_user_employee()  (auto-lookup from current user)
│  │         └─► still NO  →  Error: "No employee found for current user"
│  └─► YES ↓
│
├─► billing_type on project?
│  │
│  ├─► 'manual'  (allow_billable=True, billing_type='manual')
│  │    └─► Line stays unbilled  → Manual Invoice trigger available
│  │
│  ├─► 'milestone'  (project linked to sale.order with milestones)
│  │    └─► sale.order.line._timesheet_determine_values()
│  │         └─► milestone_id assigned  → Line linked to SOL milestone
│  │
│  └─► 'fixed'  (project linked to sale.order, fixed price)
│       └─► sale.order.line.set_timesheet_line_ids()
│            └─► SOL qty_delivered updated
│
├─► Overlap check: _validate_timesheet()
│  ├─► CONFLICT  →  Error: "Overlapping timesheet entry exists"
│  └─► OK ↓
│
├─► Hours validation: within working_hours per day?
│  ├─► NO  →  Warning (soft block, not hard error in standard Odoo)
│  └─► YES ↓
│
└─► Line saved to account_analytic_line
     │
     ├─► Already invoiced?  (so_line already billed in posted invoice)
     │    ├─► YES  →  Error: "Cannot modify an invoiced timesheet line"
     │    └─► NO  ↓
     │
     └─► SO → Invoiced state?
          └─► YES  →  sale.order._create_invoices()  → account.move created
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `account_analytic_line` | Created | name, unit_amount, date, project_id, task_id, employee_id, so_line, company_id |
| `project_project` | Read (no write) | allow_billable, billing_type, timesheet_product_id |
| `project_task` | Read (no write) | user_id, project_id, bill_count |
| `sale_order_line` | Updated | qty_delivered, timesheet_line_ids, milestone_id |
| `sale_order` | Read (no write) | invoice_status, state |
| `account_move` | Created (on invoice) | line_ids, invoice_origin referencing SO |
| `hr_employee` | Read | employee_id resolved from user |
| `resource_resource` | Read | employee_id linked to hr.employee via _inherits |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| No project selected | `ValidationError` | ORM `required=True` on `project_id` for timesheet group |
| Task not in selected project | `ValidationError` | `_check_task_in_project()` via task_id domain constraint |
| Employee not linked to user | `UserError` | `hr.employee._get_user_employee()` returns False |
| Overlapping timesheet entries | `ValidationError` | `_validate_timesheet()` checks (employee_id, date) overlap |
| Negative hours entered | `ValidationError` | `unit_amount >= 0` enforced in `create()` |
| Already invoiced line modified | `UserError` | Line's `so_line` linked to posted invoice — write blocked |
| Project not billable | `Warning` (soft) | allow_billable=False — no SO link created, no invoice impact |
| No access to project | `AccessError` | project.project record rules restrict visibility |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| SOL qty_delivered updated | `sale.order.line` | `write({'qty_delivered': ...})` — accumulates billable hours |
| Milestone hours tracked | `sale.order.line` | `milestone_id` linked — triggers milestone completion logic |
| Employee timesheet count | `project_task` | `timesheet_count` computed field incremented |
| Manager notification | `mail.mail` | Queued notification if timesheet needs approval |
| Project billing status | `project_project` | `billable_percentage` recomputed |
| Payroll hours consumed | `hr.employee` | `total_timesheet_hours` updated for payroll reporting |
| Working hours validation | `resource.calendar` | `attendance_ids` checked against `unit_amount` per day |

---

## Security Context

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `create()` | Current user | `group_hr_user` or `group_project_user` | Respects record rules on project |
| `_onchange_project_id()` | Current user | Read ACL on `project.project` | Populates suggestion; silent skip on no access |
| `_onchange_task_id()` | Current user | Read ACL on `project.task` | Task filtered to project |
| `_validate_timesheet()` | Current user | Read ACL on own `account.analytic.line` | Only validates own entries |
| `_update_sale_line()` | `sudo()` internally | System (bypasses ACL for SOL write) | Only when `so_line` set |
| `sale.order._create_invoices()` | Current user | `group_salesalesman` or `group_account_invoice` | Requires SO access |
| `hr.employee._get_user_employee()` | `sudo()` internally | System (cross-user lookup) | Looks up by `user_id = context.uid` |
| `mail.mail` notification | `mail.group` | Public | Follower-based; respects channel ACL |

**Key principle:** The flow runs as the **current logged-in user**. Onchange methods are purely UI-driven and skip silently on access errors. The SOL link write (`_update_sale_line`) internally uses `sudo()` because the timesheet user may not have direct write access to the SOL from a linked SO.

---

## Transaction Boundary

```
Steps 1-5   ✅ INSIDE transaction  — atomic create() / onchange cascade
Steps 6-12  ✅ INSIDE transaction  — branching write / SOL link update
Step 13-15  ✅ INSIDE transaction  — SOL qty_delivered write
Step 19     ✅ INSIDE transaction  — _validate_timesheet() check
Steps 20-22 ✅ INSIDE transaction  — amount update / SOL write
Step 23     ❌ OUTSIDE transaction — sale.order._create_invoices()
               Creates account.move record outside current tx
               Failure after SOL write committed → partial state
Step 24     ❌ OUTSIDE transaction — account.move posting (if auto-posted)
Mail notify ❌ OUTSIDE transaction — via mail.mail queue (fire-and-forget)
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| `create()` + onchanges | ✅ Atomic | Full rollback on any error |
| `_validate_timesheet()` | ✅ Atomic | Rollback if overlap detected |
| `_update_sale_line()` | ✅ Atomic | Rollback if SOL write fails |
| `sale.order._create_invoices()` | ❌ Outside tx | Invoice creation failure does NOT rollback timesheet |
| `mail.mail` notification | ❌ Async queue | Retried by `ir.mail.server` cron |

**Rule of thumb:** All ORM writes inside `create()`/`write()` are inside the transaction. Explicit `action_*()` calls that reach `sale.order._create_invoices()` cross the transaction boundary — if invoice generation fails after the timesheet is committed, the timesheet stays saved but remains uninvoiced.

---

## Idempotency

| Scenario | Behavior |
|----------|----------|
| Double-click Add Line button | Two separate `create()` calls → two records created (not deduplicated at ORM level — use JS button disabling to prevent) |
| Re-save line with same values | `write()` re-runs `_update_sale_line()` with identical values — no error, SOL unchanged |
| Re-trigger `_validate_timesheet()` on saved record | No-op if entry passes validation |
| Timesheet line already linked to posted invoice | `write()` raises `UserError` — idempotent blocking |
| `sale.order._create_invoices()` called twice | First call creates invoice; second call raises "Invoice already exists for this order" or creates duplicate (configure `uom_pricelist` uniqueness to prevent) |
| Onchange called via API | `_onchange_*()` methods are NOT idempotent at API level — same input always produces same output, but side effects (suggestion population) are not persisted until `create()` |

**Common patterns:**
- **Idempotent:** `create()` (unique records), `write()` (re-running with same vals is a no-op on DB), `_validate_timesheet()` (stateless check)
- **Non-idempotent:** `sale.order._create_invoices()` (creates financial records), SOL `qty_delivered` increment (state accumulates)
- **Deduplication strategy:** Use a unique constraint on `(employee_id, date, project_id, task_id, unit_amount)` or implement a lock-check in `create()` to prevent duplicate time slices.

---

## Extension Points

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 3 | `_onchange_project_id()` | Custom task suggestion, product override | self | Extend with `super()`, add domain filter |
| Step 4 | `_onchange_task_id()` | Custom billing amount logic | self | Add field sync after `super()` |
| Step 5 | `sale.order.line._timesheet_determine_values()` | Add milestone/analytic defaults | self | Extend with `super()`, inject custom vals |
| Step 12/15 | `_update_sale_line()` | Custom SO link behavior | self | Override to add custom billing rules |
| Step 19 | `_validate_timesheet()` | Custom validation (e.g., overtime rules) | self | Add `@api.constrains` or extend method |
| Pre-create | `create()` vals processing | Inject default employee, project defaults | vals | Extend `create()` with `super()` |
| Step 23 | `sale.order._create_invoices()` | Custom invoice generation logic | self, group_by_project | Override `_create_invoices()` group behavior |

**Standard override pattern:**
```python
# WRONG — replaces entire method
def _onchange_project_id(self):
    # your code

# CORRECT — extends with super()
def _onchange_project_id(self):
    res = super()._onchange_project_id()
    # your additional field sync
    self.product_id = self.project_id.custom_product_id
    return res
```

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct `_workflow` calls (deprecated — use `action_*` methods)
- Overriding `create()` without calling `super()` first

---

## Reverse / Undo Flow

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `create()` line | `unlink()` | `record.unlink()` | Reverses SOL qty_delivered update; cascade unlinks from SOL if set |
| Line → SOL link | Break link | `write({'so_line': False})` | Only if SOL not yet invoiced; qty_delivered not reversed automatically |
| `sale.order._create_invoices()` | `action_reverse()` | Creates `account.move.reversal` | Creates credit note; original invoice remains; timesheet uninvoiced |
| `account.move` posted | NOT reversible directly | Credit note via reversal | Accounting entries are immutable once posted |
| Milestone assignment | Break milestone link | `write({'milestone_id': False})` | Only if milestone not yet achieved |

**Important:** Once an `account.move` (invoice) is **posted**, it cannot be deleted — only reversed via credit note. Timesheet lines that have been included in a posted invoice must be uninvoiced by reversing the invoice first. The `so_line.qty_delivered` is decremented only when the invoice is reversed and the line is no longer referenced.

---

## Alternative Triggers

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | Grid view cell edit | Interactive | Manual per entry |
| User action | Form view `create()` | Interactive | Manual |
| Onchange cascade | `_onchange_project_id()` | Field change on project_id | On demand |
| Onchange cascade | `_onchange_task_id()` | Field change on task_id | On demand |
| Cron scheduler | `_cron_sync_timesheets()` | External timer sync | Per configured interval |
| Automated action | `base.automation` | Rule triggered | On rule match |
| Webhook / API | `account.analytic.line.create()` | External system (e.g., Jira, Toggl) | On demand |
| Project close | `project.project.action_close()` | State change | Manual |
| Import | `base_import.import` | CSV/XLSX import | Manual bulk |

**For AI reasoning:** The flow branches significantly based on billing_type. Always trace `project_id.billing_type` before assuming how the SOL link works. Manual billing projects do NOT auto-create invoices — they require explicit "Create Invoice" action.

---

## Related

- [Modules/HR](Modules/HR.md) — HR module reference
- [Modules/Project](Modules/Project.md) — Project module reference
- [Modules/Account](Modules/Account.md) — Account module reference
- [Flows/Cross-Module/employee-projects-timesheet-flow](Flows/Cross-Module/employee-projects-timesheet-flow.md) — Cross-module timesheet flow
- [Flows/Project/task-lifecycle-flow](Flows/Project/task-lifecycle-flow.md) — Task lifecycle reference
- [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) — Workflow pattern reference
- [Core/API](Core/API.md) — @api decorator patterns
