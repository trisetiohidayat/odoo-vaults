---
type: guide
title: "Sales Process Guide"
module: sale
audience: business-consultant
level: 2
prerequisites:
  - products_activated
  - sale_team_configured
  - payment_terms_set
  - pricelist_configured
  - chart_of_accounts_configured
  - warehouse_configured
estimated_time: "~30 minutes"
related_flows:
  - "[Flows/Sale/quotation-to-sale-order-flow](Flows/Sale/quotation-to-sale-order-flow.md)"
related_guides:
  - "[Business/Stock/warehouse-setup-guide](Business/Stock/warehouse-setup-guide.md)"
  - "[Business/Account/chart-of-accounts-guide](Business/Account/chart-of-accounts-guide.md)"
source_module: sale
created: 2026-04-06
updated: 2026-04-06
version: "1.0"
---

# Sales Process Guide

> **Quick Summary:** End-to-end sales process from initial quotation through confirmed order, delivery, invoicing, and payment collection — covering all three standard sales patterns (prepaid, invoiced at delivery, and invoiced after delivery).

**Actor:** Salesperson / Sales Manager
**Module:** Sale
**Use Case:** Creating and managing customer sales orders from quote to cash collection
**Difficulty:** ⭐⭐ Medium

---

## Prerequisites Checklist

Before starting, ensure the following are configured. Skipping these will cause errors or missing features.

- [ ] **[Products Activated]** — All saleable products created with `sale_ok = True`, pricing set in pricelist, and income accounts assigned
- [ ] **[Sale Team Configured]** — Sales team (quotation tolerances, assigned salespeople, pipeline stages) set up in `Sale → Configuration → Sales Teams`
- [ ] **[Payment Terms Set]** — Payment term templates configured in `Accounting → Configuration → Payment Terms` (e.g., "30 Days", "Immediate", "50% Advance")
- [ ] **[Pricelist Configured]** — Pricelists created in `Sale → Configuration → Pricelists` and assigned to partners or set as default
- [ ] **[Chart of Accounts Configured]** — Revenue/income accounts set on product categories in `Accounting → Configuration → Accounting → Product Categories`
- [ ] **[Warehouse Configured]** — Warehouse set up in `Inventory → Configuration → Warehouses` with at least one location and routes defined

> **⚠️ Critical:** If **Products** are not marked `sale_ok = True`, they will not appear in the sales order product picker and you will get a "Product not found" error when quoting.

---

## Quick Access

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/Sale/quotation-to-sale-order-flow](Flows/Sale/quotation-to-sale-order-flow.md) | Full method chain and branching logic for order creation |
| 📖 Module Reference | [Modules/Sale](Modules/sale.md) | Complete field and method reference for sale.order |
| 📋 Related Guide | [Business/Account/chart-of-accounts-guide](Business/Account/chart-of-accounts-guide.md) | Invoice and payment management |
| 📋 Related Guide | [Business/Stock/warehouse-setup-guide](Business/Stock/warehouse-setup-guide.md) | Delivery and warehouse operations |
| 🔧 Configuration | [Modules/Sale](Modules/sale.md) → Configuration section | Advanced sales team and workflow settings |

---

## Use Cases Covered

This guide covers the following use cases. Jump to the relevant section:

| # | Use Case | Page | Difficulty |
|---|----------|------|-----------|
| 1 | Basic Quote-to-Cash — quotation confirmed, delivered, invoiced, paid | [#use-case-a-basic-quote-to-cash](#use-case-a-basic-quote-to-cash.md) | ⭐ |
| 2 | Prepaid Order — advance payment required before delivery | [#use-case-b-prepaid-order-with-immediate-invoice](#use-case-b-prepaid-order-with-immediate-invoice.md) | ⭐⭐ |
| 3 | Postpaid Order — invoice after delivery confirmation | [#use-case-c-postpaid-order-with-invoice-after-delivery](#use-case-c-postpaid-order-with-invoice-after-delivery.md) | ⭐⭐ |

---

## Use Case A: Basic Quote-to-Cash

*[The standard flow: quotation → confirmed order → delivery → invoice → payment]*

### Scenario

A customer requests a quote for 3 products. The salesperson creates a quotation, the customer accepts it, and the order is fulfilled: products are delivered from stock, an invoice is sent, and payment is collected.

### Steps

#### Step 1 — Create a Quotation

Navigate to: `Sale → Orders → Quotations → Create`

Click **Create**.

> **⚡ System Behavior:** When you navigate here, Odoo loads the quotation form with the default warehouse, company, and team pre-filled from your user preferences. The SO number is auto-generated as a draft.

#### Step 2 — Enter Customer and Product Lines

| Field | Value | Required | Auto-filled |
|-------|-------|----------|-------------|
| **Customer** | Select partner | ✅ Yes | — |
| **Order Date** | Today's date | ✅ Yes | Default today |
| **Warehouse** | e.g., "Main Warehouse" | ✅ Yes | From user settings |
| **Pricelist** | Customer's pricelist | No | Auto-filled from partner |
| **Payment Terms** | e.g., "30 Net" | No | Auto-filled from partner |

Click the **Add a line** button and fill:

| Field | Value | Notes |
|-------|-------|-------|
| **Product** | Select product | Must have `sale_ok = True` |
| **Description** | Auto-filled from product | Override if needed |
| **Quantity** | e.g., 5 | Required |
| **Unit Price** | Auto-filled from pricelist | Editable |
| **Tax** | Auto-selected from product | Editable |

> **⚡ System Trigger:** When you select a **Customer**, Odoo triggers `_onchange_partner_id()` which auto-fills the Pricelist, Payment Terms, and Delivery Address from the partner record. If the partner has a different currency, the `currency_id` changes accordingly.

> **⚡ System Trigger:** When you select a **Product**, Odoo triggers `_onchange_product_id()` which auto-fills the Description, Unit Price (from pricelist), and Tax from the product's `taxes_id` field.

> **⚡ System Side Effect:** Adding a line triggers `_compute_amount()` — the subtotal, tax amount, and total are computed immediately in the form footer.

#### Step 3 — Confirm the Quotation (Convert to Sale Order)

Click **Confirm**.

> **⚡ System Behavior:** Confirmation is only available when at least one line is present and the customer is set. If any required field is missing, the button is disabled.

> **⚡ System Trigger:** When **Confirm** is clicked, Odoo calls `action_confirm()` which:
> - Validates the order has at least one line
> - Changes state from `draft` to `sale_order` (confirmed)
> - Creates `sale_order_line` records linked to `account.move` (not yet created)
> - Reserves quantities in `stock.quant` (if `type` = 'make_to_stock')
> - Sends confirmation email to customer (if mail template configured)
> - Creates follower entries for sales team members

**Expected Results Checklist:**
- [ ] Order status changes from "Quotation" to "Sales Order"
- [ ] Order appears in `Sale → Orders → Sales Orders`
- [ ] Inventory reservation created (check `Inventory → Reporting → Stock`)
- [ ] Customer notified by email (if email configured)
- [ ] Order is now locked from accidental deletion (only cancellation available)

---

## Use Case B: Prepaid Order with Immediate Invoice

*[Quotation confirmed with advance payment — order invoiced before delivery]*

### Scenario

A customer places an order for a high-value custom product that requires prepayment. The salesperson creates the order, issues an invoice immediately upon confirmation, and only releases the product after payment is received.

### Steps

#### Step 1 — Create Order with Prepaid Payment Terms

Navigate to: `Sale → Orders → Quotations → Create`

Fill in the order as in Use Case A, but change the **Payment Terms** to a prepaid option (e.g., "100% Advance", "50% Advance, 50% on Delivery").

> **⚡ System Trigger:** Setting a prepaid payment term triggers `_onchange_payment_term()` — the invoice due date is set to the order date (immediate) or computed based on the advance percentage installment schedule.

> **⚡ Conditional Step:**
> - IF `payment_terms = "100% Advance"`: Invoice will be due immediately upon posting
> - IF `payment_terms = "50% Advance"`: Two invoices will be generated — one for 50% now, one for 50% on delivery

#### Step 2 — Confirm and Trigger Immediate Invoice

Click **Confirm**, then click **Create Invoice**.

> **⚡ System Behavior:** The "Create Invoice" button appears on the confirmed sale order form. It will open a wizard:

| Wizard Field | Value | Notes |
|-------------|-------|-------|
| **Invoice Type** | "Regular invoice" | For partial advance: select "Percentage" and enter 50 |
| **Operation** | "Normal" | Use for standard invoicing |
| **Date** | Invoice date | Defaults to today |

Click **Create and View Invoice**.

> **⚡ System Trigger:** `sale.order._create_invoices()` is called — this creates an `account.move` in draft state with:
> - `move_type = 'out_invoice'`
> - Lines from each `sale.order.line` with income account and tax
> - Invoice date = today's date (or computed from payment terms)

> **⚡ System Side Effect:** The sale order's `invoice_count` increments. The SO remains "in progress" until all invoices are paid and the picking is done.

#### Step 3 — Post the Invoice

Open the invoice from the SO's "Invoices" smart button → Click **Post**.

> **⚡ System Trigger:** `account.move.action_post()` — see [Flows/Account/invoice-post-flow](Flows/Account/invoice-post-flow.md) for full chain.
> - Invoice number (move_name) is generated from the sequence
> - Journal entries are locked
> - PDF report is auto-generated and attached
> - Customer receives invoice notification

#### Step 4 — Register Payment

Click **Register Payment** on the posted invoice → fill amount, journal, date → Click **Post Payment**.

> **⚡ System Trigger:** `account.payment.action_post()` — see [Flows/Account/payment-flow](Flows/Account/payment-flow.md) for full chain.
> - Payment move created: Dr. Bank / Cr. Customer AR
> - Invoice reconciled: state → 'paid' (or 'in_payment' for partial)
> - SO's `invoice_status` field updated to 'invoiced'

**Expected Results Checklist:**
- [ ] Invoice posted and numbered
- [ ] Payment registered and reconciled
- [ ] SO state: "Sales Order" (confirmed), invoice_status: "Invoiced"
- [ ] Delivery can now be released (pick, pack, ship)

---

## Use Case C: Postpaid Order with Invoice After Delivery

*[Order confirmed, product delivered, then invoice issued — the most common B2B pattern]*

### Scenario

A customer orders products from stock. The order is confirmed, products are shipped from the warehouse, and the invoice is sent after delivery confirmation — typical for B2B net-30 terms.

### Steps

#### Step 1 — Create and Confirm Order

Navigate to: `Sale → Orders → Quotations → Create`

Fill in the order with payment terms set to `"30 Net"` (or similar post-delivery terms). Confirm the order.

> **⚡ System Behavior:** On confirmation, Odoo creates a `stock.picking` (Delivery Order) in draft state, linked to the SO via `stock.picking.move_ids_without_package`.

#### Step 2 — Validate the Picking (Ship the Products)

Navigate to: `Sale → Orders → Sales Orders → [Your Order] → Delivery tab`

Click on the delivery order → Click **Validate**.

> **⚡ System Trigger:** `stock.picking.button_validate()` → `_action_done()`:
> - Quantities verified against reserved stock
> - `stock.quant` records updated: reserved quantity moved to done
> - `stock.move` records set to `state = 'done'`
> - `sale.order.line` quantities delivered updated
> - SO `delivery_status` updated to 'delivered' when all lines complete

> **⚡ System Side Effect:** If `stock_account` module is installed, accounting entries are generated:
> - Dr. Cost of Goods Sold
> - Cr. Inventory (stock valuation account)
> These entries record the cost impact of the delivery.

#### Step 3 — Create Invoice After Delivery

Navigate back to the SO → Click **Create Invoice**.

> **⚡ System Behavior:** When you click Create Invoice, Odoo opens a wizard with three options:

| Option | Behavior |
|--------|---------|
| **Invoice based on delivered quantities** | Default — invoices only what has been delivered |
| **Invoice based on order quantities** | Invoices full order qty regardless of delivery (even if partially delivered) |
| **No autoreload on product invoices** | Prevents automatic invoice creation |

Select **"Invoice based on delivered quantities"** → Click **Create and View Invoice**.

> **⚡ System Trigger:** `sale.order._create_invoices(final=False)` — only lines with `qty_delivered > 0` are included in the invoice draft.

> **⚡ System Side Effect:** Each line on the invoice pulls `qty_delivered` as the quantity, and `price_unit` from the original SO line.

#### Step 4 — Post and Send Invoice

Open the invoice → Click **Post** → Click **Send** to email to the customer.

> **⚡ System Behavior:** The invoice due date (`invoice_date_due`) is computed from the payment terms ("30 Net" = 30 days from invoice date). The customer is expected to pay by that date.

**Expected Results Checklist:**
- [ ] SO delivery_status = 'delivered'
- [ ] Invoice created with delivered quantities
- [ ] Invoice posted — move_name assigned, entries locked
- [ ] Invoice due date set to +30 days from today
- [ ] Customer receives invoice by email

#### Step 5 — Wait for Payment (Follow-up)

> **⚡ System Trigger:** Odoo tracks the invoice due date and flags overdue invoices. You can check the dashboard at `Accounting → Dashboard` to see outstanding receivables and overdue items.

When payment is received:
- Navigate to the invoice → Click **Register Payment**
- Fill in amount (full or partial), journal, date → Confirm

> **⚡ System Behavior:** Payment is reconciled against the invoice → invoice state → 'paid' → SO `invoice_status` → 'done' (fully processed).

---

## Common Pitfalls

| # | Mistake | Symptom | How to Avoid |
|---|---------|---------|-------------|
| 1 | Not setting `sale_ok = True` on products | Products don't appear in SO line picker | Always mark saleable products as sale_ok |
| 2 | Forgetting to set income account on product category | "No income account found" error on invoice post | Configure `property_account_income_categ_id` on the product category |
| 3 | Confirming order before finalizing pricing | Customer sees wrong price on confirmation email | Always review line prices before confirming |
| 4 | Creating invoice before picking is validated | Invoice shows 0 qty (no delivery lines) | Always validate picking before creating invoice if using "delivered qty" mode |
| 5 | Wrong warehouse selected on SO | Products shipped from wrong location or stock mismatch | Always confirm warehouse on the order header before confirming |

---

## Configuration Deep Dive

*[Optional section — for advanced configuration]*

### Related Configuration Paths

| Configuration | Menu Path | Controls |
|--------------|-----------|----------|
| Sale Team | Sale → Configuration → Sales Teams | Assigned salespeople, quotation validity days, warehouse |
| Pricelist | Sale → Configuration → Pricelists | Product pricing rules, discounts, currency |
| Payment Terms | Accounting → Configuration → Payment Terms | Invoice due date calculation, installment schedules |
| Product Categories | Accounting → Configuration → Accounting → Product Categories | Income/expense accounts for products |
| Warehouse | Inventory → Configuration → Warehouses | Delivery routes, default vals, replenishment |
| Workflow | Sale → Configuration → Settings | Auto-lock, automatic invoice creation, dropshipping |

### Advanced Options

| Option | Field Name | Default | Effect When Enabled |
|--------|-----------|---------|-------------------|
| Automatic invoice | `auto_done_setting` | Off | Automatically invoices orders on confirmation |
| Delivery slips | `delivery_tmpl_id` | Default template | Controls the delivery report PDF format |
| Confirm locks | `lock_confirmed_order` | Off | Prevents editing of confirmed orders |
| Partial delivery invoicing | `invoice_policy` on product | 'ordered' | Switch to 'delivered' to invoice only shipped qty |

---

## Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|---------|
| Products not appearing in the product picker | Product has `sale_ok = False` or is archived | Edit product → enable "Can be sold" and ensure Active = True |
| Invoice post fails with "No income account" | Product category has no `property_account_income_categ_id` | Set income account in Accounting → Product Categories |
| Wrong price on order line | Wrong or missing pricelist on customer | Assign correct pricelist in partner form under "Sales & Purchases" tab |
| SO shows "Reserved" but stock is available | Warehouse has insufficient stock or `available` qty < ordered | Check Inventory → Reporting → Availability by product |
| Cannot validate delivery — "Not enough stock" | Insufficient `available` quantity at warehouse | Either increase stock (MTO route) or split delivery into available qty only |
| Invoice amount does not match SO total | Tax not included or extra tax applied | Verify tax configuration on product and fiscal position on partner |
| Customer does not receive confirmation email | Email not configured or partner has no email | Check partner's email field; verify Outgoing Mail Server in Settings |

---

## Related Documentation

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/Sale/quotation-to-sale-order-flow](Flows/Sale/quotation-to-sale-order-flow.md) | Full method chain — for developers |
| 📖 Module Reference | [Modules/Sale](Modules/sale.md) | Complete field and method list |
| 🔀 Technical Flow | [Flows/Account/invoice-creation-flow](Flows/Account/invoice-creation-flow.md) | Invoice creation from SO |
| 🔀 Technical Flow | [Flows/Account/invoice-post-flow](Flows/Account/invoice-post-flow.md) | Invoice posting |
| 🔀 Technical Flow | [Flows/Account/payment-flow](Flows/Account/payment-flow.md) | Payment registration |
| 📋 Related Guide | [Business/Stock/warehouse-setup-guide](Business/Stock/warehouse-setup-guide.md) | Delivery and warehouse operations |
| 📋 Related Guide | [Business/Account/chart-of-accounts-guide](Business/Account/chart-of-accounts-guide.md) | Accounting and invoicing |
| 🛠️ Patterns | [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) | Workflow design patterns |
| 🔧 Snippets | [Snippets/Model Snippets](odoo-18/Snippets/Model Snippets.md) | Code snippets for customization |