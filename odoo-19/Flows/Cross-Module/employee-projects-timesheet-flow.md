---
type: flow
title: "Employee → Projects → Timesheet Cross-Module Flow"
primary_model: project.project
trigger: "User action — Project → Tasks → Log Time"
cross_module: true
models_touched:
  - hr.employee
  - project.project
  - project.task
  - account.analytic.line
  - res.users
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/HR/employee-creation-flow](Flows/HR/employee-creation-flow.md)"
  - "[Flows/Sale/sale-to-invoice-flow](Flows/Sale/sale-to-invoice-flow.md)"
related_guides:
  - "[Business/Project/project-management-guide](Business/Project/project-management-guide.md)"
source_module: project
source_path: ~/odoo/odoo19/odoo/addons/project/
created: 2026-04-07
updated: 2026-04-07
version: "1.0"
---

# Employee → Projects → Timesheet Cross-Module Flow

## Overview

Employee linked to project membership, timesheet recording, and automatic billing to sale order. This flow spans `hr_employee`, `project_project`, `project_task`, and `account_analytic_line`, enabling time tracking that feeds into both project progress and customer invoicing.

## Trigger Point

- **Timesheet entry:** `account.analytic.line.create(vals)` — from task, project, or manual entry
- **Start timer:** Employee starts timer from task → creates timesheet on stop
- **Manual log:** Employee manually enters hours on project or task

---

## Complete Method Chain

```
1. account.analytic.line.create(vals)
   │
   ├─► 2. _onchange_account_id()
   │      └─► 3. project_id = analytic_account_id.project_id
   │            └─► 4. task_id auto-set if from task context
   │                  └─► 5. project.billable_type determined
   │
   ├─► 6. _onchange_product_id()
   │      └─► 7. product linked (service product)
   │            └─► 8. uom_id set from product
   │                  └─► 9. amount = product.list_price × unit_amount (if not employee rate)
   │
   ├─► 10. _onchange_unit_amount()
   │       └─► 11. amount computed from unit_amount × rate
   │             └─► 12. IF project.billable_type = 'employee_rate':
   │                   └─► 13. employee_id = resource_id.employee_id
   │                         └─► 14. amount = employee.hourly_cost × hours
   │             └─► 15. ELSE IF project.billable_type = 'product_rate':
   │                   └─► 16. amount = product.list_price × hours
   │
   ├─► 17. IF project linked to sale.order:
   │       └─► 18. sale_line_id = project.sale_line_id (billable line)
   │             └─► 19. sale_order_id = project.sale_order_id
   │                   └─► 20. timesheet auto-invoiced based on SO invoice policy
   │                         └─► [A] IF so.invoice_policy = 'order':
   │                               └─► revenue recognized on order confirmation
   │                         └─► [B] IF so.invoice_policy = 'delivery':
   │                               └─► revenue recognized on invoice validation
   │
   ├─► 21. IF so_line set:
   │       └─► 22. amount posted to so_line revenue account
   │             └─► 23. account.move.line generated for revenue
   │
   ├─► 24. _update_project_progress()
   │       └─► 25. project.task progress updated
   │             └─► IF milestone exists:
   │                   └─► milestone progress updated
   │
   ├─► (Post-create effects):
   │      ├─► hr_employee.timesheet_count updated
   │      ├─► activity scheduled for manager if overtime
   │      ├─► IF project.allow_timesheets = False:
   │      │      └─► warning raised
   │      └─► uom conversion: company_timesheet_uom applied
```

---

## Decision Tree

```
Timesheet created (account.analytic.line)
│
├─► Is project billable?
   ├─► YES → Determine billing rate type
   │         ├─► employee_rate → amount = employee.hourly_cost × hours
   │         ├─► product_rate → amount = product.list_price × hours
   │         └─► fixed_price → amount from project fixed price (not hourly)
   │              └─► milestone billing → amount reserved until milestone done
   │
   └─► NO → Timesheet for tracking only (no customer billing)
│
├─► Is project linked to sale order?
   ├─► YES → sale_line_id auto-populated
   │         └─► Revenue posted to SO line account
   │         └─► Will be invoiced per SO invoice policy
   │
   └─► NO → Standalone project — no billing
│
├─► Is employee linked to project?
   ├─► YES → Timesheet valid, employee_id set from resource
   │
   └─► NO → Check if contractor or external
            ├─► Contractor → timesheet without employee link
            └─► External → warning if timesheet not allowed
│
└─► ALWAYS:
    └─► Project progress updated
    └─► Task progress updated
    └─► Employee timesheet count incremented
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `account_analytic_line` | Created | employee_id, project_id, task_id, unit_amount, amount, so_line |
| `project_project` | Updated (progress) | total_timesheet_time, progress |
| `project_task` | Updated (progress) | effective_hours, progress |
| `sale_order_line` | Updated (invoiced qty) | qty_delivered, qty_to_invoice |
| `account_move_line` | Created (if invoiced) | account_id, debit, credit, sale_line_ids |
| `hr_employee` | Updated (timesheet count) | timesheet_count |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Timesheet on non-timesheet project | `UserError` | `project.allow_timesheets = False` — warning shown |
| Employee not linked to project | `UserError` | Employee not in project.members |
| Missing project on analytic line | `ValidationError` | Account must have project_id set |
| Quantity exceeds daily limit | `UserError` | Overtime threshold configured in settings |
| Invalid UOM for timesheet | `ValidationError` | UOM must match company_timesheet_uom |
| Contractor timesheet on restricted project | `UserError` | External users cannot log time without access |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Project progress updated | `project.project` | `total_timesheet_time` sum, `progress` recomputed |
| Task progress updated | `project.task` | `effective_hours` sum, `progress` recomputed |
| Milestone progress updated | `project.milestone` | Revenue milestone progress tracked |
| Employee timesheet count | `hr.employee` | `timesheet_count` incremented |
| SO line qty updated | `sale.order.line` | `qty_delivered` updated for billing |
| Revenue entry posted | `account.move.line` | Revenue posted to sale account |
| Manager notification | `mail.activity` | Overtime alert activity created |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `account.analytic.line.create()` | Current user | Project member | Self-service timesheet |
| `_onchange_account_id()` | Current user | Read on project | Onchange respects ACL |
| `_onchange_product_id()` | Current user | Read on product | Onchange reads product |
| `_update_project_progress()` | Current user | Write on project | Member can update own task |
| Sale line qty update | `sudo()` | System (internal) | Cross-module write |
| Manager overtime activity | `sudo()` | System (internal) | Internal activity creation |

**Key principle:** Employees can log time on projects they are members of. Non-members cannot create timesheets without project manager approval.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside.*

```
Steps 1-16   ✅ INSIDE transaction  — atomic (timesheet create, onchanges)
Steps 17-23  ✅ INSIDE transaction  — atomic (SO link, revenue posting)
Steps 24-25  ✅ INSIDE transaction  — atomic (project/task progress update)
Activity (overtime notification) ❌ OUTSIDE transaction — via mail queue
Mail notification                ❌ OUTSIDE transaction — via mail queue
SO invoice creation              ❌ OUTSIDE transaction — separate flow (SO invoice flow)
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Timesheet create/write | ✅ Atomic | Rollback on any error |
| Project progress update | ✅ Atomic | Rolled back with timesheet |
| SO link and revenue | ✅ Atomic | Rolled back with timesheet |
| Mail notification | ❌ Async queue | Retried by `ir.mail.server` cron |
| SO invoice creation | ❌ Separate flow | Handled by sale order invoice flow |

**Rule of thumb:** Timesheet creation and all direct effects (progress, revenue) are atomic. Notifications and SO invoicing are handled by separate flows.

---

## Idempotency

> *What happens when this flow is executed multiple times.*

| Scenario | Behavior |
|----------|----------|
| Double-save timesheet | Only one analytic line created |
| Re-edit timesheet (same values) | `write()` re-runs, progress recalculated |
| Duplicate timesheet on refresh | Only one record per vals — ORM deduplicates |
| Re-trigger on same task | Each entry creates a separate line (not idempotent) |
| Multiple quick entries | Each `create()` is separate — design allows multiple |

**Common patterns:**
- **Idempotent:** Write on existing record (no duplicate created)
- **Non-idempotent:** Each `create()` creates a new timesheet line — multiple entries allowed
- **Partial idempotent:** Project progress update — re-running updates to latest value

---

## Extension Points

> *Where and how developers can override or extend this flow.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 3 | `_onchange_account_id()` | Custom project mapping | self | Extend to set task, step from project |
| Step 7 | `_onchange_product_id()` | Custom product behavior | self | Add UOM conversion, custom pricing |
| Step 13 | Employee rate lookup | Custom hourly cost computation | employee_id | Override `employee.hourly_cost` getter |
| Step 20 | SO link logic | Custom sale order determination | project_id | Extend `_get_sale_line()` |
| Post-create | `_after_timesheet_create()` | Post-creation side effects | self | Extend via `create()` override |
| Progress update | `_update_project_progress()` | Custom progress computation | self | Extend with `super()` |

**Standard override pattern:**
```python
# CORRECT — extends with super()
def _onchange_account_id(self):
    result = super()._onchange_account_id()
    # custom project field sync, step mapping, etc.
    self.project_id = result.get('project_id', self.project_id)
    return result

# CORRECT — extend create
def create(self, vals):
    # pre-processing
    line = super().create(vals)
    # post-processing (custom notifications, external sync)
    return line
```

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct `_timesheet_billing()` calls (deprecated — use sale order link)
- Bypassing `sale_line_id` for manual revenue entry (use SO flow instead)

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| Create timesheet | `unlink()` | `line.unlink()` | Project progress recalculated; SO qty reversed |
| Edit timesheet (reduce hours) | `write()` | `line.write({'unit_amount': new_hours})` | Project progress and SO qty updated |
| Delete timesheet after SO invoiced | Credit note | `account.move` reversal | Must credit-note the customer invoice |
| Delete timesheet on delivered SO | Adjust SO | `so_line.write({'qty_delivered': ...})` | Requires sale manager approval |

**Important:**
- Deleting a timesheet line automatically decrements project/task progress
- If the timesheet has been invoiced (SO confirmed and delivered), a credit note is required
- Editing timesheet hours on an invoiced line requires invoice adjustment
- Timesheet history is preserved — deleted records may still appear in audit trail
- Overtime activities cannot be undone once created — must manually cancel the activity

---

## Alternative Triggers

> *All the ways this flow can be initiated.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| Task timer start/stop | `project.task.timesheet_start()` / `_stop()` | Task form | Manual |
| Manual entry | `account.analytic.line.create()` | Project or task form | Manual |
| Quick entry | Inline timesheet widget | Project kanban view | Manual |
| Mobile app | Mobile timesheet entry | Mobile | Manual |
| Import | CSV/XLS import | Bulk import | Manual |
| API / external | `external_endpoint()` | External time tracking system | On demand |
| Onchanges on related models | Cascade onchange | Project/task field change | On demand |

**For AI reasoning:** When asked "what happens if a timesheet is logged on a billed project?", trace through the SO invoice policy and revenue recognition implications.

---

## Related

- [Modules/project](Modules/Project.md) — Project module reference
- [Modules/HR](Modules/HR.md) — HR module reference
- [Modules/Sale](Modules/Sale.md) — Sale module reference (SO billing)
- [Flows/HR/employee-creation-flow](Flows/HR/employee-creation-flow.md) — Employee creation
- [Flows/Sale/sale-to-invoice-flow](Flows/Sale/sale-to-invoice-flow.md) — Sale to invoice flow
- [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) — Cross-module flow patterns
- [Core/API](Core/API.md) — @api decorator patterns