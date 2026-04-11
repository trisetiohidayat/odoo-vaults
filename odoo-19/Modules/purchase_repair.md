# purchase_repair

Odoo 19 Purchase/After-Sales Module

## Overview

`purchase_repair` links **Purchase Orders and Repair Orders**. When a repair order generates a purchase (e.g., ordering replacement parts), the PO is linked to the repair order for traceability.

## Module Details

- **Category**: Supply Chain/Purchase
- **Depends**: `repair`, `purchase_stock`
- **Version**: 1.0
- **Author**: Odoo S.A.
- **License**: LGPL-3
- **Auto-install**: Yes

## Key Components

### Models

#### `purchase.order` (Inherited)

| Field | Type | Description |
|---|---|---|
| `repair_count` | Integer | Count of linked repair orders (computed) |

`_compute_repair_count()` — Counts repair orders that have destination moves linked to this PO's order lines.

`action_view_repair_orders()` — Opens the related repair order(s) from the PO form.

#### `repair.order` (Inherited)

| Field | Type | Description |
|---|---|---|
| `purchase_count` | Integer | Count of generated POs (computed) |

`_compute_purchase_count()` — Counts POs created from repair moves (`created_purchase_line_ids`).

`action_view_purchase_orders()` — Opens linked purchase orders from the repair form.

## Usage

1. Create a Repair Order for a product under warranty or paid repair.
2. Use the repair's "Create Purchase Order" functionality (via `purchase_stock`) to source parts.
3. The PO is linked to the repair — from the PO you can view the source repair, and from the repair you can view generated POs.
