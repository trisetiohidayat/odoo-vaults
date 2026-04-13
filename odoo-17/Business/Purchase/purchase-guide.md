---
tags: [odoo, odoo17, guide]
---

# Purchase Guide

## Creating a Purchase Order

1. Go to **Purchase -> Orders -> Requests for Quotation**
2. Click **Create**
3. Select vendor
4. Add products and quantities
5. Click **Send** to email the vendor

## Confirming an Order

1. Vendor confirms pricing and availability
2. Click **Confirm Order**
3. System creates receipt picking (inbound receipt)

## Recording a Vendor Bill

1. Go to **Purchase -> Vendors -> Bills**
2. Click **Create**
3. Select vendor, add invoice lines
4. Match with purchase order if needed (use **Add Credit Note** or link to PO)
5. Confirm and **Post**

## Managing Purchase Orders

- View associated receipt pickings from the **Delivery Orders** smart button
- Use **Register Payment** to record payment against vendor bills
- Control multi-company visibility with `company_id` field

## See Also

- [Modules/purchase](odoo-18/Modules/purchase.md)
- [Modules/stock](odoo-18/Modules/stock.md)
- [Modules/account](odoo-18/Modules/account.md)
