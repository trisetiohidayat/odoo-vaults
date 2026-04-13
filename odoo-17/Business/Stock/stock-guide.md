---
tags: [odoo, odoo17, guide]
---

# Stock Guide

## Checking On-Hand Quantities

1. Go to **Inventory -> Reporting -> Current Stock**
2. Filter by product, location, or lot/serial number

## Receiving Goods (Receipts)

1. Go to **Inventory -> Operations -> Receipts**
2. Find the receipt picking for the purchase order
3. Click into the picking, set quantities and lot numbers as needed
4. Click **Validate**

## Delivery Orders

1. Go to **Inventory -> Operations -> Delivery Orders**
2. Find the outbound picking linked to a sale order
3. Set quantities and lot/serial numbers
4. Click **Validate** to confirm the shipment

## Repair Operations

1. Go to **Inventory -> Operations -> Repairs**
2. Create or open a repair order
3. Add parts (use `repair_line_type`: `add`, `remove`, `recycle`)
4. Validate the repair to update stock and link back to sale order

## Managing Lots and Serial Numbers

1. Go to **Inventory -> Master Data -> Lots/Serial Numbers**
2. Track warranty and repair history per lot
3. Serial numbers can be linked to repair orders for traceability

## See Also

- [Modules/stock](modules/stock.md)
- [Modules/repair](modules/repair.md)
- [Modules/purchase](modules/purchase.md)
