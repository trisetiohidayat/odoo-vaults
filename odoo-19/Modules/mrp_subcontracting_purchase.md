# MRP Subcontracting Purchase

## Overview
- **Name:** Purchase and Subcontracting Management
- **Category:** Supply Chain/Purchase
- **Depends:** `mrp_subcontracting`, `purchase_mrp`
- **Auto-install:** Yes
- **License:** LGPL-3

## Description
Bridge module between MRP Subcontracting and Purchase. Adds smart buttons and views linking subcontracting stock pickings to their associated Purchase Orders, enabling a full view from the subcontracted MO through to the vendor PO.

## Key Features
- **Smart buttons** on subcontracting pickings showing PO count.
- **Smart buttons** on PO form showing subcontracting picking count.
- Cross-navigation between PO and the subcontract pickings (receipts from subcontractor).

## Data
- `views/purchase_order_views.xml`: Adds subcontracting-related fields/views to PO.
- `views/stock_picking_views.xml`: Adds PO link to subcontract pickings.

## Demo Data
- `mrp_subcontracting_purchase_demo.xml`: Demo data for testing.

## Related
- [Modules/mrp_subcontracting](odoo-18/Modules/mrp_subcontracting.md) - Subcontract BoMs and MO tracking
- [Modules/purchase_mrp](odoo-18/Modules/purchase_mrp.md) - PO to MO linkage
