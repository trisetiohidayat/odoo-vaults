---
type: flow
title: "POS Order to Invoice Flow"
primary_model: pos.order
trigger: "User action — Order → Invoice"
cross_module: true
models_touched:
  - pos.order
  - pos.order.line
  - pos.payment
  - account.move
  - account.move.line
  - account.payment
  - res.partner
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/POS/pos-session-flow](Flows/POS/pos-session-flow.md)"
  - "[Flows/Account/invoice-creation-flow](Flows/Account/invoice-creation-flow.md)"
  - "[Flows/Account/payment-flow](Flows/Account/payment-flow.md)"
related_guides:
  - "[Business/POS/pos-configuration-guide](Business/POS/pos-configuration-guide.md)"
  - "[Flows/Account/invoice-creation-flow](Flows/Account/invoice-creation-flow.md)"
source_module: pos
source_path: ~/odoo/odoo19/odoo/addons/point_of_sale/
created: 2026-04-07
updated: 2026-04-07
version: "1.0"
---

# POS Order to Invoice Flow

## Overview

The POS Order to Invoice Flow converts a paid `pos.order` into a draft `account.move` (customer invoice), applies fiscal positions to remap taxes and accounts, posts the invoice, and reconciles it against the payments already registered on the order. If the customer is unknown (no `partner_id`), a minimal guest partner is resolved or created at invoice time. The flow spans `pos.order`, `pos.payment`, `account.move`, and `account.move.line`, requiring coordination between Point of Sale and Accounting modules.

## Trigger Point

**User action:** Clicking **Invoice** on a paid POS order (`pos.order` with `state='paid'` or `state='done'`), which calls `pos.order.action_pos_order_invoice()`. Also triggered automatically via `pos.order._generate_pos_order_invoice()` when `to_invoice=True` is set on the order and `config_id.invoice_journal_id` is configured.

---

## Complete Method Chain

```
pos.order.action_pos_order_invoice()
  │
  ├─► ensure_one()
  │
  ├─► IF account_move exists:
  │     └─► return existing invoice form action (no-op)
  │
  └─► write({'to_invoice': True})
        └─► IF company_id.anglo_saxon_accounting
              AND session_id.update_stock_at_closing
              AND session_id.state != 'closed':
              └─► _create_order_picking()
                    └─► stock.picking + stock.move created
        └─► _generate_pos_order_invoice()
              └─► [full invoice generation chain below]
```

```
_generate_pos_order_invoice()
  │
  ├─► IF not _with_locked_records(allow_raising=False):
  │     └─► raise UserError("Orders already being invoiced")
  │
  ├─► write({'state': 'done'})
  │     └─► (idempotent if already 'done')
  │
  ├─► _prepare_invoice_vals()
  │     │
  │     ├─► fiscal_position_id resolved from order
  │     │     └─► pos_config.fiscal_position_id or order-level override
  │     │
  │     ├─► move_type = 'out_invoice' OR 'out_refund'
  │     │     └─► based on any(order.is_refund)
  │     │
  │     ├─► partner_id = partner_id.address_get(['invoice'])['invoice']
  │     │     └─► address_resolve resolves contact addresses
  │     │
  │     ├─► IF partner_id exists → commercial_partner resolved
  │     │     └─► property_account_receivable looked up
  │     │     └─► property_payment_term_id applied if pay_later used
  │     │
  │     ├─► IF partner_id is False (guest):
  │     │     └─► res.partner created as commercial partner
  │     │           └─► name = order.partner_id.name (from UI)
  │     │           └─► company_id = order.company_id
  │     │           └─► applied to invoice partner_id
  │     │
  │     ├─► invoice_payment_term_id:
  │     │     └─► partner_id.property_payment_term_id
  │     │           IF any(p.payment_method_id.type == 'pay_later')
  │     │           ELSE False
  │     │
  │     ├─► currency_id = pos.session.currency_id
  │     │     └─► multi-currency: rate applied per session
  │     │
  │     ├─► journal_id = config_id.invoice_journal_id
  │     │
  │     └─► invoice_line_ids = _prepare_invoice_lines(move_type)
  │           └─► per order line → Command.create with tax_ids
  │                 └─► fiscal position taxes remapped via
  │                       account.fiscal.position._map_tax()
  │                       account.fiscal.position._map_account()
  │
  ├─► _create_invoice(invoice_vals)
  │     └─► account.move.sudo().with_company().create(vals)
  │           └─► move_type='out_invoice', linked_to_pos=True
  │           └─► invoice_line_ids Command.create executed
  │                 └─► account.move.line records created per line
  │                       └─► tax lines via _generate_and_send()
  │           └─► IF cash_rounding:
  │                 └─► rounding account applied (profit or loss)
  │                       └─► rounding line created or updated
  │
  ├─► invoice._post()  [draft → posted]
  │     └─► validates all lines
  │     └─► sets move to 'posted' state
  │
  ├─► per session in orders grouped:
  │     └─► order._get_payments()
  │           └─► pos.payment._create_payment_moves(is_session_closed)
  │                 └─► account.move created per payment
  │                 └─► account.move.line created (receivable debit)
  │                 └─► account.move.line created (journal credit)
  │
  ├─► _reconcile_invoice_payments(invoice, all_payment_moves)
  │     └─► receivable_account = partner.property_account_receivable_id
  │           └─► IF NOT receivable.reconcile: skip
  │           └─► payment_receivable_lines =
  │                 payment_moves.pos_payment_ids
  │                   ._get_receivable_lines_for_invoice_reconciliation()
  │           └─► invoice_receivable_lines =
  │                 invoice.line_ids filtered by receivable account
  │           └─► (payment_lines | invoice_lines).reconcile()
  │
  ├─► IF session closed:
  │     └─► _create_misc_reversal_move(payment_moves)
  │           └─► reverses payment moves from closed session
  │                 └─► to avoid double-counting on reconciliation
  │
  └─► invoice._generate_and_send()
        └─► PDF generated
        └─► email sent to partner (if email configured)
```

---

## Decision Tree

```
Order Paid (state='paid')
│
├─► Invoice button clicked
│     └─► action_pos_order_invoice()
│           │
│           ├─► Invoice already generated?
│           │  ├─► YES → return existing form action (open it)
│           │  └─► NO → continue
│           │
│           ├─► to_invoice written True
│           │     ├─► Anglo-Saxon accounting + stock at close?
│           │     │  ├─► YES → _create_order_picking()
│           │     │  └─► NO → skip
│           │     └─► _generate_pos_order_invoice()
│           │
│           ├─► Customer known? (partner_id exists)
│           │  ├─► YES → use existing partner
│           │  │     └─► address resolved to invoice contact
│           │  │           └─► commercial_partner looked up
│           │  │                 └─► receivable account found
│           │  │
│           │  └─► NO (guest) → create minimal partner
│           │        └─► name from UI (customer_name field)
│           │              └─► company_id set
│           │                    └─► used as invoice partner
│           │
│           ├─► Fiscal position applied?
│           │  ├─► YES → _map_tax() per line → tax_ids remapped
│           │  │        └─► _map_account() → account_id remapped
│           │  └─► NO → original taxes used
│           │
│           ├─► Multi-currency?
│           │  ├─► YES → session.currency_id.rate applied
│           │  │        └─► balance = amount_currency * rate
│           │  └─► NO → single currency, no conversion
│           │
│           └─► Invoice created (draft)
│                 ├─► _post() called
│                 │     └─► state: draft → posted
│                 │           └─► payments reconciled
│                 └─► PDF generated and emailed
│                       └─► Done
│
└─► Done
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `pos_order` | Updated | to_invoice=True, state='done', account_move linked |
| `pos_payment` | Updated | account_move_id set (payment move) |
| `account_move` | Created (draft → posted) | move_type='out_invoice', partner_id, journal_id, state='posted' |
| `account_move_line` | Created per order line + payment lines | account_id, balance, partner_id, tax_ids, reconcile |
| `account_payment` | Created per pos.payment | pos_payment_id linked, journal_id, amount |
| `res_partner` | Created if guest order | name, company_id, commercial_partner_id |
| `stock_picking` | Created if anglo-saxon + session open | pos_order_id, state |
| `stock_move` | Created per picking | product_id, product_uom_qty, picking_id |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Invoice already exists | Returns existing (no error) | Idempotent — early return |
| Concurrent invoice generation | `UserError` | `_with_locked_records` prevents duplicate |
| No invoice journal configured | `UserError` | "No invoice journal configured for this POS session" |
| Partner does not exist | `ValidationError` | `_check_partner_id` — partner_id reset to False |
| Fiscal position tax not found | Silent | Taxes filtered; unmatched taxes dropped |
| Currency mismatch | `ValidationError` | `check_company_currency_id` on move creation |
| Payment amount mismatch | `UserError` | "Order is not fully paid" in `action_pos_order_paid` |
| Rounding configured but no rounding account | `ValidationError` | Rounding method needs loss/profit account |
| Unreconcilable receivable account | Silent skip | `_reconcile_invoice_payments` skips if `reconcile=False` |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Partner created | `res.partner` | Guest orders get a minimal partner record |
| Order state | `pos.order` | State moves `paid` → `done` during `_generate_pos_order_invoice` |
| Payment move | `account.move` | Payment moves created from `pos.payment._create_payment_moves` |
| Receivable reconciliation | `account.move.line` | Payment lines and invoice receivable line reconciled |
| Payment reversal | `account.move` | Misc reversal move created if session was closed |
| Stock picking | `stock.picking` | Created if Anglo-Saxon accounting and session not yet closed |
| PDF / email | `ir.attachment` / `mail.mail` | Invoice document generated and emailed |

---

## Security Context

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `action_pos_order_invoice()` | Current user | Read on `pos.order`, Write on `pos.order` | Button-level security |
| `_generate_pos_order_invoice()` | `sudo()` for invoice | Write on `account.move` | Invoice created as superuser |
| `_prepare_invoice_vals()` | Current user with `with_company()` | Read on `res.partner`, `account.fiscal.position` | Company-scoped reads |
| `_create_invoice()` | `sudo()` on `AccountMove` | Write on `account.move` | Invoice created as superuser |
| `invoice._post()` | `with_company()` | Write on `account.move` | Posted in company context |
| `_create_payment_moves()` | `with_company()` on session | Write on `account.move` | Payment moves in company context |
| `_reconcile_invoice_payments()` | `sudo()` on lines | Write on `account.move.line` | Reconciliation as superuser |
| `invoice._generate_and_send()` | Current user | Email template access | Mail generated for user |

**Key principle:** Invoice creation uses `sudo()` on `AccountMove` because POS users typically do not have direct accounting write access. The `with_company()` context ensures multi-company isolation throughout.

---

## Transaction Boundary

```
action_pos_order_invoice()    ✅ INSIDE transaction  — write to_invoice=True
_generate_pos_order_invoice() ✅ INSIDE transaction  — state update to 'done'
  ├─► _prepare_invoice_vals()    ✅ INSIDE transaction
  ├─► _create_invoice()          ✅ INSIDE transaction
  ├─► invoice._post()            ✅ INSIDE transaction
  ├─► _create_payment_moves()    ✅ INSIDE transaction
  ├─► _reconcile_invoice_payments() ✅ INSIDE transaction
  └─► _create_misc_reversal_move()  ✅ INSIDE transaction
_generate_and_send()           ❌ OUTSIDE transaction — PDF + email queue
  └─► mail.mail queued
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1-9 (invoice creation) | ✅ Atomic | Rollback on any error |
| `_with_locked_records` contention | `UserError` raised | Blocked until lock released |
| `invoice._post()` failure | Rollback | E.g., invalid account on line |
| `mail.mail` creation | ❌ Async queue | Never blocks invoice completion |
| PDF generation failure | ❌ Async | Retried; does not block posting |

---

## Idempotency

| Scenario | Behavior |
|----------|----------|
| Click Invoice twice on same order | First call creates; second returns existing `account_move` form action |
| Re-call `_generate_pos_order_invoice()` on already-invoiced order | `UserError` — "Some orders are already being invoiced" via `_with_locked_records` |
| Session close + invoice on same order | Payment moves reversed via `_create_misc_reversal_move()` to prevent double-count |
| Invoice already posted, `action_post()` re-called | No-op (already posted) |
| Reconciliation re-run on same lines | Lines already reconciled — `reconcile()` no-ops on reconciled lines |

**Invoice creation is NOT idempotent without the lock guard** — `_generate_pos_order_invoice()` requires the `_with_locked_records` mechanism to prevent concurrent calls.

---

## Extension Points

| Step | Hook Method | Purpose | Override Pattern |
|------|-------------|---------|-----------------|
| Invoice values | `_prepare_invoice_vals()` | Add custom invoice fields | Extend with `super()` then update vals |
| Invoice lines | `_prepare_invoice_lines()` | Add/discard order lines | Extend with `super()` then modify |
| Partner resolution | Override in `_prepare_invoice_vals()` | Custom partner creation for guests | Add guest partner creation before invoice |
| Tax computation | `_prepare_tax_base_line_values()` | Modify tax base | Extend with `super()` |
| Invoice line values | `_get_invoice_lines_values()` | Modify per-line amounts | Extend with `super()` |
| Post-processing | Override `_generate_pos_order_invoice()` | Custom post-invoice actions | Extend with `super()` |
| Payment reconciliation | `_reconcile_invoice_payments()` | Custom reconciliation | Extend with `super()` |
| PDF/email | Override `_generate_and_send()` | Custom delivery | Extend with `super()` |

**Standard override pattern:**
```python
# CORRECT — extends with super()
def _prepare_invoice_vals(self):
    vals = super()._prepare_invoice_vals()
    vals['narration'] = self.company_id.name  # add custom field
    return vals
```

---

## Reverse / Undo Flow

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| Invoice created + posted | `action_reverse()` | Creates credit note (out_refund) | Original invoice remains posted; credit note is new move |
| `account.move` reversed | Credit note posted | Out_refund with reversed_entry_id | Reversal moves are reconciled against original |
| Order invoiced but not yet paid | Not applicable | POS orders paid at POS — no separate payment step | Payments reconciled automatically |
| Session already closed | `_create_misc_reversal_move()` | Called during `_generate_pos_order_invoice` | Prevents double-count on closed session |
| Guest partner created | Manual delete | `res.partner.unlink()` | Only if not used elsewhere |

**Important:** Invoice reversal creates a new `out_refund` credit note — it does NOT delete the original invoice. The POS order retains its `account_move` reference to the original invoice. If you need to re-invoice, create a new order.

---

## Alternative Triggers

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `action_pos_order_invoice()` button | POS order form | Manual |
| Automatic (session open) | `_process_saved_order()` | POS frontend order finalization | Per order if `to_invoice=True` |
| Automatic (session close) | `_validate_session()` → orders → 'done' | Session close | Manual end-of-shift |
| API / external | `POST /pos/order/<id>/action_pos_order_invoice` | External integration | On demand |
| Cron (auto-close) | `_auto_close_abandoned_sessions()` | Server-side | Daily |

**For AI reasoning:** When asked "can I invoice a draft order?", trace through `_process_saved_order()` — orders are invoiced automatically if `to_invoice=True` AND `config_id.invoice_journal_id` is set, triggered when the order reaches `paid` state.

---

## Related

- [Flows/POS/pos-session-flow](Flows/POS/pos-session-flow.md) — Session lifecycle and payment registration
- [Flows/Account/invoice-creation-flow](Flows/Account/invoice-creation-flow.md) — Generic invoice creation flow
- [Flows/Account/payment-flow](Flows/Account/payment-flow.md) — Payment matching and reconciliation
- [Business/POS/pos-configuration-guide](Business/POS/pos-configuration-guide.md) — POS setup including invoice journal
- [Flows/Account/invoice-creation-flow](Flows/Account/invoice-creation-flow.md) — Manual invoicing guide
- [Modules/pos](Modules/pos.md) — Full POS module reference
- [Modules/Account](Modules/Account.md) — account.move, journal entries
- [Modules/res.partner](Modules/res.partner.md) — Partner model
- [Patterns/Security Patterns](Patterns/Security Patterns.md) — ACL and record rules
