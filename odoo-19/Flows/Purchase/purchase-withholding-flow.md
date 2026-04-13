---
type: flow
title: "Purchase Withholding Tax Flow"
primary_model: account.move
trigger: "User — Create vendor bill with withholding tax / System — Tax computation on bill post"
cross_module: true
models_touched:
  - account.move
  - account.move.line
  - account.tax
  - account.tax.group
  - account.payment
  - account.reconcile.model
  - res.partner
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Purchase/purchase-to-bill-flow](Flows/Purchase/purchase-to-bill-flow.md)"
  - "[Flows/Account/payment-flow](Flows/Account/payment-flow.md)"
  - "[Flows/Account/invoice-post-flow](Flows/Account/invoice-post-flow.md)"
source_module: l10n_id
source_path: ~/odoo/odoo19/odoo/addons/l10n_id/
created: 2026-04-07
updated: 2026-04-07
version: "1.0"
---

# Purchase Withholding Tax Flow

## Overview

The Purchase Withholding Tax Flow handles vendor bills that include tax deductions at source — a common requirement in many tax jurisdictions including Indonesia (PPh 21/22/23/26), India (TDS), and Philippines (expanded withholding). When a vendor bill with a withholding tax is posted, Odoo splits the accounting entry into three components: the **gross amount** payable to the vendor, the **withholding amount** held back and credited to a tax payable account, and the **net amount** actually paid to the vendor. This ensures proper tax compliance, accurate tax payable reporting, and correct cash flow accounting. The withholding amount is later remitted to the tax authority (DJP in Indonesia) through a separate tax payment process.

---

## Trigger Point

**Primary trigger:** `account.move.action_post()` is called when a user posts a vendor bill (`move_type='in_invoice'`) that has one or more lines with a `withholding_tax_id` set. This is a user action triggered by clicking the **Post** button on the vendor bill form.

**Secondary trigger (pre-computation):** As the user fills in invoice lines and selects taxes, `account.move._compute_tax_totals()` is called via the `@api.depends` decorator on each field change. This computes both the regular tax amount and the withholding amount before the user even clicks Post.

**Split entry trigger:** When `action_post()` executes, the `withhold.tax.compute()` method is invoked internally, determining the withholding amount (e.g., 15% of gross for PPh 23 on service payments). The resulting withholding lines are injected into `account.move.line` alongside the regular tax lines.

---

## Complete Method Chain

```
STEP 1 — Vendor Bill Creation
───────────────────────────────────
1. account.move.create({
      move_type='in_invoice',
      partner_id=vendor_id,
      invoice_date='2026-04-07',
      invoice_line_ids: [
        (0,0,{
           product_id: service_product,
           price_unit: 10_000_000,
           tax_ids: [(6,0,[tax_vat_11pct_id])],
           withholding_tax_id: tax_pph23_id   ← key field
        })
      ]
   })
      │
      ├─► 2. account.move._compute_tax_totals()
      │        └─► 3. account.tax._compute_tax_totals_json()
      │              ├─► 4. Compute regular VAT: 10_000_000 * 11% = 1_100_000
      │              └─► 5. withhold.tax.compute(tax_pph23_id, 10_000_000)
      │                    ├─► 6. rate = tax_pph23_id.amount = 15%
      │                    ├─► 7. base = gross_amount = 10_000_000
      │                    └─► 8. withholding_amount = 10_000_000 * 15% = 1_500_000
      │                          └─► 9. tax_totals dictionary updated:
      │                                {
      │                                  amount_untaxed: 10_000_000,
      │                                  amount_tax: 1_100_000,
      │                                  amount_withholding: 1_500_000,
      │                                  amount_total: 10_000_000 + 1_100_000 - 1_500_000 = 9_600_000
      │                                }
      │
      └─► 10. account.move.line created (draft lines preview):
               ├─► Line 1: Service — 10_000_000 Dr (expense/vendor)
               ├─► Line 2: VAT PPN 11% — 1_100_000 Dr (tax receivable)
               └─► Line 3: PPh 23 Withholding — 1_500_000 Cr (tax payable)
               └─► Line 4: Net payable — 9_600_000 Cr (vendor account)

STEP 2 — Bill Posted
───────────────────────────────────
11. account.move.action_post()
      │
      ├─► 12. account.move._post() — soft validation
      │        ├─► 13. Check: all required fields filled
      │        ├─► 14. Check: journal is postable (not 'draft_only')
      │        └─► 15. Check: not already posted
      │
      ├─► 16. account.move.write({'state': 'posted'})
      │        └─► 17.-ir.sequence' consumed: NEXT-2026-04-0001
      │
      └─► 18. account.move.line records confirmed:
               ├─► 19. Line: 10_000_000 Dr → Expense/Asset account
               ├─► 20. Line: 1_100_000 Dr → VAT Input (PPN Masukan) account
               ├─► 21. Line: 1_500_000 Cr → Withholding Tax Payable (PPh 23)
               └─► 22. Line: 9_600_000 Cr → Vendor Payable account
                                                          └─► 23. fiscal_position applied:
                                                                   If vendor has fp_id:
                                                                   tax mapping: DST → DST (11%)
                                                                   withholding unchanged

STEP 3 — Payment Registration
───────────────────────────────────
24. account.payment.register() on bill
      │
      ├─► 25. account.payment.create({
               partner_id: vendor_id,
               amount: 9_600_000,     ← NET amount only
               journal_id: bank_journal,
               account_payment_method_id: transfer_method,
               payment_type: 'outbound',
               partner_type: 'supplier'
         })
      │        └─► 26. account.move.create() for payment:
      │              ├─► Dr: Vendor Payable — 9_600_000
      │              └─► Cr: Bank — 9_600_000
      │
      └─► 27. account.reconcile.model._get_write_off_account()
             └─► 28. account.move.line._reconcile_lines()
                   ├─► 29. Match vendor payable Cr (9_600_000) with payment Dr
                   └─► 30. Partial reconciliation recorded in account_partial_reconcile

STEP 4 — Tax Remittance (Separate Process)
─────────────────────────────────────────
31. account.payment.register() for PPh 23 payment to DJP
      │
      ├─► 32. Create payment journal entry:
      │        Dr: Withholding Tax Payable (PPh 23) — 1_500_000
      │        Cr: Bank — 1_500_000
      └─► 33. Res_partner._l10n_id_reconcile_withholding_pph() — match remittance
            └─► 34. Creates matching entry: payment linked to original withholding line
                  └─► 35. Tax report: PPh 23 reported in SPT Masa PPh 23
```

---

## Decision Tree

```
Vendor Bill Created
       │
       ▼
┌──────────────────────────┐
│ Any line has             │
│ withholding_tax_id?      │
└──────────┬───────────────┘
           │ NO
           ▼
    Normal invoice flow
    (post → pay vendor full amount)

           │ YES
           ▼
┌──────────────────────────┐
│ Withholding type?       │
└──────┬────────┬────┬────┘
        │        │    │
      PPh 21   PPh 22  PPh 23/26
        │        │    │
        ▼        ▼    ▼
┌──────────────────────────────┐
│ Compute withholding rate     │
│ and base amount              │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────┐
│ Fiscal position applied?│
│ (l10n_id.fp_indonesia)  │
└──────────┬───────────────┘
           │
     ┌─────┴──────┐
     │Yes         │No
     ▼            ▼
  Tax mapping  No mapping
  applied      (default)

           ▼
┌──────────────────────────┐
│ Split journal entry:     │
│                         │
│ Dr  Expense   10_000_000│
│ Dr  VAT Input   1_100_000
│ Cr  PPh Payable 1_500_000│
│ Cr  Vendor       9_600_000│
└──────────┬───────────────┘
           │
           ▼
    ┌──────────────────┐
    │ Payment to vendor │
    │ = NET amount only│
    │ 9_600_000         │
    └────────┬───────────┘
             │
             ▼
    ┌──────────────────┐
    │ Separate payment  │
    │ to DJP for PPh    │
    │ 1_500_000          │
    └──────────────────┘
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `account_move` | Created (posted) | `move_type='in_invoice'`, `state='posted'`, `amount_tax=1_100_000`, `amount_withholding=1_500_000` |
| `account_move_line` | Created (4 lines) | `withholding_tax_id`, `tax_line_id`, `tax_ids`, `account_id` (varied per line) |
| `account_tax` | Read | `amount`, `type_tax_use`, `tax_group_id`, `withholding_tax` |
| `account_tax_group` | Read | `property_tax_payable_account_id`, `property_tax_receivable_account_id` |
| `account_payment` | Created | `partner_id`, `amount=9_600_000`, `state='posted'` |
| `account_partial_reconcile` | Created | Links payable line to payment |
| `res_partner` | Read | `property_account_position_id`, `l10n_id_npwz` (NPWZ number) |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Withholding rate = 0 | Silent | No withholding created; bill posts normally |
| No NPWZ on vendor (PPh 21) | `UserError` "NPWZ number required for this withholding" | Vendor must have `l10n_id_npwz` set |
| Withholding on credit note without prior bill | `UserError` "Cannot compute withholding on refund" | Withholding only applies to `in_invoice` |
| Wrong sign on reversal | `ValidationError` | Reversing PPh should produce negative Dr/Cr, not positive |
| Payment exceeds net amount | `UserError` "Payment amount exceeds remaining payable" | Payment for vendor = only net; withholding paid separately |
| Tax authority account not set | `UserError` "No tax payable account set for tax group" | `property_tax_payable_account_id` must be configured on `account.tax.group` |
| Multiple withholding taxes on same line | `UserError` "Only one withholding tax allowed per line" | `withholding_tax_id` is a single Many2one |
| Currency mismatch | `ValidationError` "Currency mismatch between invoice and payment" | Payment currency must match bill currency |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Vendor payable updated | `account.move.line` | Cr to vendor account; matches payment on reconciliation |
| Tax receivable recorded | `account.move.line` | Dr to VAT Input account (PPN Masukan) |
| Withholding payable recorded | `account.move.line` | Cr to PPh Payable account; later remitted |
| Bill amount updated | `account.move` | `amount_total` = gross + tax - withholding |
| Tax group totals updated | `account_tax_group` | Aggregate tax payable/receivable for reporting |
| Partner's payable cleared | `account_partial_reconcile` | Vendor payable line matched with payment |
| Journal entry number | `ir.sequence` | Next number consumed from journal sequence |
| Tax reportable amount | `account.report` | Withholding amount appears in SPT Masa PPh report |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `account.move.create()` | Current user | `group_account_invoice` | User must have vendor bill creation rights |
| `_compute_tax_totals()` | Current user | Read on `account.tax` | Onchange; uses current user ACL |
| `withhold.tax.compute()` | `sudo()` | System | Pure computation; no ACL |
| `action_post()` | Current user | `group_account_invoice` | User must have posting rights |
| `account.move.line` write | `sudo()` | System | Internal line creation; bypasses ACL |
| `account.payment.create()` | Current user | `group_account_manager` | Payment creation typically manager-level |
| `_reconcile_lines()` | `sudo()` | System | Reconciliation writes; no user context |
| Tax remittance payment | Current user | `group_account_manager` | Only managers remit withholding to DJP |

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside.*

```
Steps 1-22   ✅ INSIDE transaction  — action_post() atomic
             All lines created and posted in one transaction;
             rollback on any error

Steps 24-30  ✅ INSIDE transaction  — payment registration atomic
             Payment move created, reconciled in same transaction

Steps 31-35  ✅ INSIDE transaction  — tax remittance payment atomic
             DJP payment created as separate journal entry

Steps 36+    ❌ OUTSIDE transaction — tax report (e-faktur, SPT Masa)
             Reports generated from posted records; no transaction boundary
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| `action_post()` | ✅ Atomic | Rollback: bill stays draft, no lines created |
| Payment registration | ✅ Atomic | Rollback: payment not created, bill stays unpaid |
| Tax remittance | ✅ Atomic | Rollback: DJP payment not created |
| SPT Masa report generation | ❌ Outside | Read-only; generated from posted records |
| E-faktur submission | ❌ External API | HTTP to DJP endpoint; retried via cron |

---

## Idempotency

> *What happens when this flow is executed multiple times.*

| Scenario | Behavior |
|----------|----------|
| Double-click Post button | ORM creates bill once; second click: `UserError` "Bill already posted" |
| Re-post cancelled bill | `UserError` "Cannot post cancelled entry" — state machine prevents |
| Re-create payment for same bill | Creates second payment record; bill now overpaid — reconciliation error |
| Withholding computed twice | Computed only once at post time; re-compute on edit before post only |
| Multiple withholding on same vendor | Each bill creates its own withholding lines; cumulative reporting |

---

## Extension Points

> *Where and how developers can override or extend this flow.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Pre-compute | `_compute_tax_totals()` | Modify tax totals before display | `self` | Extend with `super()` for custom withholding |
| Withholding calculation | `withhold.tax.compute()` | Custom withholding rate logic | `tax`, `base_amount` | Override in custom `l10n_id` module |
| Line creation | `_recompute_static_data()` | Add custom line logic at post | `self` | Extend `_post()` with vals dict |
| Payable account | `_get_account_by_move_line()` | Route withholding to different account | `move_line` | Override for multi-company tax accounts |
| Reconciliation | `_reconcile_revenue_payment()` | Custom matching logic | `self` | Override `account.reconcile.model` |
| Tax report | `_prepare_tax_局_report()` | Add withholding to tax return | `self` | Extend SPT Masa report method |

**Standard override pattern:**
```python
# Custom withholding computation for PPh 23
class AccountTax(models.Model):
    _inherit = 'account.tax'

    def withhold_tax_compute(self, base_amount):
        self.ensure_one()
        # Custom: if vendor is in specific category, apply different rate
        if self.env.context.get('vendor_category') == 'freelance':
            return base_amount * (self.amount + 5) / 100  # +5% surcharge
        return super().withhold_tax_compute(base_amount)
```

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| Bill posted | Cancel + Create credit note | `action_cancel()` → `action_reverse()` | Withholding tax lines reversed; PPh payable reset |
| Withholding line removed | Revert bill first | `action_draft()` → edit lines → re-post | Withholding recomputed on re-post |
| Vendor payment | Cancel payment | `action_cancel()` | Vendor payable line un-reconciled; bill becomes unpaid |
| DJP remittance payment | Reverse journal entry | `action_reverse()` | Creates opposite entry; tax payable restored |
| E-faktur submitted | Revoke on DJP portal | Manual — no Odoo method | Odoo e-faktur record marked as 'cancelled' |

**Important:** Withholding tax reversals must also update the tax payable account balance. If PPh 23 has already been remitted to DJP before the bill is cancelled, a separate correction entry must be created.

---

## Alternative Triggers

> *All the ways this flow can be initiated.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `action_post()` | Post vendor bill button | Manual |
| Import from EDI | `account.move.import_edi_doc()` | Peppol/via edi | Per invoice |
| Onchange cascade | `_compute_tax_totals()` | Tax field change | On demand |
| Automated action | `base.automation` on `account.move` | Rule-triggered | On state change |
| Batch posting | `account.move._post_mass()` | List view → Action → Post | Bulk |
| Purchase bill auto-post | `purchase.order._create_invoice()` | PO → Create Bill | Per PO receipt |

---

## Related

- [Modules/Account](Modules/account.md) — `account.move`, `account.move.line`, `account.tax` field reference
- [Flows/Purchase/purchase-to-bill-flow](Flows/Purchase/purchase-to-bill-flow.md) — PO to vendor bill creation
- [Flows/Account/payment-flow](Flows/Account/payment-flow.md) — Vendor payment and reconciliation
- [Flows/Account/invoice-post-flow](Flows/Account/invoice-post-flow.md) — General invoice posting flow
- [Business/Account/l10n-id-tax-guide](Business/Account/l10n-id-tax-guide.md) — Indonesian tax guide (PPN, PPh 21/22/23/26)
- [Core/API](Core/API.md) — `@api.depends` and tax computation decorators
