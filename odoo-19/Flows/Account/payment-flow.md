---
type: flow
title: "Payment Flow (Invoice Payment)"
primary_model: account.payment
trigger: "User action — Invoice → Register Payment / Accounting → Payments → Create"
cross_module: true
models_touched:
  - account.payment
  - account.move
  - account.move.line
  - account.journal
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Account/invoice-post-flow](invoice-post-flow.md)"
  - "[Flows/Account/payment-flow](payment-flow.md)"
  - "[Flows/Account/invoice-creation-flow](invoice-creation-flow.md)"
related_guides:
  - "[Business/Account/chart-of-accounts-guide](chart-of-accounts-guide.md)"
source_module: account
source_path: ~/odoo/odoo19/odoo/addons/account/
created: 2026-04-06
updated: 2026-04-06
version: "1.0"
---

# Payment Flow (Invoice Payment)

## Overview

Registering a payment settles an invoice (fully or partially), creating a payment record and reconciling journal entries. The payment move debits the bank/cash account and credits the customer/vendor counterpart account, then matches against open invoice lines to mark them paid. A single payment can settle multiple invoices (batch payment), and partial payments leave the invoice open with updated residual.

## Trigger Point

Two primary entry points:

1. **From Invoice** — "Register Payment" button on an open (posted) invoice — pre-fills invoice details
2. **Manual** — `Accounting → Payments → Create` — user selects invoices and journal manually

---

## Complete Method Chain

```
1. account.payment.register(
       reconciliation_model='from.reconciliation',
       invoices=[inv1, inv2]
   )
   └─► or: account.payment.create(vals)

   ├─► 2. _compute_payment_amount()
   │     └─► 3. amount = SUM(invoice.amount_residual for each invoice)
   │           └─► 4. currency_id = invoice.currency_id
   │
   ├─► 5. account.journal.write({'journal_id': selected_journal})
   │     └─► 6. journal_type validated (bank/cash for outbound, same for inbound)
   │
   ├─► 7. account.payment.write({
   │         'journal_id': journal_id,
   │         'amount': amount,
   │         'partner_id': partner_id,
   │         'date': payment_date
   │     })
   │
   ├─► 8. account.payment.action_post()
   │     └─► 9. _post() → _check(date, journal_id)
   │           ├─► 10. journal_id.sequence.number_next incremented
   │           │
   │           ├─► 11. account.move.create() — one move per payment
   │           │     ├─► 12. Line 1: debit (or credit) to bank/cash account
   │           │     │     └─► amount = payment.amount
   │           │     │           └─► account_id = journal.default_account_id
   │           │     │
   │           │     └─► 13. Line 2: credit (or debit) to counterpart account
   │           │           └─► account_id = partner.property_account_receivable_id
   │           │                 (or payable for vendor payments)
   │           │
   │           ├─► 14. FOR EACH invoice being paid:
   │           │     └─► 15. _create_payment_reconciliation_moves()
   │           │           ├─► 16. account.move.line.create() for each invoice line
   │           │           │     └─► 17. matches invoice's open AR/AP line
   │           │           │
   │           │           └─► 18. account.move.line.reconcile()
   │           │                 ├─► 19. IF amount_paid == invoice.residual:
   │           │                 │     └─► 20. full_reconcile record created
   │           │                 │           └─► 21. invoice.state = 'paid'
   │           │                 │
   │           │                 └─► 22. IF amount_paid < invoice.residual:
   │           │                       └─► 23. partial_reconcile created
   │           │                             └─► 24. invoice.state = 'in_payment'
   │           │                                   └─► invoice.amount_residual updated
   │           │
   │           ├─► 25. bank.recconciliation record created (if journal_type = bank)
   │           │     └─► 26. bank.transaction matched to payment
   │           │
   │           └─► 27. _invalidate_cache()
   │                 └─► 28. partner balance recomputed
   │                       └─► 29. invoice.amount_residual updated per partial
   │
   └─► 30. mail.message posted on invoice chatter confirming payment
```

---

## Decision Tree

```
Is amount == invoice.residual (full payment)?
├─► YES → full reconciliation
│         └─► invoice.state = 'paid'
│         └─► account.move.line → full_reconcile record
└─► NO → partial reconciliation

Is amount < invoice.residual (partial payment)?
├─► YES → partial_reconcile created
│         └─► invoice.state = 'in_payment' (still open)
│         └─► amount_residual = original - payment.amount
└─► NO → overpayment

Is amount > invoice.residual (overpayment)?
├─► YES → credit left on partner account (overpayment balance)
│         └─► partner.credit_limit check
│         └─► credit note auto-created or left as credit
└─► NO (amount == residual): full payment path

payment_type = 'inbound' (customer payment)?
├─► YES → Dr. Bank, Cr. Customer AR
└─► payment_type = 'outbound' (vendor payment):
     └─► Dr. Vendor AP, Cr. Bank

journal_type = 'bank'?
├─► YES → bank.recconciliation entry created
│         └─► statement line matched to payment
└─► journal_type = 'cash':
     └─► cash.box record created (if using cash register)

Is reconciliation with multiple invoices?
├─► YES → payment splits across invoice lines
│         └─► partial_reconcile per invoice
└─► Single invoice: same logic, single reconciliation
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `account_payment` | Created | journal_id, amount, partner_id, date, state='posted', payment_type |
| `account_move` | Created | move_type='entry', journal_id, date, ref=payment.name |
| `account_move_line` | Created (2+ lines per payment) | debit/credit, account_id, partner_id, payment_id |
| `account_partial_reconcile` | Created (1 per invoice reconciled) | debit_move_id, credit_move_id, amount, date |
| `account_full_reconcile` | Created (if fully paid) | reconcile_id linked to partial_reconcile records |
| `bank_reconciliation_line` | Created (if bank journal) | matched against statement line |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| amount > invoice residual + tolerance | `UserError` | Overpayment requires special handling |
| journal has no default_account_id | `ValidationError` | Bank journal must have default debit/credit account |
| payment_date before period lock | `UserError` | "Cannot register payment in locked period" |
| invoice already fully paid | `UserError` | "Invoice already paid" — no open residual |
| user lacks `group_account_manager` for bank reconciliation | `AccessError` | Bank statement reconciliation ACL |
| currency mismatch between payment and invoice | `UserError` | Payment currency must match invoice currency |
| partner has different company than payment | `AccessError` | Multi-company enforcement |
| journal is not compatible with payment_type | `ValidationError` | Inbound journal vs. outbound payment mismatch |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Bank/cash account updated | `account.move.line` | Bank credited (inbound) or debited (outbound) |
| Customer/Vendor balance updated | `account.move.line` | AR/AP line reduced or cleared |
| Invoice state updated | `account.move` | `'posted'` → `'in_payment'` → `'paid'` (on full recon) |
| Outstanding amount recalculated | `account.move` | amount_residual reduced by payment amount |
| Partner credit updated | `res.partner` | credit_left / debit balance adjusted |
| Payment sequence consumed | `ir.sequence` | payment reference number generated |
| Bank statement matched | `account.bank.statement.line` | Payment linked to statement for reconciliation |
| Mail notification sent | `mail.mail` | Payment confirmation posted to invoice chatter |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `account.payment.create()` | Current user | `group_account_manager` | Payment creation is restricted |
| `action_post()` button | Current user | `group_account_manager` | Posting requires manager rights |
| Journal sequence increment | `sudo()` | System (no ACL) | Sequence runs as superuser |
| `reconcile()` method | `sudo()` | System (no ACL) | Reconciliation bypasses ACL for integrity |
| Bank reconciliation | Current user | `group_account_user` | Bank statement line matching |
| Mail notification | `mail.group` | Public | Follower-based, chatter post |

**Key principle:** Payment registration is a privileged operation — most flows run with `group_account_manager` rights. Reconciliation internally uses `sudo()` to ensure accounting integrity and prevent accidental breakage of linked entries.

---

## Transaction Boundary

```
Steps 1-30  ✅ INSIDE transaction  — atomic (all or nothing)
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| All payment + reconciliation | ✅ Atomic | Rollback — no partial payment recorded |
| Bank statement matching | ✅ Atomic | Part of same transaction |
| Mail notification | ✅ Within ORM | Written to `mail.mail` in same tx |

**Rule of thumb:** Payment registration is fully atomic. If `reconcile()` fails at step 22 (e.g., due to locking conflict), the entire payment is rolled back, including the payment move. No orphaned journal entries are created.

---

## Idempotency

> *What happens when this flow is executed multiple times.*

| Scenario | Behavior |
|----------|----------|
| Double-click "Register Payment" | First click succeeds, second raises `UserError` ("Payment already processed") — duplicate check via state |
| Re-trigger payment on already-paid invoice | Raises `UserError` — amount_residual = 0 blocks creation |
| Network timeout + retry | If `create()` succeeded but `action_post()` failed on timeout — payment in draft state; re-post possible |
| Payment posted twice (race condition) | `account.move` state check prevents double-post |
| Multiple partial payments on same invoice | Each creates a new partial_reconcile; amount_residual decremented each time |

**Non-idempotent points:**
- `account.payment.action_post()` always consumes journal sequence number
- `reconcile()` always creates `account.partial_reconcile` records
- `account_move` record is always created (but can be reversed)
- `account.payment` record state transitions: draft → posted (cannot undo without cancellation)

---

## Extension Points

> *Where and how developers can override or extend this flow.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Pre-payment | `_compute_payment_amount()` | Custom amount calculation | self, invoices | Extend to add fees/discounts |
| Amount validation | `_check_amount_limit()` | Custom payment limit check | self | Add credit limit validation |
| Pre-post | `_check_payment_journal()` | Custom journal validation | self | Validate journal compatibility |
| Line creation | `_create_payment_move()` | Custom move line generation | self | Override line accounts |
| Reconciliation | `_create_payment_reconciliation_moves()` | Custom reconciliation logic | self | Override reconciliation matching |
| Post-payment hook | `_invalidate_cache()` | Post-payment cache invalidation | self | Custom cache management |
| Bank statement match | `_auto_reconcile_statement_line()` | Auto-match to bank statement | self | Extend matching rules |

**Standard override pattern:**
```python
# CORRECT — extends with super()
def _compute_payment_amount(self, invoices, currencies):
    amount = super()._compute_payment_amount(invoices, currencies)
    # deduct bank fees
    return amount - self.journal_id.bank_fee_amount

# CORRECT — extend action_post
def action_post(self):
    res = super().action_post()
    self._post_payment_notification()  # custom hook
    return res
```

**Deprecated override points to avoid:**
- `@api.one` anywhere (deprecated in Odoo 19)
- Directly overriding `reconcile()` without understanding full reconciliation state
- Modifying `account_partial_reconcile` directly (always go through payment flow)

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| Posted payment | `action_cancel()` | Cancels payment record + reverses move | Payment move is reversed, not deleted |
| Posted payment | `action_draft()` | Returns to draft state | Move unposted; can be edited and re-posted |
| Full reconciliation | `action_unreconcile()` | Breaks reconciliation link | Invoice re-exposed as open; residual restored |
| Partial reconciliation | `action_unreconcile()` | Breaks partial recon link | Full or partial restoration of residual |
| Bank statement match | unmatch from statement | `account.bank.statement.line` unlink | Payment remains, bank rec unlinked |

**Important:** Cancelled payments do not automatically un-reconcile the invoice — you must manually unreconcile if you want the invoice to show as open again. The invoice state (`paid` / `in_payment`) is only updated when reconciliation is explicitly broken.

**Payment Cancellation Flow:**
```
Posted Payment (inbound, state=posted)
   └─► Action: "Cancel" / action_cancel()
        ├─► Payment state: posted → cancelled
        ├─► Payment move: state → cancelled (reversed via move)
        ├─► Account.move.line: debit/credit lines reversed
        ├─► invoice.state remains 'paid' (manually unreconcile to change)
        └─► bank.statement.line matched: unlinked from payment
             └─► Manual unreconcile required to restore invoice residual
```

---

## Alternative Triggers

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | "Register Payment" button on invoice | Interactive | Manual |
| User action | "Create Payment" on journal | Accounting menu | Manual |
| Batch action | `action_register_payment` multi-select | Kanban view | Manual |
| Cron scheduler | `account.payment._cron_auto_post()` | Auto-post scheduled payments | Configurable |
| Bank statement import | `_auto_reconcile_statement_line()` | Bank feed auto-match | Per bank feed |
| Automated action | `base.automation` | Rule-triggered payment | On rule match |
| API (external) | `POST /api/account.payment` | External system (e-commerce, POS) | On demand |

---

## Related

- [Modules/Account](Account.md) — Account module reference
- [Flows/Account/invoice-post-flow](invoice-post-flow.md) — Previous step: posting the invoice
- [Flows/Account/invoice-creation-flow](invoice-creation-flow.md) — Invoice creation before posting
- [Flows/Account/payment-flow](payment-flow.md) — Automatic reconciliation logic
- [Patterns/Workflow Patterns](Workflow Patterns.md) — Workflow pattern reference
- [Core/API](API.md) — @api decorator patterns