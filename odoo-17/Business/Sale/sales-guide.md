---
tags: [odoo, odoo17, guide]
---

# Sales Guide

## Creating a Quotation

1. Go to **Sales -> Orders -> Quotations**
2. Click **Create**
3. Select customer
4. Add products to order lines
5. Click **Send** to email the customer

## Confirming an Order

1. Customer accepts the quotation
2. Click **Confirm**
3. System creates delivery order (and optionally repair orders if `create_repair` is set on product)

## Managing Sale Orders

- View linked repair orders from the **Repair Orders** smart button on the sale order form
- `sale.order.line._create_repair_order()` auto-creates a `repair.order` on SO confirmation for products with `create_repair = True`
- Delivery quantities can be driven by completed repair orders

## See Also

- [[Modules/sale]]
- [[Modules/repair]]
- [[Modules/stock]]
