---
type: flow
title: "Expense Request Flow"
primary_model: hr.expense
trigger: "User action — Expenses → Create Expense"
cross_module: true
models_touched:
  - hr.expense
  - hr.expense.sheet
  - account.move
  - account.move.line
  - product.product
  - hr.employee
  - hr.expense.analytic
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/HR/employee-creation-flow](odoo-19/Flows/HR/employee-creation-flow.md)"
  - "[Flows/Account/payment-flow](odoo-19/Flows/Account/payment-flow.md)"
related_guides:
  - "[Modules/HR](odoo-18/Modules/hr.md)"
source_module: hr_expense
source_path: ~/odoo/odoo19/odoo/addons/hr_expense/
created: 2026-04-07
version: "1.0"
---

# Expense Request Flow

## Overview

An employee creates an expense record through the HR Expenses module, optionally grouping it into an expense sheet for batch approval. The manager approves the expense, after which an accounting journal entry is generated: the expense account is debited and the employee payable account is credited. The flow supports both individual expense submission and sheet-based batch submission, with full analytic distribution tracking across multiple accounts.

## Trigger Point

**User (Employee):** Opens **Expenses → Create Expense**, fills form, selects product and amount, clicks **Submit** or attaches to an expense sheet for batch approval.
**Method:** `hr.expense.create(vals)` + `action_submit_expenses()` or sheet-based `sheet.action_sheet_move_create()`

---

## Complete Method Chain

```
1. hr.expense.create(vals)
   │
   ├─► 2. _onchange_employee_id()
   │      ├─► 3. product_ids filtered from expense.product.map_product_employee()
   │      ├─► 4. analytic_account_id suggested from employee's department
   │      └─► 5. department_id from employee record
   │
   ├─► 6. _onchange_product_id()
   │      ├─► 7. account_id from product.expense_account (product.product)
   │      ├─► 8. unit_amount loaded from product.list_price
   │      └─► 9. tax_ids loaded from product.supplier_taxes_id
   │
   ├─► 10. _compute_total_amount()
   │       ├─► 11. total = unit_amount × quantity (via @api.depends)
   │       └─► 12. tax amount computed via account.tax.compute_all()
   │
   ├─► 13. IF sheet_id set:
   │       └─► 14. expense attached to hr.expense.sheet (sheet_id Many2one)
   │
   └─► 15. (form saved, state = 'draft')
```

```
16. hr.expense.action_submit_expenses()
    ├─► 17. state = 'submit'
    ├─► 18. _check_expense_validity() — account_id, product_id required
    │
    ├─► 19. IF sheet_id:
    │       └─► 20. sheet.write({'state': 'submit'}) — batch submit
    │
    └─► 21. mail.activity.schedule()
            └─► 22. activity created for expense manager (department manager)
                   └─► 23. mail.message posted "Expense Submitted"
```

### Sheet-Based Approval Chain

```
24. hr.expense.sheet.create(vals)
    ├─► 25. expense_ids = [(6, 0, [expense_ids])]
    ├─► 26. total_amount = sum(expense.total_amount for expense in expense_ids)
    └─► 27. state = 'draft'
```

```
28. hr.expense.sheet.approve_expense_sheets()
    ├─► 29. _check_approve() — current user is manager / officer
    ├─► 30. state = 'approve'
    │
    ├─► 31. expense_ids.action_move_create()
    │       ├─► 32. account.move.create({...})
    │       │       └─► 33. account.move.line entries prepared
    │       │              ├─► Dr: expense account (product.expense_account)
    │       │              ├─► Cr: employee payable (employee.address_home_id.property_account_payable)
    │       │              └─► 34. Analytic lines split: analytic_distribution applied
    │       │                     └─► 35. One analytic line per account_id in distribution dict
    │       │
    │       └─► 36. account.move.post() — state = 'posted'
    │
    └─► 37. sheet.write({'state': 'done'})
            └─► 38. mail.activity unlink (approval activity cleared)
```

### Individual Journal Entry (non-sheet)

```
39. hr.expense.action_move_create()
    ├─► 40. _prepare_move_values() — journal_id, ref from expense name
    ├─► 41. account.move.create(vals)
    │       └─► 42. account.move.line records
    │              ├─► Dr: expense_account_id (from product)
    │              ├─► Cr: company_account_id (hr.expense.product.map_tax() + fiscal_position)
    │              └─► 43. Analytic line split via expense.line.analytic_distribution
    └─► 44. write({'state': 'posted', 'move_id': move_id})
```

### Tax and Fiscal Position

```
45. hr.expense.product.map_tax(product_id, fiscal_position_id)
    ├─► 46. account.fiscal.position.map_tax() — applies tax mapping
    └─► 47. tax_ids adjusted per fiscal position (B2B / B2C)
```

---

## Decision Tree

```
Expense Created (state = 'draft')
│
├─► product_id selected?
│  ├─► NO → unit_amount manual, account_id must be set manually
│  └─► YES → product defaults applied: unit_amount, account_id, tax_ids
│
├─► total_amount computed: total = unit_amount × quantity
│
├─► Attach to expense sheet?
│  ├─► YES → expense saved, sheet grouping for batch approval
│  └─► NO → individual submission
│
├─► Submit clicked → action_submit_expenses()
│  ├─► state = 'submit'
│  └─► mail.activity created for manager
│
├─► Manager approval (sheet or individual):
│  ├─► APPROVE → _check_approve() → state = 'approve'
│  │             └─► account.move created and posted
│  │                   ├─► Dr: expense account
│  │                   └─► Cr: employee payable
│  │
│  └─► REFUSE → sheet.write({'state': 'cancel'})
│                 └─► mail.activity cancelled
│
└─► Journal entry posted → state = 'done' (sheet) / 'posted' (move)
       └─► Payment triggered via [Flows/Account/payment-flow](odoo-19/Flows/Account/payment-flow.md)
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|------------------------|------------|
| `hr_expense` | Created | name, product_id, unit_amount, quantity, total_amount, employee_id, account_id, analytic_distribution, state |
| `hr_expense_sheet` | Created (sheet mode) | employee_id, expense_ids, total_amount, state, approval_date |
| `account_move` | Created | ref (expense name), line_ids, state = 'posted', date |
| `account_move_line` | Created | account_id (Dr/Cr pair), analytic_line_ids, expense_id |
| `account_analytic_line` | Created | account_id, amount, product_id, general_account_id |
| `mail_activity` | Created then unlinked | manager notified, then cleared on done |
| `mail_message` | Created | "Expense Submitted" / "Expense Approved" chatter |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Prevention |
|----------|-------------|------------------------|
| No product selected + no account_id | `ValidationError` | "Expense account is required" — enforced in `_check_expense_validity()` |
| Negative unit_amount or quantity | `UserError` | Amounts must be positive — domain constraint |
| Total amount = 0 | `ValidationError` | "Amount must be greater than 0" |
| Insufficient expense limit (policy) | `UserError` | Policy check in `hr.expense.sheet.approve_expense_sheets()` |
| Employee has no home partner | `ValidationError` | "Employee must have an associated partner" for payable account |
| Account not set on product | `ValidationError` | Product `expense_account` must be configured |
| Wrong analytic distribution | `ValidationError` | Analytic account must be active and belong to company |
| Fiscal position maps to no tax | Silent | Tax set to False if no mapping found |
| Sheet approval without expenses | `ValidationError` | Sheet must have at least one expense |
| Double submit (race condition) | State already 'submit' | Idempotent — re-submit on submitted record is no-op |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Manager notified | `mail.activity` | Activity created for department manager |
| Follower added | `mail.followers` | Employee and manager follow expense record |
| Journal entry created | `account.move` | Posted entry: Dr expense / Cr payable |
| Analytic lines split | `account.analytic.line` | One line per analytic_distribution key |
| Amount reserved | `account.analytic.account` | Budget tracking affected |
| Sheet state change | `hr.expense.sheet` | Batch state transitions |
| Tax computation | `account.tax` | Tax amounts affect total |
| Payment triggered | `account.payment` | Employee reimbursement via [Flows/Account/payment-flow](odoo-19/Flows/Account/payment-flow.md) |

---

## Security Context

| Step | Security Mode | Access Required | Notes |
|------|--------------|----------------|-------|
| `create()` | Current user | `group_hr_expense_user` | Own expenses only |
| `_onchange_*()` | Current user | Read on related fields | No write |
| `action_submit_expenses()` | Current user | Own expense | Submits own record |
| `approve_expense_sheets()` | Current user | `group_hr_expense_manager` | Manager/officer only |
| `action_move_create()` | `sudo()` internally | System for account moves | Bypasses ACL for accounting |
| `account.move.create()` | `sudo()` | System | Accounting requires superuser |
| `mail.activity.schedule()` | Current user | Write on activity model | Manager activity target |
| Sheet approval | Officer / Manager | `group_hr_expense_manager` | Button-level ir.rule |

**Key principle:** Expense creation runs as the current employee user. Accounting journal entry creation runs under `sudo()` to bypass record rules. Approval actions enforce `group_hr_expense_manager` group.

---

## Transaction Boundary

```
Steps 1-15   ✅ INSIDE transaction  — create() atomic
Steps 16-23  ✅ INSIDE transaction  — action_submit_expenses() atomic
Steps 24-27  ✅ INSIDE transaction  — sheet create() atomic
Steps 28-38  ✅ INSIDE transaction  — approve + move_create() atomic
Steps 39-44  ✅ INSIDE transaction  — individual move_create() atomic
Mail send    ❌ OUTSIDE transaction — via mail.mail queue (ir.mail.server)
Activity     ✅ INSIDE transaction  — activity_schedule() inside ORM call
```

| Step | Boundary | Behavior on Failure |
|------|----------|---------------------|
| `create()` / `write()` | ✅ Atomic | Rollback on any error |
| `account.move.post()` | ✅ Atomic | Rolled back with parent transaction |
| Mail notification | ❌ Async queue | Retried by `ir.mail.server` cron |
| Activity creation | ✅ Within ORM | Rolled back with transaction |

**Rule of thumb:** All ORM operations inside `create()`/`write()`/`action_*()` bodies are atomic. Email delivery is fire-and-forget via `mail.mail` queue. If `account.move` creation fails, the entire expense/sheet write is rolled back.

---

## Idempotency

| Scenario | Behavior |
|----------|----------|
| Double-click Submit | ORM deduplicates — only one state transition; second call sees state already 'submit' → no-op or raises `UserError` |
| Re-approve already approved sheet | `approve_expense_sheets()` checks state — already 'approve'/'done' → raises `UserError("Sheet already approved")` |
| Re-post already posted journal entry | `account.move` is immutable post — raises `UserError("Move is already posted")` |
| Re-create expense journal entry | Expense already has `move_id` set → raises `UserError("Journal entry already created")` |
| Sheet approve on cancelled sheet | State = 'cancel' → raises `UserError` |
| Network timeout + retry | create() is idempotent for same vals; move_create() is not (double entry) — use idempotency key |

**Non-idempotent operations:**
- `account.move.create()` / `post()` — creates accounting entries (unique per expense via `move_id` stored on expense)
- Sequence increments on `account.move` reference — prevented by `move_id` check on expense
- Activity creation — duplicates avoided by state check

---

## Extension Points

| Step | Hook Method | Purpose | Override Pattern |
|------|-------------|---------|-----------------|
| Step 2 | `_onchange_employee_id()` | Employee → department/analytic defaults | Extend with `super()` + field sync |
| Step 6 | `_onchange_product_id()` | Product → account/tax/unit_amount | Extend with `super()` + new defaults |
| Step 10 | `_compute_total_amount()` | Compute total with tax | Extend via `@api.depends` |
| Pre-17 | `_check_expense_validity()` | Pre-submit validation | Add custom checks |
| Step 19 | `action_submit_expenses()` | Submit behavior | Extend with `super()` |
| Step 28 | `approve_expense_sheets()` | Manager approval | Extend with `super()` |
| Step 33 | `_prepare_move_values()` | Journal entry values | Override for custom accounts |
| Step 34 | Analytic distribution split | Multiple analytic accounts | Extend `_get_analytic_lines()` |

```python
# Correct override pattern
def _onchange_product_id(self):
    result = super()._onchange_product_id()
    self.unit_amount = self.unit_amount  # do not blindly replace
    return result

def action_move_create(self):
    self.ensure_one()
    move = super().action_move_create()
    # custom post-action: log, notify, etc.
    return move
```

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct XML workflow engine calls (deprecated — use `action_*` methods)

---

## Reverse / Undo Flow

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `create()` | `unlink()` | `record.unlink()` | Only if state = 'draft' and no move_id |
| `action_submit_expenses()` | `action_draft()` | Resets to 'draft' | Only if manager hasn't approved |
| `approve_expense_sheets()` | NOT directly reversible | Requires manager manual action | No automated undo |
| `action_move_create()` | `action_reverse()` | Creates credit note move | Original entry remains, counter-entry created |
| `action_sheet_move_create()` | NOT reversible | Sheet state is terminal | Journal entries immutable |

**Important:** Accounting entries (account.move) are immutable once posted. Reversal creates a new correcting entry via `action_reverse()`, not deletion. Expense state can be reset to 'draft' only before approval.

---

## Alternative Triggers

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `action_submit_expenses()` button | Interactive | Manual |
| User action | Sheet batch submit | Interactive | Manual |
| Onchange cascade | `_onchange_product_id()` | Product field change | On demand |
| Onchange cascade | `_onchange_employee_id()` | Employee field change | On demand |
| Cron scheduler | `_cron_process_expense_sheets()` | Auto-approve low-value | Configurable |
| Import | `import_batch()` | CSV/XLS import | Bulk |
| Portal user | `portal_expense_submit()` | Employee via portal | External |
| Onchanges on related models | Cascade onchange | Related field change | On demand |

**For AI reasoning:** When expense flow fails mid-way, check: (1) product has expense_account set, (2) employee has home partner with payable account, (3) analytic accounts are active and belong to correct company, (4) current user has correct group for approval.

---

## Related

- [Modules/HR](odoo-18/Modules/hr.md) — HR module reference
- [Flows/HR/employee-creation-flow](odoo-19/Flows/HR/employee-creation-flow.md) — Employee setup (payable account, department)
- [Flows/Account/payment-flow](odoo-19/Flows/Account/payment-flow.md) — Reimbursement payment after expense approval
- [Core/API](odoo-18/Core/API.md) — @api.depends, @api.onchange decorator patterns
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — State machine pattern used in hr.expense.sheet
