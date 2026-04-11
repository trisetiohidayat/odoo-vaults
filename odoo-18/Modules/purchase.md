---
type: module
name: purchase
version: Odoo 18
models_count: ~12
documentation_date: 2026-04-11
tags: [purchase, procurement, vendors, rfq]
---

# Purchase

Request for Quotation (RFQ) to Purchase Order management for procurement from vendors.

## Models

### purchase.order

Main purchase order model. States: `draft` → `sent` → `purchase` (confirmed) → `done` / `cancel`.

**Key Fields:**
- `name` — Auto-generated PO reference
- `partner_id` (`res.partner`) — Vendor
- `line_ids` (`purchase.order.line`) — PO lines
- `date_order` — RFQ/PO date
- `date_approve` — Approval timestamp
- `date_planned` — Expected delivery date (latest line)
- `state` — `draft`, `sent`, `purchase`, `cancel`, `done`
- `amount_total`, `amount_untaxed` — Totals
- `currency_id` (`res.currency`) — Currency
- `invoice_status` — `no`, `to invoice`, `invoicing`, `yes`
- `picking_ids` — Related stock pickings
- `order_line` → `product_id` relation
- `partner_ref` — Vendor's reference/PO number
- `incoterm_id` (`account.incoterms`) — Incoterms
- `fiscal_position_id` (`account.fiscal.position`) — Fiscal mapping
- `picking_policy` — `receive` (partial) or `flexible` (all at once)
- `company_id` (`res.company`) — Operating company

**L3 Workflow:** `button_confirm()` → `picks.auto_modify` → `_add_supplier_to_product()`:
1. Calls `_add_supplier_to_product()` — adds vendor as supplier on product if not exists
2. Creates `procurement.group` for the PO
3. Triggers `purchase_stock` picking creation

**Key Methods:**
- `_add_supplier_to_product()` — Creates `product.supplierinfo` from vendor/price/UOM data on PO confirmation
- `_prepare_picking()` — Generates values for incoming `stock.picking`
- `_get_groups_to_merge_into(line)` — Groups same-product lines on same order to same procurement group

### purchase.order.line

**Key Fields:**
- `order_id` (`purchase.order`) — Parent PO
- `product_id` (`product.product`) — Product to purchase
- `product_uom_qty` — Quantity to order
- `product_uom` (`uom.uom`) — Unit of measure
- `price_unit` — Negotiated price
- `discount` — Line discount %
- `taxes_id` (`account.tax`, many2many) — Taxes
- `date_planned` — Expected receipt date for this line
- `qty_received` — Received quantity (stock moves)
- `qty_received_manual` — Manual override
- `qty_invoiced` — Invoiced quantity
- `product_purchase_description` — Vendor-specific product description

**L3 Behavior:**
- `product_id` change triggers: seller_ids lookup → name update → taxes update → UOM update
- `qty_received` uses `qty_received_manual` if > 0, else sums from done `stock.move` records
- `_update_received_qty()` called by stock.move write — updates qty_received based on procurement group
- Lines with same `product_id` on same PO are mergeable into one via `_get_groups_to_merge_into()`

### purchase.requisition (Phase 3)

Call for Tenders / Blanket Orders — procurement bidding process.

## Purchase Stock Extensions (purchase_stock)

`sale.order` gains:
- `effective_date` — When first receipt was validated
- `group_id` (`procurement.group`) — Groups incoming/outgoing moves
- `move_ids` — Generated stock moves
- `picking_ids` — Stock pickings
- `incoming_picking_count`, `delivery_count`
- `receipt_status` — `pending` / `partial` / `full` / `done`

`sale.order.line` gains:
- `move_ids` — Stock moves from this PO line
- `qty_received_method` — `manual` or `stock_move`
- `move_dest_id` — Links to outgoing stock move (DROPSHIP etc.)
- `route_id` — Route for procurement

**Key Methods:**
- `_create_or_update_picking()` — Called on PO confirmation; creates/checks existing incoming picking
- `_create_stock_moves()` — Generates `stock.move` records per PO line
- `_merge_moves(product_id)` — Groups moves by (product, group, route)
- `_adjust_procurement_group_key(vals)` — Includes vendor info in group key

## Integrations

- **Stock** (`purchase_stock`): Confirmed PO creates `stock.picking` (incoming receipt)
- **Account**: PO confirmation creates vendor bill (`account.move`); invoice_policy affects `amount_to_invoice`
- **Product**: Vendor info from `product.supplierinfo` (seller_ids)
- **Purchase**: Uses `purchase_analytic_precision` from `res.company`

## Code

- Model: `~/odoo/odoo18/odoo/addons/purchase/models/purchase.py`
- Stock extension: `~/odoo/odoo18/odoo/addons/purchase_stock/models/`
