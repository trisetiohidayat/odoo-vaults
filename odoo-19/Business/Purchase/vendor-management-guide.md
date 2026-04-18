---
type: guide
title: "Purchase Workflow Guide"
module: purchase
audience: business-consultant, purchase-manager
level: 2
prerequisites:
  - vendors_created
  - products_with_seller_prices
  - warehouse_configured
  - picking_types_setup
estimated_time: "~15 minutes"
related_flows:
  - "[Flows/Purchase/purchase-order-creation-flow](Flows/Purchase/purchase-order-creation-flow.md)"
  - "[Flows/Purchase/purchase-order-receipt-flow](Flows/Purchase/purchase-order-receipt-flow.md)"
  - "[Flows/Purchase/purchase-to-bill-flow](Flows/Purchase/purchase-to-bill-flow.md)"
source_module: purchase
created: 2026-04-06
version: "1.0"
---

# Purchase Workflow Guide

> **Quick Summary:** End-to-end purchase process from creating vendors and RFQ to receiving goods and processing vendor bills.

**Actor:** Purchase Manager / Purchase User
**Module:** Purchase
**Difficulty:** ⭐⭐ Medium

---

## Prerequisites Checklist

- [ ] **Vendors created** — Purchase → Configuration → Vendors (res.partner with supplier checkbox)
- [ ] **Products with seller prices** — Product → Seller tab → Add vendor and price
- [ ] **Warehouse configured** — Inventory → Configuration → Warehouses
- [ ] **Purchase product categories** — Product → Categories

---

## Quick Access

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/Purchase/purchase-order-creation-flow](Flows/Purchase/purchase-order-creation-flow.md) | RFQ → PO confirmation |
| 🔀 Technical Flow | [Flows/Purchase/purchase-order-receipt-flow](Flows/Purchase/purchase-order-receipt-flow.md) | PO → receipt |
| 🔀 Technical Flow | [Flows/Purchase/purchase-to-bill-flow](Flows/Purchase/purchase-to-bill-flow.md) | Receipt → vendor bill |
| 📖 Module Reference | [Modules/Purchase](Modules/Purchase.md) | Complete model reference |

---

## Use Cases Covered

| # | Use Case | Difficulty |
|---|----------|-----------|
| 1 | Create PO from RFQ and confirm | ⭐ |
| 2 | Partial receipt and handling | ⭐⭐ |
| 3 | Process vendor bill and payment | ⭐⭐ |

---

## Use Case 1: Create PO and Confirm

### Scenario
Purchase manager creates a Purchase Order from Request for Quotation (RFQ) and confirms it.

### Steps

#### Step 1 — Create RFQ

Go to: **Purchase → Orders → Create**

| Field | Value | Required |
|-------|-------|----------|
| **Vendor** | Select vendor | ✅ Yes |
| **Order Date** | Today | ✅ Yes |
| **Warehouse** | Select warehouse | ✅ Yes |

> **⚡ System Trigger:** When vendor is selected, Odoo auto-fills payment terms from vendor's configuration.

#### Step 2 — Add Products

Click **Add a product** and fill:

| Field | Value | Notes |
|-------|-------|-------|
| **Product** | Select product | |
| **Quantity** | Order qty | |
| **Scheduled Date** | Expected delivery | |

> **⚡ System Trigger:** When product is added, Odoo auto-fills:
> - **Price** from vendor's seller price (product.supplierinfo)
> - **Taxes** from vendor's fiscal position
> - **UoM** from product's purchase unit of measure
> - **Delivery Lead Time** from seller info

#### Step 3 — Confirm Order

Click **Confirm Order** (or **Send to Vendor** first for RFQ stage).

> **⚡ System Trigger:** When confirmed:
> - State changes: RFQ → Purchase Order
> - Picking (receipt) created for each storable product
> - Vendor added to product's supplier info automatically
> - Activity scheduled for receipt follow-up
> - Email sent to vendor (if configured)

> **⚡ Side Effects:**
> - `stock.picking` created with type = 'incoming'
> - Vendor receives email with PO
> - PO locked (no edits to lines after confirmation — must cancel first)

#### Step 4 — Verify Receipt Created

Go to: **Inventory → Operations → Receipts**

Confirm receipt order is visible.

---

## Use Case 2: Partial Receipt

### Scenario
Vendor delivers only partial quantity. Remaining quantity to be received later.

### Steps

#### Step 1 — Open Receipt

Go to: **Inventory → Operations → Receipts** → Open receipt for PO.

#### Step 2 — Receive Partial Quantity

For each product line:
- Adjust **Done** quantity (less than **Demand**)
- Specify **Lot/Serial** if product is tracked

> **⚡ System Trigger:** When you set Done < Demand, Odoo prompts: "Create Backorder?" or "No Backorder".

#### Step 3 — Choose Backorder Option

| Option | Result |
|--------|--------|
| **Create Backorder** | Original receipt done, new receipt created for remaining qty |
| **No Backorder** | Only received qty processed, remaining cancelled |

#### Step 4 — Receive Remaining Later

Go to: **Purchase → Orders → Receipts**

New receipt visible for remaining quantity. Repeat when goods arrive.

---

## Use Case 3: Process Vendor Bill

### Scenario
Process vendor bill for received goods.

### Steps

#### Step 1 — Create Bill from PO

Go to: **Purchase → Orders → Purchase Orders** → Open PO

Click **Create Bill**.

> **⚡ System Trigger:** Bill creation wizard opens with options:
> - **Bill at order** — Bill based on PO quantity (ordered qty)
> - **Bill based on received** — Bill based on received quantity (most accurate)

#### Step 2 — Confirm Bill

Click **Create Bill** → Bill created as draft.

Go to: **Accounting → Vendors → Bills**

Open the draft bill. Verify:
- Vendor name
- Invoice lines (product, qty, price)
- Taxes

Click **Confirm**.

> **⚡ System Trigger:** When confirmed:
> - Journal entries created (debit expense/inventory, credit vendor)
> - State: Draft → Posted
> - Payment due date tracked

#### Step 3 — Register Payment

On posted bill, click **Register Payment**.

> **⚡ System Trigger:** Payment registered:
> - Bank/cash journal selected
> - Journal entry created
> - Bill state: Posted → In Payment → Paid
> - Vendor account credited

---

## Common Pitfalls

| # | Mistake | Symptom | How to Avoid |
|---|---------|---------|-------------|
| 1 | Bill for unreceived goods | Vendor paid for undelivered goods | Always use "Bill based on received" |
| 2 | Confirm PO without vendor seller price | Price = 0 or wrong price | Add seller info first |
| 3 | Edit confirmed PO | Changes not reflected in receipt | Cancel PO first, create new |
| 4 | Forget to set warehouse | Receipt created in wrong WH | Check warehouse on PO |
| 5 | Bill without fiscal position | Wrong taxes applied | Set vendor's fiscal position |

---

## Related Documentation

| Type | Link | Description |
|------|------|-------------|
| 🔀 PO Creation Flow | [Flows/Purchase/purchase-order-creation-flow](Flows/Purchase/purchase-order-creation-flow.md) | RFQ → PO confirmation |
| 🔀 Receipt Flow | [Flows/Purchase/purchase-order-receipt-flow](Flows/Purchase/purchase-order-receipt-flow.md) | PO → goods received |
| 🔀 Purchase-to-Bill | [Flows/Purchase/purchase-to-bill-flow](Flows/Purchase/purchase-to-bill-flow.md) | Receipt → vendor bill |
| 📖 Module Reference | [Modules/Purchase](Modules/Purchase.md) | Complete model reference |
