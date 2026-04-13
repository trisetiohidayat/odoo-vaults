---
type: flow
title: "Customer Invoice Creation Flow"
primary_model: account.move
trigger: "User action — Sale Order → Create Invoice / Account → Customers → Invoices → Create"
cross_module: true
models_touched:
  - account.move
  - account.move.line
  - sale.order
  - res.partner
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Account/invoice-post-flow](odoo-19/Flows/Account/invoice-post-flow.md)"
  - "[Flows/Account/payment-flow](odoo-19/Flows/Account/payment-flow.md)"
  - "[Flows/Sale/quotation-to-sale-order-flow](odoo-19/Flows/Sale/quotation-to-sale-order-flow.md)"
related_guides:
  - "[Business/Account/chart-of-accounts-guide](odoo-19/Business/Account/chart-of-accounts-guide.md)"
  - "[Business/Sale/sales-process-guide](odoo-19/Business/Sale/sales-process-guide.md)"
source_module: account
source_path: ~/odoo/odoo19/odoo/addons/account/
created: 2026-04-06
updated: 2026-04-06
version: "1.0"
---

# Customer Invoice Creation Flow

## Overview

Creating a customer invoice (`out_invoice`) in Odoo — either programmatically from a confirmed Sale Order, manually via the accounting menu, or automatically via a recurring invoicing cron job. Invoice creation in draft state lays the groundwork for posting, which locks the journal entries and makes the invoice legally binding.

## Trigger Point

Three entry points for this flow:

1. **From Sale Order** — `sale.order._create_invoices()` triggered by "Create Invoice" button on a confirmed SO
2. **Manual** — User navigates to `Accounting → Customers → Invoices → Create`
3. **Scheduled (cron)** — `sale.order._cron_generate_invoice()` runs on recurring contracts or subscription lines

---

## Complete Method Chain

```
1. account.move.create({
       'move_type': 'out_invoice',
       'partner_id': partner.id,
       'invoice_date': date
   })
   │
   ├─► 2. _onchange_partner_id()
   │     ├─► 3. fiscal_position resolved from partner.fiscal_position_id
   │     │     └─► 4. accounts/taxes remapped per fiscal_position.map_*()
   │     ├─► 5. payment_terms set from partner.property_payment_term_id
   │     └─► 6. invoice_payment_term_id field populated
   │
   ├─► 7. invoice_date_due computed from invoice_payment_term_id
   │     └─► 8. _compute_date_sequential() — due dates per installment line
   │
   ├─► 9. _onchange_journal()
   │     └─► 10. journal_id set from default journal (account_id of move_type)
   │
   ├─► 11. FOR EACH line from SO (sale.order.line) or manual entry:
   │
   │     ├─► 12. account.move.line.create() — product line
   │     │     ├─► 13. name = product.name_get()[0][1]
   │     │     ├─► 14. account_id = income account resolved via:
   │     │     │     ├─► product.categ_id.property_account_income_categ_id
   │     │     │     └─► OR fiscal_position.map_account()
   │     │     ├─► 15. debit = 0, credit = price_subtotal
   │     │     ├─► 16. analytic_distribution from sale.order.line
   │     │     │     └─► 17. analytic_account_id / analytic_distribution JSON
   │     │     └─► 18. quantity, product_uom_id from sale line
   │     │
   │     └─► 19. Tax computation:
   │           ├─► 20. tax_id._compute_all(
   │           │       price_unit, quantity, currency, product
   │           │     )
   │           │     └─► 21. tax amounts calculated per line (incl. repartition)
   │           │           └─► 22. FOR EACH tax result → account.move.line
   │           │                 ├─► 23. name = tax_id.name
   │           │                 ├─► 24. account_id = tax_id.account_id
   │           │                 └─► 25. credit = tax_amount (rounded)
   │           └─► 26. round() applied per company currency precision
   │
   ├─► 27. _onchange_price_subtotal() triggered per line
   │     └─► 28. price_subtotal = unit_price * qty * (1 - discount%)
   │
   ├─► 29. _onchange_amount() — recalculate totals
   │     ├─► 30. amount_untaxed = SUM(line.credit for non-tax lines)
   │     ├─► 31. amount_tax = SUM(tax line credits)
   │     └─► 32. amount_total = amount_untaxed + amount_tax
   │
   ├─► 33. _compute_payments_widget_terms() — due date schedule
   │     └─► 34. payment_terms widget populated with installment dates
   │
   └─► 35. state = 'draft' (default, not yet posted)
         └─► 36. mail.activity scheduled if auto-activity set on partner
```

---

## Decision Tree

```
Is invoice from a Sale Order?
├─► YES: sale.order._create_invoices() pre-fills lines from sale.order.line
└─► NO (manual): user enters lines manually

move_type = 'out_invoice'?
├─► YES → Dr. Customer (Accounts Receivable), Cr. Revenue + Tax
└─► Check other types:

├─► move_type = 'out_refund' → Dr. Revenue (reverse), Cr. Customer
├─► move_type = 'in_invoice'  → Dr. Expense, Cr. Vendor (Accounts Payable)
└─► move_type = 'in_refund'   → Dr. Vendor, Cr. Expense

fiscal_position set on partner?
├─► YES → accounts remapped via fiscal_position.map_account()
│          taxes remapped via fiscal_position.map_tax()
└─► NO → use default accounts from product/category

partner.customer_rank > 0?
├─► YES → customer invoice flow (out_*)
└─► NO → vendor bill flow (in_*) — different journal defaults

invoice_payment_term_id set?
├─► YES → invoice_date_due computed from payment term installments
└─► NO → invoice_date_due = invoice_date (immediate payment)
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `account_move` | Created | move_type='out_invoice', state='draft', partner_id, invoice_date, name (draft prefix) |
| `account_move_line` | Created (1 per product line + 1 per tax) | debit, credit, account_id, partner_id, move_id |
| `sale_order_invoice_rel` | Created | Links invoice to originating SO for reconciliation |
| `account_payment_term_line` | Read (not created) | Used to compute invoice_date_due |
| `mail_followers` | Updated | Partner and sales team followers subscribed |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| partner_id not set | `ValidationError` | ORM `required=True` on partner_id |
| journal_id not found for move_type | `UserError` | "No journal found for..." — configure journal in Settings |
| tax_id has no account_id configured | `UserError` | Tax must have `account_id` set in tax definition |
| product has no income account | `ValidationError` | Property `property_account_income_categ_id` not set on category |
| duplicate SO invoice (SO already fully invoiced) | `UserError` | `sale.action_view_sale_advance_payment_vals` blocks re-invoice |
| user lacks `account.group_account_invoice` | `AccessError` | ACL restriction on `account.move` create |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Partner balance updated | `account.move.line` | AR line created (debit or credit depending on type) |
| SO invoice count updated | `sale.order` | `invoice_count` field incremented |
| Revenue recognized | `account.account` | Income account credited on each product line |
| Tax liability recorded | `account.move.line` | Tax payable account credited (if tax is payable type) |
| Follower added | `mail.followers` | Partner's contact added as follower for notifications |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `account.move.create()` | Current user | `group_account_invoice` | Respects record rules |
| `_onchange_partner_id()` | Current user | Read on `res.partner` | Reads fiscal_position from partner |
| `account.move.line.create()` | Current user | `group_account_invoice` | Line-level ACL on account_id |
| Tax computation | `sudo()` | System (no ACL) | `_compute_all` runs internally |
| `sale.order._create_invoices()` | Current user | `group_sale_manager` | SO must be confirmed first |
| Mail activity creation | `mail.group` | Public | Follower-based, respects `mail.channel` ACL |

**Key principle:** Invoice creation runs as the **current logged-in user**, applying all partner-based access rules and record-level restrictions.

---

## Transaction Boundary

```
Steps 1-36  ✅ INSIDE transaction  — atomic (all or nothing)
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| All create + compute | ✅ Atomic | Rollback on any error |
| Mail activity | ✅ Within ORM | Rolled back with transaction |

**Rule of thumb:** Invoice creation is fully atomic — if any step fails (e.g., missing tax account), the entire `create()` rolls back and no partial invoice is saved.

---

## Idempotency

> *What happens when this flow is executed multiple times.*

| Scenario | Behavior |
|----------|----------|
| Double-click "Create Invoice" on SO | ORM deduplicates — one invoice per click, SO blocks second if already fully invoiced |
| Re-save draft invoice | `write()` re-runs onchange cascades, no new record |
| Multiple SO lines with same product | Separate line records created (one per SO line) — not deduplicated |
| Manual re-create from same SO | Raises `UserError` — "Invoice already exists for this order" |

**Non-idempotent points:**
- Each `account.move.create()` always creates a new record (no dedup on same vals)
- Sequence not consumed until `action_post()` is called
- SO `invoice_count` is incremented on each create

---

## Extension Points

> *Where and how developers can override or extend this flow.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Pre-create | `_onchange_partner_id()` | Add custom field sync on partner change | self | Extend with `super()` |
| Pre-line | `_onchange_purchase_order_id()` (in `purchase` module) | Auto-fill lines from PO | self | Similar to SO pattern |
| Line creation | `_onchange_product()` | Custom product field population | self | Add field defaults |
| Tax override | `_prepare_tax_lines()` | Custom tax line generation | self, tax_results | Override tax computation |
| Totals override | `_onchange_amount()` | Custom total rounding logic | self | Extend rounding precision |
| Pre-save hook | `_check_balanced()` | Validate invoice balance before save | self | `@api.constrains` decorator |

**Standard override pattern:**
```python
# CORRECT — extends with super()
def _onchange_partner_id(self):
    res = super()._onchange_partner_id()
    self.invoice_origin = self.partner_id.ref  # custom field sync
    return res
```

**Deprecated override points to avoid:**
- `@api.one` anywhere (deprecated in Odoo 19)
- Direct field assignment in onchange (use `self[field] = value` pattern)

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| Draft invoice (not posted) | `unlink()` | `record.unlink()` | Removes all lines; SO invoice_count decremented |
| Posted invoice | `action_reverse()` | Creates `account.move` with move_type='out_refund' | Original entry preserved; credit note is new record |
| Posted invoice (alternative) | `action_register_payment` → overpayment credit | Partial reversal via payment | Only works if payment hasn't been reconciled |

**Important:** Posted invoices cannot be deleted — only reversed via credit note (`action_reverse()`). The original `account.move` record is locked and remains in the ledger for audit trail.

**Credit Note Reverse Flow:**
```
Posted Invoice (out_invoice)
   └─► action_reverse()
        ├─► Creates new account.move with move_type='out_refund'
        │     └─► Lines: Dr. Revenue (original) / Cr. Customer
        ├─► original.move.reversal_id = credit_note.id
        └─► credit_note.state = 'posted' (also locked)
```

---

## Alternative Triggers

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `action_create_invoice()` button on SO | Interactive | Manual |
| User action | Invoice form → Create button | Accounting menu | Manual |
| Cron scheduler | `sale.order._cron_generate_invoice()` | Recurring contracts | Daily (configurable) |
| Onchange cascade | `_onchange_partner_id()` | Field change on form | On demand |
| Automated action | `base.automation` | Rule-triggered invoice | On rule match |
| API (external) | `POST /api/account.move` | External system integration | On demand |

---

## Related

- [Modules/Account](odoo-18/Modules/account.md) — Account module reference
- [Modules/Sale](odoo-18/Modules/sale.md) — Sale module reference (SO invoice creation)
- [Flows/Account/invoice-post-flow](odoo-19/Flows/Account/invoice-post-flow.md) — Next step: posting the invoice
- [Flows/Account/payment-flow](odoo-19/Flows/Account/payment-flow.md) — Payment registration after posting
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — Workflow pattern reference
- [Core/API](odoo-18/Core/API.md) — @api decorator patterns