---
tags: [odoo, odoo17, module, purchase_requisition]
---

# Purchase Requisition Module

**Source:** `addons/purchase_requisition/models/`

## Key Models

| Model | File | Description |
|-------|------|-------------|
| `` `purchase.requisition` `` | `purchase_requisition.py` | Purchase tender / call for bids |
| `` `purchase.requisition.line` `` | `purchase_requisition.py` | Lines within a requisition |
| `` `purchase.requisition.type` `` | `purchase_requisition.py` | Agreement type configuration |

## purchase.requisition.type

Defines the behaviour of a purchase agreement. Key fields:

- `` `exclusive` `` — `` `exclusive` `` (cancel others on first PO confirm) or `` `multiple` `` (allow multiple POs)
- `` `quantity_copy` `` — `` `copy` `` (use requisition quantities) or `` `none` `` (manual)
- `` `line_copy` `` — `` `copy` `` (auto-create PO lines) or `` `none`` `` (manual line creation)

## purchase.requisition

A purchase tender (also called a "Call for Bids" or "Blanket Order"). Used to request quotations from multiple vendors and compare bids before issuing a Purchase Order.

### State Machine

`` `purchase.requisition`` `` uses an explicit `` `state`` `` field:

| State | Label | Description |
|-------|-------|-------------|
| `` `draft` `` | Draft | Initial state |
| `` `ongoing` `` | Ongoing | Long-term blanket agreement |
| `` `in_progress` `` | Confirmed | Vendor selection in progress |
| `` `open` `` | Bid Selection | Receiving and comparing vendor bids |
| `` `done` `` | Closed | Agreement concluded |
| `` `cancel` `` | Cancelled | Requisition cancelled |

### Key Fields

- `` `vendor_id` `` — Vendor (used for blanket orders vs. tenders)
- `` `type_id` `` — `` `purchase.requisition.type` `` controlling exclusive/quantity-copy behaviour
- `` `ordering_date` `` — When the purchase should be placed
- `` `date_end` `` — Deadline for receiving vendor bids
- `` `schedule_date` `` — Expected delivery date across all products
- `` `line_ids` `` — `` `purchase.requisition.line`` `` records (product + qty)
- `` `purchase_ids` `` — Generated `` `purchase.order`` `` records linked to this requisition
- `` `origin` `` — Source document reference

### Workflow

1. Create a requisition with line items (products + quantities)
2. Set `` `vendor_id` `` for a single-vendor blanket order, or leave blank for a multi-vendor tender
3. On `` `in_progress`` `` / `` `open`` ``, generate RFQs (Request for Quotation) against one or more vendors
4. Vendors submit bids; quantities and prices are tracked on `` `purchase.order.line` ``
5. Select winning vendor(s) and confirm the purchase order
6. When `` `type_id.exclusive = 'exclusive'` ``, confirming one PO cancels remaining POs for that requisition

## See Also

- [Modules/Purchase](odoo-18/Modules/purchase.md) — base `` `purchase.order` `` and `` `purchase.order.line` ``
