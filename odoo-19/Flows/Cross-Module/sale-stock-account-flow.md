---
type: flow
title: "Sale → Stock → Account Cross-Module Flow"
primary_model: sale.order
trigger: "User action — Sale Order → Confirm"
cross_module: true
models_touched:
  - sale.order
  - sale.order.line
  - procurement.group
  - stock.picking
  - stock.move
  - stock.quant
  - account.move
  - account.move.line
  - account.payment
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Sale/quotation-to-sale-order-flow](quotation-to-sale-order-flow.md)"
  - "[Flows/Stock/delivery-flow](delivery-flow.md)"
  - "[Flows/Account/invoice-post-flow](invoice-post-flow.md)"
  - "[Flows/Account/payment-flow](payment-flow.md)"
source_module: sale
source_path: ~/odoo/odoo19/odoo/addons/sale_stock/
created: 2026-04-06
version: "1.0"
---

# Sale → Stock → Account Cross-Module Flow

## Overview

Complete end-to-end flow from customer sale order through warehouse delivery to accounting entries. This cross-module flow spans three major areas: Sale (quotation → order), Stock (procurement → delivery), and Account (invoice → payment).

## Trigger Point

**User:** Opens **Sale → Quotations → [SO] → Confirm Sale Order**
**Method:** `sale.order.action_confirm()`

---

## Complete Method Chain (Phase 1: Sale Confirmation)

```
1. sale.order.action_confirm()
   │
   ├─► 2. _action_confirm()  [sale]
   │      ├─► 3. _ensure_cart_is_valid()
   │      │      └─► 4. cart prerequisite checks
   │      │
   │      ├─► 5. state = 'sale'
   │      ├─► 6. commitment_date set
   │      │
   │      ├─► 7. procurement_group_id = procurement.group.create({...})
   │      │      └─► 8. group.name = SO.name
   │      │
   │      ├─► 9. for each sol: _action_launch_stock_rule()
   │      │      └─► 10. procurement_group.run()
   │      │             └─► 11. stock.picking.create({...})
   │      │                   └─► 12. picking type = 'outgoing'
   │      │
   │      ├─► 13. _create_invoices()  [if order_policy='prepaid']
   │      │      └─► 14. account.move.create() draft invoice
   │      │
   │      ├─► 15. message_post "Sale Order Confirmed"
   │      └─► 16. activity_schedule()
```

---

## Complete Method Chain (Phase 2: Delivery)

```
17. stock.picking.action_confirm()  [automatic]
   ├─► 18. _action_confirm() per move
   │      └─► 19. state = 'confirmed'
   │
   ├─► 20. stock.picking.action_assign()  [automatic or manual]
   │      └─► 21. _action_assign() per move
   │             ├─► 22. stock.quant reserved (quantity updated)
   │             └─► 23. state = 'assigned'
   │
   ├─► 24. User validates: stock.picking.action_done()
   │      └─► 25. _button_done() per move
   │             ├─► 26. stock.quant reserved_qty -= done_qty
   │             ├─► 27. stock.quant qty_on_hand -= done_qty  [WH output]
   │             ├─► 28. stock.quant qty_on_hand += done_qty  [Customer loc]
   │             ├─► 29. stock.valuation.layer created
   │             ├─► 30. account.move.line created  [valuation entry]
   │             └─► 31. state = 'done'
```

---

## Complete Method Chain (Phase 3: Invoice & Payment)

```
32. User creates invoice: sale.order._create_invoices()
   ├─► 33. account.move.create()  [out_invoice]
   │      ├─► 34. _onchange_partner_id() → fiscal position
   │      ├─► 35. _onchange_journal() → journal set
   │      └─► 36. for each sol: account.move.line.create()
   │             └─► 37. taxes computed from product + fiscal position
   │
   ├─► 38. account.move.action_post()  [manual or auto]
   │      ├─► 39. fiscal lock date check
   │      ├─► 40. sequence.next_by_code() → move_name assigned
   │      ├─► 41. state = 'posted'
   │      └─► 42. account.move.line records locked
   │
   ├─► 43. User registers payment: account.payment.create()
   │      ├─► 44. account.payment.action_post()
   │      │      ├─► 45. account.move.create() for payment
   │      │      ├─► 46. line: debit to bank account
   │      │      ├─► 47. line: credit to receivable (customer)
   │      │      └─► 48. account.move.line reconcile()
   │      │
   │      └─► 49. invoice.state: 'posted' → 'in_payment' → 'paid'
```

---

## Cross-Module Linkage

```
sale.order
  └─► procurement_group_id → links to stock.picking
         └─► stock.move → links back to sale.order.line
                └─► account.move.line (from invoice)

sale.order.line
  └─► stock.move (procurement link)
         └─► stock.picking (delivery)
                └─► account.move (valuation entry)
```

---

## Decision Tree

```
SO Confirmed
│
├─► order_policy?
│  ├─► 'prepaid' → create draft invoice immediately
│  ├─► 'manual' → no auto invoice
│  └─► 'postpaid' → invoice after delivery
│
├─► picking_policy?
│  ├─► 'direct' → create pickings immediately
│  ├─► 'one' → one picking per order
│  └─► 'multi' → multi-step delivery
│
└─► payment_policy?
   ├─► 'paid' → payment before confirmation
   └─► 'credit' → payment after delivery
```

---

## Database State Summary

| Table | Records | Key Fields |
|-------|---------|------------|
| `sale_order` | Updated | state = 'sale', commitment_date |
| `procurement_group` | Created | name = SO.name |
| `stock_picking` | Created | picking_type_id, group_id, state |
| `stock_move` | Created | product_id, product_uom_qty, state |
| `stock_quant` | Reserved/Updated | reserved_qty, qty_on_hand |
| `account_move` | Created | move_type='out_invoice', state |
| `account_move_line` | Created | debit, credit, account_id |
| `account_payment` | Created | amount, journal_id, state |

---

## Error Scenarios

| Scenario | Error | Module | Prevention |
|----------|-------|--------|-----------|
| Product not in stock | Picking stuck at 'waiting' | Stock | Check product availability |
| Invoice before delivery | Tax posted before delivery | Stock | Use 'postpaid' policy |
| Payment to wrong journal | Accounting error | Account | Select correct payment journal |
| Duplicate SO confirm | Picking already exists | Stock | Guard check on state |
| Product deleted after SO | Picking without product | Stock | Product must be active |

---

## Side Effects Summary

| Effect | Models | What Happens |
|--------|--------|-------------|
| Picking created | `stock.picking` | Delivery order generated |
| Quant reserved | `stock.quant` | Quantity held for this order |
| Quant moved | `stock.quant` | Stock decreased at output |
| Valuation entry | `account.move.line` | COGS recorded |
| Invoice receivable | `account.move` | Customer owes money |
| Payment received | `account.payment` | Customer balance cleared |

---

## Security Context

| Phase | Security Mode | Access Required |
|-------|-------------|---------------|
| SO Confirmation | Current user | `group_sale_salesman` |
| Picking Confirm | Current user | `group_stock_user` |
| Picking Done | Current user | `group_stock_user` |
| Invoice Post | Current user | `group_account_invoice` |
| Payment | Current user | `group_account_payment` |

---

## Transaction Boundary

| Phase | Boundary | Rollback on Failure |
|-------|----------|-------------------|
| Steps 1-16 | ✅ Atomic | Complete rollback |
| Steps 17-31 | ✅ Atomic | Picking can be re-opened |
| Steps 32-36 | ✅ Atomic | Invoice can be cancelled |
| Steps 38-48 | ✅ Atomic | Payment can be reversed |
| Async notifications | ❌ Outside | Queued separately |

---

## Related

- [Modules/Sale](Sale.md) — Sale module reference
- [Modules/Stock](Stock.md) — Stock module reference
- [Modules/Account](Account.md) — Account module reference
- [Flows/Sale/quotation-to-sale-order-flow](quotation-to-sale-order-flow.md) — Sale confirmation
- [Flows/Stock/delivery-flow](delivery-flow.md) — Delivery process
- [Flows/Account/invoice-post-flow](invoice-post-flow.md) — Invoice posting
- [Flows/Account/payment-flow](payment-flow.md) — Payment registration
