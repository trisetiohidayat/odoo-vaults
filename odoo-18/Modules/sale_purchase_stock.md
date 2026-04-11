# sale_purchase_stock — Sale Purchase Stock

**Tags:** #odoo #odoo18 #sale #purchase #stock
**Odoo Version:** 18.0
**Module Category:** Sale + Purchase + Stock Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_purchase_stock` extends `sale_purchase` with stock picking links on purchase orders. When a PO is created from a sale order service (via `sale_purchase`), incoming receipt pickings can be tracked and linked back to the original SO. It also schedules follow-up activities when the SO is cancelled with outstanding linked POs.

**Technical Name:** `sale_purchase_stock`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_purchase_stock/`
**Depends:** `sale_purchase`, `purchase_stock`
**Inherits From:** `purchase.order`, `purchase.order.line`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/purchase_order.py` | `purchase.order` | SO count, SO view action, cancel activity |
| `models/purchase_order_line.py` | `purchase.order.line` | SOL→POL links, index on sale_line_id |

---

## Models Reference

### `purchase.order` (models/purchase_order.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `sale_order_count` | Integer | Count of linked SOs |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_sale_order_count()` | Counts distinct SOs via linked POLs |
| `action_view_sale_orders()` | Returns action for linked SO list |
| `button_cancel()` | Schedules cancellation activity on linked SOs |
| `_get_sale_orders()` | Returns SOs linked via POLs and group_id.sale_id |
| `_activity_cancel_on_sale()` | Posts cancel note on SO, schedules activity |

---

### `purchase.order.line` (models/purchase_order_line.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `sale_order_id` | Many2one | Related from `sale_line_id.order_id` (stored) |
| `sale_line_id` | Many2one | Link to source SOL (index btree_not_null) |

---

## Critical Behaviors

1. **SOL→POL Index**: `sale_line_id` has `index='btree_not_null'` for fast lookups from POL to SOL.

2. **Cancel Activity**: When a PO is cancelled via `button_cancel()`, `_activity_cancel_on_sale()` notifies the linked SOs by posting a message and scheduling a follow-up activity.

3. **Combined with `sale_purchase`**: This module adds the stock dimension (receipt picking tracking) on top of `sale_purchase`'s PO generation logic.

---

## v17→v18 Changes

No significant changes from v17 to v18 identified.

---

## Notes

- Thin module extending both `sale_purchase` and `purchase_stock`
- `sale_line_id` index enables efficient SOL↔POL lookups in reporting and reconciliation
- The `sale_order_id` stored related field provides quick access to the parent SO without traversing through `sale_line_id.order_id`
