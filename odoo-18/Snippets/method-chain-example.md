---
type: snippets
name: method-chain-example
version: Odoo 18
tags: [snippets, method-chain, notation]
---

# Method Chain Notation

Standard notation for documenting multi-step method call chains in Odoo.

## Sale Order → Delivery → Invoice

```
sale.order.create()
  └─→ .action_confirm()
        └─→ _create_delivery_orders()  [via stock.picking]
              └─→ stock.picking.button_validate()
                    └─→ stock.move._action_done()
                          └─→ stock.quant._update_available_quantity()
  └─→ sale.order._create_invoices()
        └─→ account.move.create()
              └─→ .action_post()
```

## Purchase Order → Receipt → Bill

```
purchase.order.create()
  └─→ button_confirm()
        └─→ _create_picking()
              └─→ stock.picking.button_validate()
                    └─→ stock.quant._update_available_quantity()
  └─→ action_create_invoice()
        └─→ account.move.create()
```

## Leave Request Flow

```
hr.leave.create()
  └─→ _compute_date_from_to()
  └─→ _onchange_leave_dates()
  └─→ action_validate()  [by manager]
        └─→ activity_ids.create()  [notification]
        └─→ _create_resource_leave()
              └─→ resource.calendar.leaves.create()
```

---

## Related Links
- [Flows/Sale/quotation-to-sale-order-flow](flows/sale/quotation-to-sale-order-flow.md) — Full sale flow
- [Flows/Purchase/purchase-order-creation-flow](flows/purchase/purchase-order-creation-flow.md) — Full purchase flow
