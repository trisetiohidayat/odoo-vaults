---
type: flow
title: "Purchase to Bill Flow"
primary_model: purchase.order
trigger: "User action — PO → Create Bill"
cross_module: true
models_touched:
  - purchase.order
  - purchase.order.line
  - stock.picking
  - stock.move
  - stock.quant
  - account.move
  - account.move.line
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Purchase/purchase-order-creation-flow](odoo-19/Flows/Purchase/purchase-order-creation-flow.md)"
  - "[Flows/Purchase/purchase-order-receipt-flow](odoo-19/Flows/Purchase/purchase-order-receipt-flow.md)"
  - "[Flows/Cross-Module/purchase-stock-account-flow](odoo-19/Flows/Cross-Module/purchase-stock-account-flow.md)"
source_module: purchase
source_path: ~/odoo/odoo19/odoo/addons/purchase/
created: 2026-04-06
version: "1.0"
---

# Purchase to Bill Flow

## Overview

From confirmed Purchase Order through goods receipt to vendor bill creation and posting. Links PO confirmation → stock receipt → vendor bill (account payable).

## Trigger Point

**User:** Opens **Purchase → Orders → Purchase Orders → [PO] → Create Bill**
**Method:** `purchase.order.action_create_invoice()`

---

## Complete Method Chain

```
1. purchase.order.action_create_invoice()
   │
   ├─► 2. _create_invoice(vendor_id, partner_id)
   │      ├─► 3. account.move.create({'move_type': 'in_invoice', ...})
   │      │      └─► 4. _onchange_partner_id()
   │      │             ├─► 5. fiscal_position set from vendor
   │      │             ├─► 6. payment_terms from vendor
   │      │             └─► 7. invoice_date_due computed
   │      │
   │      ├─► 8. for each po_line:
   │      │      ├─► 9. account.move.line.create() — product line
   │      │      │      ├─► 10. price_unit = po_line.price_unit
   │      │      │      ├─► 11. quantity = bill_qty (ordered or received)
   │      │      │      ├─► 12. taxes from product + vendor fiscal position
   │      │      │      └─► 13. _onchange_price_subtotal()
   │      │      │
   │      │      ├─► 14. taxes computed: tax._compute_tax()
   │      │      ├─► 15. account.move.line.create() — tax line
   │      │      └─► 16. amount_total recomputed
   │      │
   │      └─► 17. invoice_ids = [(4, invoice.id)]
   │
   ├─► 18. account.move._compute_payments_widget()
   │      └─► 19. payment_widget shows due amount
   │
   ├─► 20. PO state: purchase → 'to approve' (if approval needed)
   └─► 21. invoice_count incremented
```

---

## Decision Tree

```
Create Bill action
│
├─► Bill based on:
│  ├─► 'order' → bill_qty = product_qty (ordered)
│  ├─► 'received' → bill_qty = qty_received (received)
│  └─► 'manual' → user enters qty manually
│
├─► Vendor type:
│  ├─► Supplier (in_invoice) → vendor bill
│  └─► Customer (out_refund) → vendor credit note
│
└─► Fiscal position?
   ├─► Domestic → standard taxes
   └─► Foreign vendor → withholding tax applied
```

---

## Database State

| Table | Created/Updated | Fields |
|-------|----------------|--------|
| `account_move` | Created | move_type='in_invoice', state='draft' |
| `account_move_line` | Created | debit=amount, account=expense/inventory |
| `purchase_order_line` | Updated | qty_invoiced |
| `purchase_order` | Updated | invoice_count++ |

---

## Error Scenarios

| Scenario | Error | Prevention |
|----------|-------|------------|
| Bill > received qty | Warning shown | Use "received" billing policy |
| Vendor not set as supplier | Error | Set vendor in Contacts |
| Wrong fiscal position | Wrong taxes | Check vendor's fiscal position |
| PO locked (cancelled) | Cannot create bill | Only from active PO |

---

## Extension Points

| Hook | Purpose | Override |
|------|---------|---------|
| `_prepare_invoice()` | Custom invoice vals | Extend |
| `_create_invoice_line()` | Custom line vals | Extend |

---

## Related

- [Flows/Purchase/purchase-order-creation-flow](odoo-19/Flows/Purchase/purchase-order-creation-flow.md) — PO creation
- [Flows/Purchase/purchase-order-receipt-flow](odoo-19/Flows/Purchase/purchase-order-receipt-flow.md) — Receipt
- [Flows/Cross-Module/purchase-stock-account-flow](odoo-19/Flows/Cross-Module/purchase-stock-account-flow.md) — Full cross-module
