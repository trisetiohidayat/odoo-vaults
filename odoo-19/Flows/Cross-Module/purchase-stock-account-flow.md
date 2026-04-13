---
type: flow
title: "Purchase → Stock → Account Cross-Module Flow"
primary_model: purchase.order
trigger: "User action — PO → Confirm"
cross_module: true
models_touched:
  - purchase.order
  - purchase.order.line
  - stock.picking
  - stock.move
  - stock.quant
  - account.move
  - account.move.line
  - account.payment
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Purchase/purchase-order-creation-flow](flows/purchase/purchase-order-creation-flow.md)"
  - "[Flows/Purchase/purchase-order-receipt-flow](flows/purchase/purchase-order-receipt-flow.md)"
  - "[Flows/Purchase/purchase-to-bill-flow](flows/purchase/purchase-to-bill-flow.md)"
source_module: purchase
source_path: ~/odoo/odoo19/odoo/addons/purchase_stock/
created: 2026-04-06
version: "1.0"
---

# Purchase → Stock → Account Cross-Module Flow

## Overview

Complete end-to-end flow from Purchase Order through warehouse receipt to vendor bill posting and payment. Spans three modules: Purchase (RFQ → PO), Stock (receipt → storage), Account (bill → payment).

## Trigger Point

**User:** Opens **Purchase → Orders → [PO] → Confirm Order**

---

## Complete Method Chain

```
PHASE 1: PO CONFIRMATION
1. purchase.order.button_confirm()
   ├─► 2. _button_confirm()
   │      ├─► 3. _check_order()
   │      ├─► 4. state = 'purchase'
   │      ├─► 5. for each po_line: _add_supplier_to_product()
   │      │      └─► 6. product.supplierinfo updated with vendor
   │      │
   │      ├─► 7. _create_picking()
   │      │      ├─► 8. stock.picking.create() for incoming receipt
   │      │      └─► 9. for each po_line: stock.move.create()
   │      │             ├─► 10. product_id = pol.product_id
   │      │             ├─► 11. product_uom_qty = pol.product_qty
   │      │             └─► 12. location_id = vendor, dest = WH/stock
   │      │
   │      └─► 13. message_post "Purchase Order Confirmed"
   │             └─► 14. activity_schedule() for receipt follow-up

PHASE 2: GOODS RECEIPT
15. stock.picking.action_confirm()
   ├─► 16. _action_confirm() per move
   │      └─► 17. state = 'confirmed'
   │
   ├─► 18. stock.picking.action_assign() [manual/automatic]
   │      └─► 19. _action_assign()
   │             └─► 20. state = 'assigned' (for incoming receipt, usually immediate)
   │
   ├─► 21. User receives goods: stock.picking.action_done()
   │      └─► 22. _button_done() per move
   │             ├─► 23. stock.quant._update_available_quantity(+qty, location=dest)
   │             │      └─► 24. qty_on_hand increased at stock location
   │             ├─► 25. stock.valuation.layer.create()
   │             │      └─► 26. unit_cost = pol.price_unit
   │             ├─► 27. account.move.line.create() [if automatic valuation]
   │             │      └─► 28. debit to stock interim account, credit to AP vendor
   │             └─► 29. state = 'done'
   │
   ├─► 30. po_line.qty_received updated
   │      └─► 31. if qty_received >= product_qty: fully received

PHASE 3: VENDOR BILL
32. purchase.order.action_create_invoice()
   ├─► 33. account.move.create({'move_type': 'in_invoice', ...})
   │      ├─► 34. _onchange_partner_id() → fiscal position applied
   │      ├─► 35. invoice_date_due = payment_terms.compute()
   │      └─► 36. for each pol: account.move.line.create()
   │             ├─► 37. debit = price_subtotal
   │             ├─► 38. account = expense (for service) or stock (for product)
   │             └─► 39. taxes applied from product + vendor
   │
   ├─► 40. account.move.action_post()
   │      ├─► 41. fiscal lock date check
   │      ├─► 42. sequence → move_name
   │      ├─► 43. state = 'posted'
   │      └─► 44. lines locked (debit/credit immutable)

PHASE 4: PAYMENT
45. User registers payment: account.payment.create()
   ├─► 46. account.payment.action_post()
   │      ├─► 47. account.move.create() for payment
   │      │      ├─► 48. line: credit to bank/cash account
   │      │      └─► 49. line: debit to vendor payable account
   │      └─► 50. lines reconciled with bill lines
   │
   └─► 51. account.move state: 'posted' → 'in_payment' → 'paid'
```

---

## Cross-Module Linkage

```
purchase.order.line
  └─► stock.move (procurement)
         └─► stock.picking (receipt)
                └─► stock.quant (inventory)
                       └─► account.move (valuation entry)
                               └─► account.move (vendor bill)
                                      └─► account.payment (settlement)
```

---

## Key Difference: Purchase vs Sale Flow

| Aspect | Sale Flow | Purchase Flow |
|--------|-----------|--------------|
| Picking direction | WH → Customer | Vendor → WH |
| Invoice type | out_invoice | in_invoice |
| Vendor vs Customer | Customer | Vendor |
| Payment direction | Customer pays you | You pay vendor |
| Tax | Output tax (VAT out) | Input tax (VAT in) |
| Cost of goods | COGS credited | Stock received debited |

---

## Decision Tree

```
PO Confirmed
│
├─► Product type?
│  ├─► Storable → picking created
│  └─► Service → no picking
│
├─► Billing policy?
│  ├─► Bill based on ordered → bill_qty = ordered
│  └─► Bill based on received → bill_qty = qty_received
│
└─► Valuation?
   ├─► Manual → no auto valuation entries
   └─► Automatic → entries on receipt
```

---

## Database State Summary

| Table | Records | Key Fields |
|-------|---------|------------|
| `purchase_order` | Updated | state='purchase' |
| `stock_picking` | Created | type='incoming', state |
| `stock_move` | Created | product_qty, price_unit |
| `stock_quant` | Updated | qty_on_hand increased |
| `stock_valuation_layer` | Created | unit_cost=pol.price_unit |
| `account_move` | Created | move_type='in_invoice' |
| `account_move_line` | Created | debit, credit |
| `account_payment` | Created | amount, partner=vendor |

---

## Related

- [Modules/Purchase](modules/purchase.md) — Purchase module reference
- [Modules/Stock](modules/stock.md) — Stock module reference
- [Modules/Account](modules/account.md) — Account module reference
- [Flows/Purchase/purchase-order-creation-flow](flows/purchase/purchase-order-creation-flow.md) — PO creation
- [Flows/Purchase/purchase-order-receipt-flow](flows/purchase/purchase-order-receipt-flow.md) — Receipt
- [Flows/Purchase/purchase-to-bill-flow](flows/purchase/purchase-to-bill-flow.md) — Vendor bill
