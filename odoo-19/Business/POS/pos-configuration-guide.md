---
type: guide
title: "POS Configuration Guide"
module: pos
submodule: pos-config
audience: business-consultant, pos-manager
level: 2
prerequisites:
  - pos_config_created
  - payment_methods_defined
  - products_available
  - pos_users_assigned
  - invoice_journal_configured
estimated_time: "~15 minutes"
related_flows:
  - "[Flows/POS/pos-session-flow](Flows/POS/pos-session-flow.md)"
  - "[Flows/POS/pos-order-to-invoice-flow](Flows/POS/pos-order-to-invoice-flow.md)"
  - "[Flows/Account/invoice-creation-flow](Flows/Account/invoice-creation-flow.md)"
related_guides:
  - "[Business/Account/chart-of-accounts-guide](Business/Account/chart-of-accounts-guide.md)"
source_module: pos
created: 2026-04-07
updated: 2026-04-07
version: "1.0"
---

# POS Configuration Guide

> **Quick Summary:** This guide covers the end-to-end setup and operation of a Point of Sale configuration in Odoo 19 — from creating the POS, defining payment methods and products, opening and managing sessions, through closing and reconciling cash.

**Actor:** POS Manager, Cashier, Business Consultant
**Module:** Point of Sale (pos)
**Use Case:** Configure, open, operate, and close a POS session
**Difficulty:** Easy (cash only) / Medium (mixed payments)

---

## Prerequisites Checklist

Before starting, ensure the following are configured. Skipping these will cause errors or missing features.

- [ ] **[POS Configuration created]** — `Point of Sale → Configuration → Point of Sale → Create`
- [ ] **[Payment Methods defined]** — At least one payment method (cash or bank) added to the POS
- [ ] **[Products available]** — Products with proper pricing and taxes configured in Inventory
- [ ] **[Pricelist set]** — Default pricelist assigned to POS or product
- [ ] **[POS Users assigned]** — Users added to the `Point of Sale` group under Settings → Users
- [ ] **[Invoice Journal configured]** — Journal selected in POS settings for invoice generation
- [ ] **[Company set]** — Company assigned to POS configuration (multi-company environments)
- [ ] **[Warehouse set]** — Warehouse selected for stock operations (if using stock)
- [ ] **[Cash Control enabled]** — Recommended for cash-based POS (enables cash box operations)

> **Critical:** If **no payment method** is added to the POS configuration, the session will fail to open with "No payment method available." If **no invoice journal** is configured, the Invoice button will raise "No invoice journal configured for this POS session."

---

## Quick Access

| Type | Link | Description |
|------|------|-------------|
| Technical Flow | [Flows/POS/pos-session-flow](Flows/POS/pos-session-flow.md) | Full session lifecycle method chain |
| Technical Flow | [Flows/POS/pos-order-to-invoice-flow](Flows/POS/pos-order-to-invoice-flow.md) | Order-to-invoice method chain |
| Module Reference | [Modules/pos](Modules/pos.md) | Complete POS model and field reference |
| Configuration | [Modules/pos](Modules/pos.md) → Payment Methods | Payment method setup details |
| Related Guide | [Business/Account/chart-of-accounts-guide](Business/Account/chart-of-accounts-guide.md) | Accounting journals and accounts |

---

## Use Cases Covered

This guide covers the following use cases. Jump to the relevant section:

| # | Use Case | Page | Difficulty |
|---|----------|------|-----------|
| 1 | Configure POS with cash payment only | [#use-case-1-configure-pos-with-cash-only](#use-case-1-configure-pos-with-cash-only.md) | Easy |
| 2 | Configure POS with mixed payments (cash + card + pay later) | [#use-case-2-configure-pos-with-mixed-payments](#use-case-2-configure-pos-with-mixed-payments.md) | Medium |
| 3 | Open, operate, and close a POS session with reconciliation | [#use-case-3-open-operate-and-close-session-with-reconciliation](#use-case-3-open-operate-and-close-session-with-reconciliation.md) | Easy |

---

## Use Case 1: Configure POS with Cash Only

### Scenario

A small retail shop needs a simple POS that accepts only cash payments. The cashier opens a session at the start of the day, processes sales, and closes at the end of the day with cash reconciliation.

### Steps

#### Step 1 — Create POS Configuration

Navigate to: `Point of Sale → Configuration → Point of Sale → Create`

| Field | Value | Required | Auto-filled |
|-------|-------|----------|-------------|
| **Name** | Shop POS | Yes | — |
| **Company** | Your Company | Yes | From current company |
| **Warehouse** | Your Warehouse | Yes | From company |
| **Invoice Journal** | Sales Journal | Yes | Manual selection |
| **Pricelist** | Default Public Pricelist | Yes | From company |
| **PoS Order Policy** | Order → Bill | No | Manual selection |

> **System Behavior:** The `PoS Order Policy` controls when accounting entries are created:
> - `Order → Bill`: Entries created when order is placed
> - `Payment → Bill`: Entries created only when payment is registered

#### Step 2 — Add Cash Payment Method

In the **Payment Method** tab, click **Add a line**:

| Field | Value | Notes |
|-------|-------|-------|
| **Payment Method Name** | Cash | Displayed at POS |
| **Payment Type** | Cash | Odoo classifies as cash |
| **Journal** | Cash | Select cash journal (or create one in Accounting) |
| **Receivable Account** | 110000 (Cash) | Auto-populated from journal |
| **Is Cash Count** | Yes | Enables cash box operations |
| **Split Transactions** | No | Single customer per transaction |

> **System Trigger:** When `Is Cash Count = Yes`, the payment method participates in cash box operations (opening float, cash box open/close). When `Split Transactions = Yes`, each customer gets a separate receivable line (for restaurant dividers).

#### Step 3 — Configure Cash Control (Recommended)

Expand the **Cash Control** section on the POS form:

| Field | Value | Notes |
|-------|-------|-------|
| **Cash Control** | Yes | Enables opening/closing cash counts |
| **Maximum Difference Allowed** | 0.50 | Tolerance for cash discrepancies |
| **Payment Method** | Cash | Select the cash payment method above |

> **System Behavior:** With cash control enabled, Odoo will:
> - Require the cashier to enter the starting cash box amount when opening
> - Require a cash count when closing
> - Record `account.bank.statement.line` entries for cash differences (loss or profit)
> - Post differences to `loss_account_id` or `profit_account_id` on the cash journal

#### Step 4 — Configure Other Settings

| Field | Value | Notes |
|-------|-------|-------|
| **Allow Order Deletion** | Yes | Cashiers can delete draft orders |
| **Allow Credit Note** | Yes | Enables refunds |
| **Set Current User as CL** | Yes | Auto-assigns current user as cashier |
| **Update Stock Quantities** | At Session Close | Recommended (avoids partial stock issues) |

#### Step 5 — Assign Users to POS

Navigate to: `Point of Sale → Configuration → Point of Sale → [Your POS] → General Information`

Click **Allowed Users** and select the users who may operate this POS.

> **Side Effect:** Only users in the `Point of Sale` group AND the allowed users list can open sessions for this POS. If no allowed users are set, all POS group users can access it.

**Expected Results Checklist:**
- [ ] POS configuration saved and visible in POS list
- [ ] Cash payment method visible in Payment Methods tab
- [ ] Cash control section expanded with tolerance set
- [ ] Invoice journal selected (e.g., Sale Journal)
- [ ] Users assigned (or field left empty for all POS users)
- [ ] Company and warehouse correctly set

---

## Use Case 2: Configure POS with Mixed Payments

### Scenario

A retail store accepts cash, debit/credit cards, and offers "Pay Later" (accounts receivable) for loyalty customers. The POS must be configured with three payment methods and proper receivable accounts.

### Steps

#### Step 1 — Create or Edit POS Configuration

Navigate to: `Point of Sale → Configuration → Point of Sale → [Existing POS] → Edit`

Or create a new configuration per Use Case 1, then add payment methods below.

#### Step 2 — Add Cash Payment Method

In **Payment Method** tab, add:

| Field | Value | Notes |
|-------|-------|-------|
| **Payment Method Name** | Cash | At-the-counter payment |
| **Payment Type** | Cash | Enables cash operations |
| **Journal** | Cash | From Accounting → Journals |
| **Is Cash Count** | Yes | Counts in cash box |
| **Receivable Account** | 110000 (Cash) | From journal |

#### Step 3 — Add Bank/Card Payment Method

In **Payment Method** tab, add another line:

| Field | Value | Notes |
|-------|-------|-------|
| **Payment Method Name** | Card | Debit / Credit card |
| **Payment Type** | Bank | Non-cash payment |
| **Journal** | Bank | Bank journal for card receipts |
| **Is Cash Count** | No | Not counted in cash box |
| **Receivable Account** | 110100 (Bank Receivable) | Per journal |
| **Split Transactions** | Yes | Useful for multi-customer batches |

> **System Trigger:** When `Split Transactions = Yes` on a payment method, each payment is posted to a separate receivable line per partner, enabling cleaner reconciliation for card transactions.

#### Step 4 — Add Pay Later / Credit Payment Method

In **Payment Method** tab, add a third line:

| Field | Value | Notes |
|-------|-------|-------|
| **Payment Method Name** | Pay Later | On-account payment |
| **Payment Type** | Pay Later | Triggers receivable accounting |
| **Is Cash Count** | No | Not a physical payment |
| **Receivable Account** | 121000 (Customer Receivables) | Partner-specific receivable |
| **Split Transactions** | Yes | Per-customer receivable tracking |

> **System Trigger:** When a `Pay Later` payment is used:
> - No `account.bank.statement.line` is created (no cash movement)
> - `account.move` receivable line is created per partner
> - Partner's account receivable is credited
> - Invoice reconciliation happens when the partner pays via Accounting

#### Step 5 — Configure Fiscal Positions (Tax Mapping)

Navigate to: `Accounting → Configuration → Fiscal Positions → Create`

| Field | Value |
|-------|-------|
| **Name** | POS Domestic |
| **Auto-detection** | Based on partner country / VAT |

Add a line:

| Field | Value |
|-------|-------|
| **Tax Source** | Tax X (standard) |
| **Tax Destination** | Tax Y (reduced) |

> **System Trigger:** In `_prepare_invoice_vals()`, the fiscal position's `_map_tax()` method is called for each order line. If a mapped tax cannot be found, the original tax is used. If no fiscal position is set on the POS, order-level `fiscal_position_id` is used.

#### Step 6 — Assign Fiscal Position to POS

Return to: `Point of Sale → Configuration → Point of Sale → [Your POS]`

In **Fiscal Position** field, select the fiscal position created above.

#### Step 7 — Set Pricelist for Multi-Currency (Optional)

If accepting foreign currency:

| Field | Value |
|-------|-------|
| **Pricelist** | EUR / USD Pricelist |
| **Foreign Currency** | EUR (if company in USD) |

> **System Trigger:** Session currency is set to `config_id.journal_id.currency_id`. Multi-currency conversion uses `session.currency_id.rate` at the time of order. The `invoice_currency_rate` is stored on the `account.move` for auditability.

**Expected Results Checklist:**
- [ ] Three payment methods visible in POS Payment Methods tab
- [ ] Fiscal position linked to POS
- [ ] Pricelist set correctly
- [ ] Cash method marked `Is Cash Count = Yes`
- [ ] Pay Later method has correct receivable account

---

## Use Case 3: Open, Operate, and Close Session with Reconciliation

### Scenario

A cashier opens a POS session in the morning, processes ~50 orders throughout the day (cash and card), performs a cash box open operation, and closes the session at the end of the day with full cash reconciliation.

### Steps

#### Step 1 — Open a New Session

Navigate to: `Point of Sale → Dashboard → [Your POS] → Open Session`

> **System Behavior:** `pos.session.create(vals)` is called:
> - Session record created with `state='opening_control'`
> - `action_pos_session_open()` called automatically
> - If cash control enabled, last session's `cash_register_balance_end_real` is loaded as `cash_register_balance_start`
> - Session sequence number assigned (e.g., `POS/001`)

#### Step 2 — Set Opening Cash Float (Cash Box Open)

On the POS interface, enter the **Opening Cash Amount** (e.g., 200.00 in the drawer).

> **System Behavior:** `pos.session.set_opening_control(cashbox_value, notes)`:
> - `_set_opening_control_data()` called
> - Difference calculated: `cashbox_value - cash_register_balance_start`
> - Mail message posted to session chatter
> - `cash_register_balance_start` updated to the entered value
> - Session `state` transitions to `opened`

#### Step 3 — Process Orders

As sales are made, use the POS interface to:

- Select products (order lines created on `pos.order`)
- Apply discounts or customer notes
- Select payment method (Cash / Card / Pay Later)
- Complete payment (order marked `state='paid'`)

> **System Behavior per order:**
> - `pos.order.create_from_ui()` → `pos.order.create(vals)` → `action_pos_order_paid()`
> - `pos.payment.create()` → one record per payment method used
> - Order `state` → `paid`
> - If `to_invoice=True` and invoice journal configured → `_generate_pos_order_invoice()` auto-runs

```
Order Flow:
Product selected → Order created (state='draft')
    └─► Payment registered → action_pos_order_paid()
          └─► state='paid', payment records created
                └─► (Optional) Invoice auto-generated
```

#### Step 4 — Handle Cash Box Operations During Session

If cash is added to or removed from the drawer mid-session:

Navigate to: `Point of Sale → Sessions → [Open Session] → Cash Box`

Click **Open Cash Box** and enter:

| Field | Value |
|-------|-------|
| **Operation** | Add / Remove |
| **Amount** | Amount added or removed |
| **Reason** | Note for audit trail |

> **System Behavior:** Creates a `pos.session.float_move` equivalent via `_post_cash_details_message()`. This is recorded as a note and adjusts the expected cash balance without creating formal accounting entries. Formal adjustments happen at session close.

#### Step 5 — Invoicing Orders During the Session

For any order, click the **Invoice** button.

> **System Behavior:** `action_pos_order_invoice()`:
> - Draft `account.move` (out_invoice) created via `_generate_pos_order_invoice()`
> - Fiscal position applied, taxes mapped
> - Invoice `state` → `posted`
> - Payments reconciled against invoice receivable

#### Step 6 — View Session Summary Mid-Session

Navigate to: `Point of Sale → Sessions → [Open Session]`

View the session kanban for:
- Total orders count
- Total paid amount
- Cash payments vs card payments breakdown
- Number of invoiced vs uninvoiced orders

> **System Trigger:** These are computed from `pos.order` and `pos.payment` records linked to the session. The session `move_id` is not yet created — it is only created at close.

#### Step 7 — Close the Session

Navigate to: `Point of Sale → Sessions → [Open Session] → Close`

> **System Behavior:** `action_pos_session_closing_control()`:
> - Draft orders checked → raises error if any remain
> - `state` → `closing_control`
> - If cash control → cash counting dialog appears
> - Cashier enters `cash_register_balance_end_real` (counted cash)
> - System computes difference vs expected balance
> - `action_pos_session_validate()` → `_validate_session()`:

```
Validate Session:
  ├─► _create_picking_at_end_of_session()  [if update_stock_at_closing]
  ├─► _create_account_move()
  │     └─► Sales credited (per product)
  │     └─► Taxes credited
  │     └─► Receivable debited (per payment method)
  ├─► _post_statement_difference()
  │     ├─► Difference < 0 → cash.statement.line + loss_account
  │     └─► Difference > 0 → cash.statement.line + profit_account
  ├─► move_id._post()  [account.move posted]
  ├─► pos.order (uninvoiced, paid) → state='done'
  ├─► _reconcile_account_move_lines()
  │     └─► Payment lines matched to receivable accounts
  └─► state → 'closed'
```

**Expected Results Checklist:**
- [ ] Session state = 'closed'
- [ ] `account.move` visible in session's Journal Entries tab
- [ ] Cash difference posted (if any) as statement line
- [ ] All paid orders now `state='done'`
- [ ] Invoiced orders have `account_move` linked
- [ ] Picking created if stock at closing enabled
- [ ] Cash journal balance matches physical cash

---

## Common Pitfalls

| # | Mistake | Symptom | How to Avoid |
|---|---------|---------|-------------|
| 1 | No payment method added | "No payment method available" on session open | Always add at least one payment method to POS |
| 2 | Wrong invoice journal selected | "No invoice journal configured" when clicking Invoice | Verify invoice journal in POS settings |
| 3 | Cash control without loss/profit accounts | "Define a Loss/Profit Account" on session close | Configure `loss_account_id` and `profit_account_id` on cash journal |
| 4 | Closing session with draft orders | "Cannot close POS while draft orders remain" | Cancel or complete all draft orders before closing |
| 5 | Unbalanced account move at close | Session close wizard shown with balancing option | Check all products have correct accounts set |
| 6 | Missing currency on journal | Multi-currency orders fail with conversion error | Ensure journal has `currency_id` set for non-base currencies |
| 7 | Pay Later without receivable account | Payment move fails | Ensure Pay Later payment method has `receivable_account_id` set |
| 8 | Wrong company on POS | POS not visible in dashboard | Verify `company_id` matches the logged-in user's company |
| 9 | No users in POS group | "Access Denied" for intended cashiers | Add users to Settings → Users → Access Rights → Point of Sale |
| 10 | Session stuck in 'opening_control' | Cannot process orders | Click Open Session again or use `set_opening_control()` from the UI |

---

## Configuration Deep Dive

### Related Configuration Paths

| Configuration | Menu Path | Controls |
|--------------|-----------|----------|
| POS Configuration | Point of Sale → Configuration → Point of Sale | Session behavior, workflow, payment methods |
| Payment Methods | Point of Sale → Configuration → Payment Methods | Payment type, journal, receivable account |
| Journals | Accounting → Configuration → Journals | Cash/bank journals, loss/profit accounts |
| Fiscal Positions | Accounting → Configuration → Fiscal Positions | Tax and account remapping |
| Products | Inventory → Products → Products | Pricing, taxes, route (make to order/stock) |
| Pricelists | Sales → Products → Pricelists | Currency and price computation |
| Users | Settings → Users → Users | POS group assignment |
| Cash Rounding | Accounting → Configuration → Cash Rounding | Penny difference rounding methods |
| Combo Products | Point of Sale → Products → Combos | Bundle pricing |
| Loyalty Programs | Sales → Loyalty | Points/rewards at POS |

### Advanced Options

| Option | Field Name | Default | Effect When Enabled |
|--------|-----------|---------|-------------------|
| **Cash Control** | `cash_control` | Off | Requires opening/closing cash counts; tracks cash difference |
| **Update Stock At Closing** | `update_stock_at_closing` | Closing | Delays stock moves until session close (avoids partial reservations) |
| **PoS Order Policy** | `order_policy` | Order | Controls when picking is created (at order vs at delivery) |
| **Auto-close Abandoned Sessions** | `_auto_close_abandoned_sessions()` | Off | Cron closes sessions inactive > X hours |
| **Split Transactions** | `split_transactions` | Off | Per-customer receivable lines for cleaner reconciliation |
| **Is Cash Count** | `is_cash_count` | No | Participates in cash box operations |
| **Fiscal Position** | `fiscal_position_id` | None | Tax remapping per order |
| **Cash Rounding** | `cash_rounding` | Off | Applies rounding method to totals |
| **Invoice Journal** | `invoice_journal_id` | None | Journal used when generating invoices |
| **Allowed Users** | `user_ids` | All POS users | Restricts POS access to specific users |
| **Order Edit Tracking** | `order_edit_tracking` | Off | Logs edited orders in session chatter |
| **Receipt Printer** | `printer_ids` | None | IoT Box integration for kitchen/receipt printers |
| **Proxy Endpoint** | `proxy_ip` | None | IoT Box connection for hardware |

---

## Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| "No payment method available" when opening | Payment methods not added to POS config | Add at least one payment method in POS → Configuration → Payment Methods |
| Invoice button not visible | `invoice_journal_id` not set on POS | Configure invoice journal in POS settings |
| Cash difference error on close | Cash journal missing loss/profit accounts | Go to Accounting → Journals → Cash → set Loss/Profit Account |
| Session not appearing in dashboard | Wrong company selected | Switch to correct company in top-right dropdown |
| Cannot process card payments | Payment method type = 'cash' instead of 'bank' | Edit payment method, set Type to Bank |
| Pay Later payment fails | No receivable account on payment method | Set `receivable_account_id` on Pay Later payment method |
| Draft orders cannot be closed | Draft orders still exist | Cancel or delete draft orders before closing |
| Products not showing in POS | Product not in POS category or pricelist inactive | Assign to POS category or check pricelist validity |
| Session balance mismatch | Cash counted incorrectly or payments missed | Review statement lines; check for voided orders |
| Multi-currency orders fail | Journal has no currency set | Set `currency_id` on the payment journal |
| POS loading slowly | Large product catalog | Use POS categories to filter products; load in batches |

---

## Related Documentation

| Type | Link | Description |
|------|------|-------------|
| Technical Flow | [Flows/POS/pos-session-flow](Flows/POS/pos-session-flow.md) | Full session lifecycle — for developers |
| Technical Flow | [Flows/POS/pos-order-to-invoice-flow](Flows/POS/pos-order-to-invoice-flow.md) | Order-to-invoice method chain |
| Module Reference | [Modules/pos](Modules/pos.md) | Complete POS model, field, and method reference |
| Module Reference | [Modules/Account](Modules/account.md) | account.move, journal configuration |
| Module Reference | [Modules/res.partner](Modules/res.partner.md) | Partner model for customer management |
| Patterns | [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) | State machine design for sessions |
| Security | [Patterns/Security Patterns](Patterns/Security Patterns.md) | ACL for POS users and cashiers |
| Accounting Guide | [Business/Account/chart-of-accounts-guide](Business/Account/chart-of-accounts-guide.md) | Journal and account setup |
| Snippets | [Snippets/Model Snippets](Snippets/Model Snippets.md) | Code templates for POS customization |
