---
type: flow
title: "Invoice Post Flow (Draft to Posted)"
primary_model: account.move
trigger: "User action — Invoice → Confirm"
cross_module: true
models_touched:
  - account.move
  - account.move.line
  - account.account
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Account/invoice-creation-flow](Flows/Account/invoice-creation-flow.md)"
  - "[Flows/Account/payment-flow](Flows/Account/payment-flow.md)"
  - "[Flows/Account/payment-flow](Flows/Account/payment-flow.md)"
related_guides:
  - "[Business/Account/chart-of-accounts-guide](Business/Account/chart-of-accounts-guide.md)"
source_module: account
source_path: ~/odoo/odoo19/odoo/addons/account/
created: 2026-04-06
updated: 2026-04-06
version: "1.0"
---

# Invoice Post Flow (Draft to Posted)

## Overview

Posting a draft invoice (`action_post()`) is the critical step that transitions an invoice from editable draft to a legally binding, locked journal entry. Once posted, debit and credit amounts cannot be modified — only reversed via credit note. This step consumes the sequence number (invoice number), triggers automatic reconciliations, and activates the PDF report attachment.

## Trigger Point

User clicks the **"Post"** button on a draft invoice form, or programmatically via `account.move.action_post()`. Can also be triggered via automated action or API call to post an invoice in draft state.

---

## Complete Method Chain

```
1. account.move.action_post()
   │
   ├─► 2. _post()  [entry point]
   │     └─► 3. _post_impl()
   │           ├─► 4. _check_fiscal_year_lock_date()
   │           │     └─► 5. IF invoice_date < fiscal_year_lock_date:
   │           │           └─► raise UserError("Cannot post before lock date")
   │           │
   │           ├─► 6. _check_lock_date()
   │           │     └─► 7. IF date < period_lock_date:
   │           │           └─► raise UserError("Period is locked")
   │           │
   │           ├─► 8. _check_company()
   │           │     └─► 9. company_id must match user's company
   │           │
   │           ├─► 10. FOR EACH line: _check_account_lock_date()
   │           │     └─► 11. IF account has user_lock_date:
   │           │           └─► raise UserError("Account is locked")
   │           │
   │           ├─► 12. sequence.next_by_code('account.move')
   │           │     └─► 13. move_name (invoice number) assigned
   │           │           └─► 14. write({'state': 'posted', 'move_name': name})
   │           │
   │           ├─► 15. FOR EACH line where product is asset:
   │           │     └─► 16. _create_asset()
   │           │           └─► 17. account.asset.asset record created
   │           │
   │           ├─► 18. FOR EACH line with matching account:
   │           │     └─► 19. _reconcile_with_move_lines()
   │           │           └─► 20. account.move.line.reconcile()
   │           │                 └─► 21. partial_reconcile or full_reconcile created
   │           │
   │           ├─► 22. _compute_tax_totals()
   │           │     └─► 23. tax_totals JSON finalized and locked
   │           │
   │           ├─► 24. _message_auto_subscribe_notify()
   │           │     └─► 25. followers notified of post action
   │           │
   │           ├─► 26. activity_complete()
   │           │     └─► 27. pending mail.activity on move marked done
   │           │
   │           └─► 28. _generate_pdf()
   │                 └─► 29. invoice report PDF generated
   │                       └─► 30. ir.attachment record created and linked
```

---

## Decision Tree

```
Is invoice state = 'draft'?
├─► NO → raise UserError("Invoice already posted")
└─► YES → continue

Is there a fiscal year lock date?
├─► YES → IF invoice_date < fiscal_year_lock_date: BLOCK
└─► NO → continue

Is there a period lock date?
├─► YES → IF date < period_lock_date: BLOCK (unless account_manager)
└─► NO → continue

Does any line product have is_asset = True?
├─► YES → _create_asset() → account.asset record auto-created
└─► NO → skip

Does invoice have reconcilable lines (partner balance)?
├─► YES → auto-reconciliation entry created
│          └─► invoice.state: 'posted' → 'in_payment' on partial reconciliation
└─► NO → state: 'posted' only

Is currency != company currency?
├─► YES → currency conversion applied at posting date rate
│          └─► amount_currency recorded vs. base_currency amount
└─► NO → single-currency posting, no conversion

Does invoice have payment_terms?
├─► YES → partial reconciliations created on each due date
│          └─► invoice.state: 'in_payment' per installment
└─► NO → full reconciliation expected on payment registration

Is there a tax lock date?
├─► YES → IF invoice_date < tax_lock_date: BLOCK
└─► NO → continue
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `account_move` | Updated | state='posted', move_name=sequence number, date, posted |
| `account_move_line` | Updated (now locked) | debit/credit fields frozen, move_id, reconcile_id if reconciled |
| `account_partial_reconcile` | Created (if partial reconciliation) | debit_move_id, credit_move_id, amount, date |
| `account_asset_asset` | Created (if asset product) | name, profile_id, purchase_value, state |
| `ir_attachment` | Created | name='Invoice.pdf', res_model='account.move', res_id=move.id |
| `mail_mail` | Created | notification queued to followers |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| invoice_date before fiscal year lock date | `UserError` | "The date is being used in a locked period..." |
| User is not account_manager and period is locked | `UserError` | Period lock enforced |
| No journal sequence configured | `ValidationError` | `ir.sequence` not found for journal's entry_sequence_code |
| Invoice has no lines (blank invoice) | `ValidationError` | `_check_filled_distribution()` fails — at least one line required |
| Company mismatch on move vs. user | `AccessError` | Multi-company rule enforcement |
| Account on line is locked by user_lock_date | `UserError` | "Account date is locked" |
| Draft invoice already posted (race condition) | `UserError` | "Invoice already posted" — state check before write |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Invoice number assigned | `ir.sequence` | Next number consumed from journal's sequence |
| Journal entries locked | `account.move.line` | debit/credit fields become immutable |
| Asset records created | `account.asset.asset` | If product has is_asset=True, purchase value capitalized |
| Tax totals frozen | `account.move` | tax_totals JSON field updated and locked |
| Follower notifications sent | `mail.mail` | Internal note posted with "Invoice Posted" message |
| Outstanding amount updated | `account.move` | amount_residual recomputed (set to 0 if fully reconciled) |
| PDF report attached | `ir_attachment` | 'Invoice Report' PDF linked as attachment |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `action_post()` button | Current user | `group_account_invoice` | Button-level security in XML |
| Lock date checks | `sudo()` | System (no ACL) | Internal validation, bypassed for admin |
| Sequence consumption | `sudo()` | System (no ACL) | `ir.sequence.next_by_code()` runs as admin |
| Asset creation | `sudo()` | System (no ACL) | `_create_asset()` bypasses ACL |
| Attachment creation | Current user | Write on `ir.attachment` | User must have write access to attach |
| Mail notification | `mail.group` | Public | Follower-based, respects channel ACL |

**Key principle:** Lock date and sequence checks run under `sudo()` to ensure audit integrity. Asset creation also runs as superuser to guarantee proper bookkeeping.

---

## Transaction Boundary

```
Steps 1-30  ✅ INSIDE transaction  — atomic (all or nothing)
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| All validation + posting | ✅ Atomic | Rollback on any error; no partial state |
| Asset creation | ✅ Atomic | Part of same transaction |
| PDF generation | ✅ Atomic | Generated in-memory, attached in same tx |
| Mail notification | ✅ Within ORM | Written to `mail.mail` table in same tx |

**Rule of thumb:** The entire `action_post()` runs atomically — no external HTTP calls or queue jobs. If posting fails at step 4 (lock date), no journal entry is created.

---

## Idempotency

> *What happens when this flow is executed multiple times.*

| Scenario | Behavior |
|----------|----------|
| Double-click "Post" button | First click succeeds, second raises `UserError` ("Invoice already posted") — state is checked before write |
| Re-trigger post on already posted invoice | Raises `UserError` — state check prevents re-posting |
| API call with already-posted invoice ID | Same as above — state check blocks |
| Sequence already consumed (concurrent race) | `UniqueConstraint` on (journal_id, sequence_prefix) prevents duplicate numbers; second write fails |

**Non-idempotent points:**
- `ir.sequence.next_by_code()` always consumes a number (even on failure — use `sequence._get_current_sequence()` to check if already consumed)
- `account.asset.asset` records are created once per line (not re-created on re-post)
- `ir_attachment` created once (unless re-generated, which replaces previous attachment)

---

## Extension Points

> *Where and how developers can override or extend this flow.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Pre-post validation | `_check_fiscal_year_lock_date()` | Custom pre-lock validation | self | Extend to add custom rules |
| Pre-post | `_autopost_draft_entries()` | Hook before state change | self | Extend with custom pre-post logic |
| Post completion | `_attachment_datas()` | Custom PDF generation | self | Override PDF report |
| Asset override | `_create_asset()` | Custom asset creation logic | self, line | Extend with super() |
| Reconciliation | `_reconcile_with_move_lines()` | Custom reconciliation rules | self | Override reconciliation logic |
| Lock date bypass | `_check_lock_date()` | Allow admin to bypass lock | self | Extend with group check |

**Standard override pattern:**
```python
# CORRECT — extends with super()
def _check_fiscal_year_lock_date(self):
    super()._check_fiscal_year_lock_date()
    # custom validation — e.g., check custom field
    if self.custom_field == 'block':
        raise UserError("Custom block on this move")

# CORRECT — extend action_post
def action_post(self):
    res = super().action_post()
    self._create_custom_ledger_entry()  # custom side effect
    return res
```

**Deprecated override points to avoid:**
- `@api.one` anywhere (deprecated in Odoo 19)
- Overriding `_check_unique_sequence_number` without calling super
- Direct state machine bypass without proper validation

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| Posted invoice | `action_reverse()` | Creates `account.move` type `out_refund` (credit note) | Original entry PRESERVED — not deleted; reversal is a separate entry |
| Posted invoice (alternative) | `action_reverse()` then `action_draft` on credit note | Credit note can be drafted and corrected | Credit note itself becomes reversible |
| Posted invoice | NOT deletable | `unlink()` blocked — entries are locked | Must reverse, not delete |
| Auto-reconciliation | `action_unreconcile()` | Breaks the `account.partial.reconcile` link | Re-exposing open amount on invoice |
| Asset created on post | `action_asset_modify()` or manual close | Asset lifecycle managed separately | Asset remains even if invoice reversed |

**Important:** Posted invoice entries are **immutable** — they cannot be edited or deleted. The only sanctioned reversal path is `action_reverse()`, which creates a credit note. This preserves the full audit trail.

**Credit Note Flow (Reverse):**
```
Posted Invoice (out_invoice, state=posted)
   └─► Action: "Add Credit Note" / action_reverse()
        ├─► Creates reversal move (out_refund) in draft state
        ├─► User confirms reversal amount (full or partial)
        ├─► Reverse move posted → Dr. Revenue / Cr. Customer
        ├─► original.move.reversal_id = credit_note.id
        └─► credit_note.state = 'posted' (also locked)
             └─► credit_note amount = invoice amount → invoice marked paid
```

---

## Alternative Triggers

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `action_post()` button | Interactive on invoice form | Manual |
| Cron scheduler | `account.move._autopost_draft_entries()` | Auto-post scheduled entries | Configurable |
| Automated action | `base.automation` | Rule-triggered posting | On rule match |
| API (external) | `POST /api/account.move/<id>/action_post` | External system (e.g., e-commerce) | On demand |
| Button (inline) | "Confirm" inkanban/dashboard | Bulk action on draft invoices | Manual |

---

## Related

- [Modules/Account](Modules/account.md) — Account module reference
- [Flows/Account/invoice-creation-flow](Flows/Account/invoice-creation-flow.md) — Previous step: creating the invoice
- [Flows/Account/payment-flow](Flows/Account/payment-flow.md) — Next step: registering payment
- [Flows/Account/payment-flow](Flows/Account/payment-flow.md) — Automatic reconciliation logic
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — Workflow pattern reference
- [Core/API](Core/API.md) — @api decorator patterns