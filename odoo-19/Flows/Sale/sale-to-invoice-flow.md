---
type: flow
title: "Sale Order to Invoice Flow"
primary_model: account.move
trigger: "User action — Sale Order > Create Invoice / Cron auto-invoice"
cross_module: true
models_touched:
  - sale.order
  - account.move
  - account.move.line
  - sale.order.line
  - res.partner
  - account.fiscal.position
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Sale/quotation-to-sale-order-flow](Flows/Sale/quotation-to-sale-order-flow.md)"
  - "[Flows/Sale/sale-to-delivery-flow](Flows/Sale/sale-to-delivery-flow.md)"
related_guides:
  - "[Modules/Sale](Modules/sale.md)"
  - "[Modules/Account](Modules/account.md)"
source_module: sale, account
source_path: ~/odoo/odoo19/odoo/addons/sale/
created: 2026-04-06
updated: 2026-04-06
version: "1.0"
---

# Sale Order to Invoice Flow

## Overview

This flow covers the creation of a customer invoice (`account.move` with `move_type = 'out_invoice'`) from one or more sale orders. The trigger is either a user clicking "Create Invoice" / "Create Invoice & Register Payment" on a confirmed sale order, or a cron job auto-invoicing prepaid orders. Odoo maps each sale order line to one or more invoice lines, applies fiscal positions, computes taxes, and creates the invoice in draft state — ready for review, editing, and posting. For postpaid orders, this flow is deferred until after delivery (picking `done`). A reversal creates a credit note via `action_reverse()`.

## Trigger Point

**User action (Path A):** `sale.order` → **Create Invoices** button → `action_invoice_create()` / `_create_invoices()`

**User action (Path B):** `sale.order` → **Create Invoice & Register Payment** button → `action_invoice_create()` + `account.payment.register` wizard

**Cron (Path C):** `sale.order._cron_auto_invoice()` → auto-invoice prepaid orders past a threshold date

**Manual (Path D):** `sale.order` → **Create Invoice & Register Payment** wizard → from **Accounting > Customers > Invoices > Create**

Alternative triggers:
- **From delivery:** Picking `action_done()` with `order_policy == 'postpaid'` → triggers `_create_invoices()`
- **Batch invoicing:** `sale.order.action_invoice_create()` called on multiple orders simultaneously

---

## Complete Method Chain

```
PATH A: Manual "Create Invoices" from Sale Order
────────────────────────────────────────────────

1. sale.order._create_invoices(final=False, template=None)
   │
   ├─► 2. _create_invoices_from_single_order(journal_id=None)
   │     └─► 3. account.move.prepare_invoice_vals()
   │           ├─► 4. move_type = 'out_invoice'
   │           ├─► 5. partner_id = sale_order.partner_id
   │           ├─► 6. fiscal_position_id resolved
   │           │     └─► 7. account.fiscal.position.map_account() applied
   │           ├─► 8. invoice_date = current date
   │           ├─► 9. invoice_origin = sale_order.name
   │           ├─► 10. sale_team / commercial_partner_id set
   │           └─► 11. payment_reference = sale_order.reference
   │
   ├─► 12. account.move.create(vals)
   │     └─► 13. @api.model_create_multi / create() hook
   │           └─► 14. line_ids prepared as commands
   │
   ├─► 15. FOR each sale.order.line (filtered by `invoice_lines`):
   │     ├─► 16. account.move.line create (product line)
   │     │     ├─► 17. product_id, description, name from SOL
   │     │     ├─► 18. quantity = sale_line.product_uom_qty (or qty_delivered for postpaid)
   │     │     ├─► 19. price_unit = sale_line.price_unit
   │     │     ├─► 20. discount = sale_line.discount
   │     │     ├─► 21. account_id mapped via fiscal_position
   │     │     ├─► 22. tax_ids from sale_line or fiscal_position
   │     │     └─► 23. analytic_distribution = sale_line.analytic_distribution
   │     │
   │     ├─► 24. account.move.line create (tax line) — one per unique tax
   │     │     └─► 25. tax_ids applied, tax_repartition_line_id set
   │     │
   │     ├─► 26. account.move.line create (analytic line) — if analytic distribution
   │     │     └─► 27. auto-balance line created for rounding
   │
   ├─► 28. _compute_invoice_taxes_data()   [computes tax amounts]
   │     └─► 29. tax_line_id amounts computed via `_recompute_tax_lines()`
   │
   ├─► 30. account.move write(state='posted')   [IF auto_post = True]
   │     └─► 31. _post() → _reconcile_moves()
   │
   └─► 32. _invoice_paid_hook()
         └─► 33. mail.notification sent to followers

PATH B: Manual "Create Invoice & Register Payment"
───────────────────────────────────────────────────

34. sale.order._create_invoices()   [same as steps 1-12]
    │
    └─► 35. account.payment.register wizard opened
          └─► 36. account.payment.create()
                ├─► 37. journal_id resolved (bank/cash)
                ├─► 38. amount = invoice.amount_total
                ├─► 39. partner_id, partner_type = 'customer'
                └─► 40. account.move.line created (receivable line)
    └─► 41. account.move.line reconciled with payment
          └─► 42. invoice state = 'posted' (fully paid)

PATH C: Cron auto-invoice (prepaid orders)
──────────────────────────────────────────

43. sale.order._cron_auto_invoice()
    │
    └─► 44. _get_auto_invoiceable_orders()
          ├─► 45. domain: state='sale', invoice_status='no', order_policy='prepaid'
          └─► 46. date <= today (expiry check)
    └─► 47. for each order: _create_invoices()
          └─► 48. account.move created in draft (auto_post=False by default)

PATH D: Postpaid trigger from delivery (sale-to-delivery-flow Step 45)
──────────────────────────────────────────────────────────────────────

49. stock.picking.action_done()
    │
    └─► 50. sale.order._create_invoices() triggered
          └─► 51. Same as steps 1-12
                └─► 52. quantity = qty_delivered (not ordered qty)
```

---

## Decision Tree

```
sale.order._create_invoices()
│
├─► invoice_policy (order_policy) check:
│  ├─► 'prepaid'  → invoice qty = product_uom_qty (ordered qty) — created AT confirmation
│  ├─► 'manual'   → no auto invoice — user triggers manually
│  └─► 'postpaid' → invoice qty = qty_delivered — created AFTER delivery
│
├─► invoice_method (on sale.order.line) overrides order-level policy per line?
│  └─► IF any line has custom invoice_method: mix of qty types applied
│
├─► Lines to invoice:
│  ├─► Lines with invoice_status = 'to_invoice' → included
│  ├─► Lines with invoice_status = 'no' → excluded
│  └─► Lines already invoiced → excluded (invoiceable qty = 0)
│
├─► Fiscal position check:
│  ├─► Partner has fiscal_position_id?
│  │     └─► account.mapped() on taxes and accounts applied
│  └─► No fiscal position → default accounts from product/category
│
├─► journal_id resolved:
│  ├─► Context 'default_journal_id' → used if present
│  ├─► sale_order.journal_id → used if set
│  └─► Default: sales journal for company
│
└─► Auto-post?
   └─► IF template used with auto_post=True → step to 'posted' immediately
   └─► ELSE → state = 'draft' for manual review before posting
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `account_move` | Created | `move_type = 'out_invoice'`, `state`, `partner_id`, `invoice_date`, `invoice_origin`, `amount_total` |
| `account_move_line` | Created (2-3 lines per invoice line: product + tax + balance) | `product_id`, `account_id`, `debit`, `credit`, `tax_line_id`, `analytic_distribution` |
| `sale_order` | Updated | `invoice_count`, `invoice_status = 'invoiced'` |
| `sale_order_line` | Updated | `qty_invoiced`, `invoice_lines` (M2M) |
| `account_payment` | Created (Path B only) | `partner_id`, `amount`, `journal_id`, `state = 'posted'` |
| `account_move_reconciliation` | Updated (Path B only) | `matched_credit_ids` / `matched_debit_ids` linking invoice to payment |
| `mail_mail` | Created | Notification queued to partner |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| No lines with qty to invoice | `UserError: "Nothing to invoice"` | `_create_invoices()` checks `if not invoiceable_lines` |
| Missing sale account on product | `UserError: "No sale account defined"` | `product.product._get_product_accounts()` must return sale account |
| Fiscal position maps to inactive account | `ValidationError` | Account `active=True` check in `map_account()` |
| Tax on product has no tax account | `UserError` | Tax must have `invoice_repartition_line_ids` configured |
| Partner has no customer account | `UserError: "No receivable/payable account"` | `partner.property_account_receivable_id` must be set |
| Multi-company: invoice in wrong company | `AccessError` | `company_id` enforced on `account.move` |
| User lacks billing rights | `AccessError` | `group_account_invoice` required for `_create_invoices()` |
| Duplicate invoice (already created for same lines) | Warning or no-op | `invoice_status = 'invoiced'` prevents re-invoice |
| Currency mismatch | `UserError` | Invoice currency must match order currency |
| Invoice amount exceeds tolerance | `UserError` | Payment registration checks amount vs invoice amount |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Invoiceable qty consumed | `sale.order.line` | `qty_to_invoice` reduced, `qty_invoiced` increased |
| Order-level invoice status | `sale.order` | `invoice_status` → 'invoiced' if all lines fully invoiced |
| Partner accounting data used | `res.partner` | Invoice address, fiscal position, payment terms applied |
| Fiscal position mapped | `account.account` | Sale account swapped per `account.fiscal.position` mapping |
| Taxes computed and recorded | `account.tax` | Tax amounts calculated via `_compute_tax()` |
| Analytic distribution applied | `account.analytic.distribution` | Analytic lines created linked to sale line distribution |
| Sequence number consumed | `ir.sequence` | Next invoice number from `account.journal` sequence |
| Mail notification queued | `mail.mail` | Customer notified of draft invoice (if configured) |
| Payment reconciled | `account.move.line` | `matched_debit_ids` / `matched_credit_ids` set if payment registered |
| Stock valuation (if delivered) | `account.move.line` | If `stock_account` installed, cost of goods sold entry created |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `_create_invoices()` | Current user | `group_sale_salesman` + `group_account_invoice` | Combined rights for billing |
| `account.move.create()` | `sudo()` internally | Write on `account.move` | Called within `create()` context |
| `account.move.line create()` | `sudo()` internally | Write on `account.move.line` | Framework creates lines |
| `fiscal_position.map_account()` | Current user | Read on `account.account` | Respects record rules |
| `_compute_invoice_taxes_data()` | `sudo()` (system) | System — tax computation | Needs cross-record write |
| `account.move.action_post()` | Current user | `group_account_invoice` | Posting is a user action |
| `account.payment.create()` | Current user | `group_account_user` | Payment creation rights |
| `_invoice_paid_hook()` | `sudo()` (system) | System | Side effects hook |
| `mail.notification` | `mail.group` | Public | Follower-based notification |

**Key principle:** Invoice creation runs as the **current user** with billing rights. Line creation uses `sudo()` internally because sale order lines may reference accounts/products the user cannot directly write to. Custom overrides that bypass `super()` may break this security model.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1–33   ✅ INSIDE transaction  — draft invoice creation (all or nothing)
Steps 34–42  ✅ INSIDE transaction  — payment registration (atomic with invoice)
Steps 43–48  ✅ INSIDE transaction  — cron auto-invoice (per order, atomic)
Steps 43–47  ❌ Outside for each order — cron iterates in batches
Step 33      ❌ OUTSIDE transaction — mail.notification queued via ir.mail_server
Step 52      ✅ INSIDE transaction  — postpaid invoice from delivery
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1–33 | ✅ Atomic | Rollback on any error — no draft invoice created |
| Draft invoice unlink on rollback | ✅ Automatic | ORM cascade deletes lines on rollback |
| `action_post()` | ✅ Atomic (with journal validation) | Fails if journal is locked or date is locked |
| Payment registration | ✅ Atomic | Payment + reconciliation rolled back together |
| `mail.mail` notification | ❌ Async queue | Retried by `ir.mail_server` cron if failed |
| Tax computation | ✅ Atomic | Taxes recomputed on rollback |
| `ir.sequence` number | ✅ Atomic | Consumed on `create()`, freed on rollback (DB TX rollback) |

**Rule of thumb:** Draft invoice creation is fully **atomic** — if any step fails, the entire invoice is rolled back. Only `mail.mail` and external integrations (like EDI) happen outside the transaction.

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| Double-click "Create Invoices" | ORM creates only one invoice; `invoice_status = 'invoiced'` after first run prevents second |
| Re-trigger on same order | `action_invoice_create()` with `invoice_status = 'invoiced'` returns existing invoice IDs |
| Multiple orders in batch | Each order creates its own invoice; intra-order idempotent |
| Re-open draft invoice and re-create | Must delete draft invoice first; then re-create works |
| Payment registered twice (race) | Unique constraint on `account.payment` journal + sequence prevents duplicate payments |
| Cron re-runs on same order | `invoice_status` guard prevents duplicate invoice creation |
| Manual create on already-invoiced lines | `qty_to_invoice = 0` → `UserError: "Nothing to invoice"` |

**Common patterns:**
- **Idempotent:** `action_invoice_create()` (invoice_status guard), re-running on draft invoice (updates same record)
- **Non-idempotent:** `ir.sequence` number consumed (unique per invoice), `account.move.line` creates (new records each time), payment reconciliation records (unique constraint)

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 3 | `_prepare_invoice_vals()` | Customize invoice header vals | `self, final=False` | Return custom `vals` dict before `create()` |
| Step 12 | `account.move.create()` | Invoice record creation | `vals` | Override `create()` with vals processing |
| Step 15–27 | `_prepare_invoice_lines()` | Customize per-line creation | `self, order_lines` | Return custom `vals_list` for line `create()` |
| Step 24 | `_compute_tax_ids()` | Dynamic tax computation per line | `self, line, fiscal_pos` | Return custom `tax_ids` for each line |
| Step 28 | `_compute_invoice_taxes_data()` | Tax recalculation | `self` | Override to add/remove tax lines |
| Post-create | `_invoice_created_hook()` | Post-invoice creation side effects | `self, invoice` | Called after invoice is created |
| Post-post | `_invoice_post_hook()` | Post-invoice posting side effects | `self, invoice` | Called after `action_post()` |
| Payment | `_invoice_paid_hook()` | Post-payment side effects | `self, invoice` | Called after payment reconciliation |
| Template | `_get_invoice_template()` | Choose invoice template per order | `self` | Return `mail.template` record |
| Line grouping | `_group_sale_order_lines()` | Group multiple SOLs into one invoice | `self, orders` | Override for consolidated invoicing |

**Standard override pattern:**
```python
# WRONG — replaces entire method
def _create_invoices(self, final=False):
    # your code

# CORRECT — extends with super()
def _create_invoices(self, final=False):
    res = super()._create_invoices(final=final)
    # your additional code
    return res
```

**Odoo 19 specific hooks:**
- `sale.order._create_invoices()` is the main entry point — override to customize header vals
- `sale.order._prepare_invoice_vals()` called to prepare the vals dict before `account.move.create()`
- `account.move` has `write()` hooks: `_invoicing_late_items()` for aging, `_get_late_late_move_message()` for follow-up
- `account.move.line` uses `_compute_name()` for line naming — override if custom descriptions needed
- Invoice grouping: `_group_sale_order_lines()` controls whether multiple SOLs go to one invoice or separate

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Overriding `action_invoice_create()` without calling `super()` — breaks line filtering and status updates
- Directly creating `account.move.line` records without going through the ORM — bypasses fiscal position and tax mapping

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow. Critical for understanding what is and isn't reversible.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| Draft invoice (`state = 'draft'`) | `unlink()` | `account.move.unlink()` | Deletes invoice and all lines; sale lines' `qty_invoiced` reset |
| Posted invoice (`state = 'posted'`) | **Credit note** | `action_reverse()` / `action_credit_note` | Creates new `out_refund` move; original remains |
| Posted + paid invoice | **Credit note + refund** | `action_reverse()` → refund payment | Money refunded to customer |
| Partial credit note | Partial reversal | `action_reverse()` for specific qty | New refund invoice with partial amounts |
| Posted invoice (unpaid) | **Cancel** | `action_cancel()` | Moves to `cancel` state; can then delete |
| Payment on invoice | **Unreconcile** | `button_draft()` on payment | Breaks reconciliation; invoice returns to 'posted' |
| Sale order invoiced but not paid | Credit note first, then cancel SO | `action_reverse()` + `action_cancel()` | Both steps needed |

**Important:** This flow is **partially reversible**:
- Draft invoices → can be fully deleted (unlinked); sale order `qty_invoiced` is reset
- Posted invoices → **immutable** — cannot delete, only reverse via credit note
- Credit note (`out_refund`) creates a new `account.move` record — original `out_invoice` remains in database
- Paid invoices → must refund payment first, then reverse invoice
- Partial reversals create a new credit note for the partial amount

**Credit Note Wizard flow:**
1. User opens posted invoice → clicks **Add Credit Note** or **Reverse**
2. `account.move.reversal` wizard opens: select date, reason, journal
3. `action_reverse()` creates `out_refund` record (credit note)
4. Credit note is in `draft` state → user posts it
5. If payment was registered: refund payment creates `account.payment` (outgoing)
6. Original invoice remains `posted` but is linked to credit note via `reversal_id`

---

## Alternative Triggers

> *All the ways this flow can be initiated — not just the primary user action.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `_create_invoices()` button | Sale order form | Manual |
| User action | "Create Invoice & Register Payment" wizard | Sale order form | Manual |
| Cron scheduler | `_cron_auto_invoice()` | Server startup | Configurable (e.g., daily) |
| From delivery | `_create_invoices()` triggered in `stock.picking.action_done()` | Automatic | Per delivery |
| Batch invoice | `action_invoice_create()` on many orders | Sale order list | Manual bulk action |
| Portal / e-commerce | Customer requests invoice via portal | Customer portal | On demand |
| EDI / API | External system POSTs to invoice creation endpoint | Web service | On demand |
| Automated action | `base.automation` rule | Server action | On rule match |
| Subscription renewal | `sale.subscription` auto-invoice | Subscription module | On renewal date |

**For AI reasoning:** When asked "what happens if X?", trace all triggers. The `order_policy` determines timing — prepaid orders are invoiced at confirmation, postpaid at delivery. `invoice_status` on sale lines is the definitive record of what's been billed.

---

## Related

- [Modules/Sale](Modules/sale.md) — Sale module reference
- [Modules/Account](Modules/account.md) — Account/invoice module reference
- [Flows/Sale/quotation-to-sale-order-flow](Flows/Sale/quotation-to-sale-order-flow.md) — Sale order confirmation (prepaid invoices created here)
- [Flows/Sale/sale-to-delivery-flow](Flows/Sale/sale-to-delivery-flow.md) — Delivery confirmation triggers postpaid invoices
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — Workflow pattern reference
- [Core/API](Core/API.md) — @api decorator patterns
