# purchase_requisition_stock — Purchase Requisition Stock

**Tags:** #odoo #odoo18 #purchase #requisition #stock #warehouse #procurement
**Odoo Version:** 18.0
**Module Category:** Purchase + Requisition + Stock Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`purchase_requisition_stock` connects purchase requisitions with the warehouse/stock management system, adding warehouse assignment to requisitions, propagating `move_dest_id` through requisition lines, and overriding stock rule logic to route procurement through requisitions. It also adds on-time delivery rate computation for requisitions.

**Technical Name:** `purchase_requisition_stock`
**Python Path:** `~/odoo/odoo18/odoo/addons/purchase_requisition_stock/`
**Depends:** `purchase_requisition`, `purchase_stock`
**Inherits From:** `purchase.requisition`, `purchase.requisition.line`, `stock.rule`, `stock.move`, `purchase.order`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/purchase_requisition.py` | `purchase.requisition`, `purchase.requisition.line` | Warehouse/picking type on requisition; `move_dest_id` on lines |
| `models/stock.py` | `stock.rule`, `stock.move` | Requisition-aware PO creation, upstream document propagation |
| `models/purchase.py` | `purchase.order` | On-time rate per requisition |
| `wizard/purchase_requisition_create_alternative.py` | `purchase.requisition.create.alternative` (wizard) | Passes picking type and `move_dest_id` to alternative POs |

**Wizard File:** `wizard/purchase_requisition_create_alternative.py` (lines 10–30)

- `_get_alternative_values()` — Adds `picking_type_id` and `group_id` from the origin PO to the new PO values.
- `_get_alternative_line_value(order_line)` — Passes `move_dest_ids` (downstream stock moves) through to the alternative PO line.

---

## Models Reference

### `purchase.requisition` (models/purchase_requisition.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `warehouse_id` | Many2one (`stock.warehouse`) | Target warehouse for the requisition, constrained to company |
| `picking_type_id` | Many2one (`stock.picking.type`) | Operation type (incoming receipt), defaults to company's incoming picking type |

#### Methods

| Method | Behavior |
|--------|----------|
| `_default_picking_type_id()` | Returns the first incoming picking type for the company's warehouse |

---

### `purchase.requisition.line` (models/purchase_requisition.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `move_dest_id` | Many2one (`stock.move`) | Downstream stock move that will consume the ordered qty |

#### Methods

| Method | Line | Behavior |
|--------|------|----------|
| `_prepare_purchase_order_line()` | 27 | Override: adds `move_dest_ids` to PO line vals so the procurement is linked to the destination move |

---

### `stock.rule` (models/stock.py)

#### Methods

| Method | Line | Behavior |
|--------|------|----------|
| `_prepare_purchase_order()` | 10 | Override: if the supplier has a `purchase_requisition_id`, sets `requisition_id` and `partner_ref` on the PO, and overrides currency from the requisition |
| `_make_po_get_domain()` | 19 | Override: adds `requisition_id` to the PO merge domain when a supplier has a linked requisition — ensures POs from the same requisition are merged |

---

### `stock.move` (models/stock.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `requisition_line_ids` | One2many (`purchase.requisition.line`) | Links moves to requisition lines that created them |

#### Methods

| Method | Line | Behavior |
|--------|------|----------|
| `_get_upstream_documents_and_responsibles()` | 33 | Override: if `requisition_line_ids` exist, returns the requisition as the upstream document (sudo mode, so non-purchase users can still trace) |

---

### `purchase.order` (models/purchase.py)

Extends the on-time rate computation from `purchase_stock` to include requisition context. The requisition's expected delivery date factors into the PO's on-time rate calculation.

---

## Wizard Reference

### `purchase.requisition.create.alternative` (wizard/)

Extends the standard alternative PO wizard from `purchase_requisition` to include:
- `picking_type_id`: Passes the requisition's picking type to the new PO
- `move_dest_ids`: Passes the destination move from the requisition line to the new PO line

---

## Security File

No security file.

---

## Data Files

None.

---

## Critical Behaviors

1. **Warehouse Assignment**: `warehouse_id` on `purchase.requisition` ensures that when POs are created from the requisition, they are assigned to the correct warehouse. The `picking_type_id` defaults to that warehouse's incoming receipt type.

2. **`move_dest_id` Propagation**: When a requisition line creates a PO line, `_prepare_purchase_order_line()` links the PO line to the downstream stock move via `move_dest_ids`. This is the key stock→requisition→PO linkage.

3. **Requisition-Aware PO Merge**: `_make_po_get_domain()` adds `requisition_id` to the merge domain so that POs from the same requisition are properly grouped — even if they have different partners (when requisitions override partner selection).

4. **Requisition as Upstream Doc**: `_get_upstream_documents_and_responsibles()` uses sudo mode to return the requisition as the upstream document for traceability — allowing non-purchase users to trace moves back to the requisition without needing purchase access.

5. **Currency Override**: If a supplier has a `purchase_requisition_id`, the requisition's currency is used for the PO rather than the supplier's default — ensuring correct currency for blanket orders in foreign currencies.

---

## v17→v18 Changes

- `warehouse_id` and `picking_type_id` fields added to `purchase.requisition` for warehouse-specific requisitions
- `_make_po_get_domain()` enhancement to group POs by requisition even with different partners
- `_get_upstream_documents_and_responsibles()` refactored to use sudo for cross-access traceability

---

## Notes

- `purchase_requisition_stock` is the stock/warehouse extension of `purchase_requisition`
- When blanket orders are used via purchase requisitions, the warehouse context ensures correct routing of receipts
- The `requisition_line_ids` on `stock.move` enables tracing any stock move back to the requisition line that generated the procurement
- `auto_install` is not set, so this module must be explicitly installed alongside `purchase_requisition` and `purchase_stock`
