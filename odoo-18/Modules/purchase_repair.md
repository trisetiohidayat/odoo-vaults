# purchase_repair — Purchase Repair

**Tags:** #odoo #odoo18 #purchase #repair #cross-navigation
**Odoo Version:** 18.0
**Module Category:** Purchase + Repair Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`purchase_repair` creates cross-links between purchase orders and repair orders, enabling bidirectional navigation between POs and their related repairs. When a product is received on a PO and later sent for repair, this module maintains the traceability chain and provides quick-action buttons to navigate between the two documents.

**Technical Name:** `purchase_repair`
**Python Path:** `~/odoo/odoo18/odoo/addons/purchase_repair/`
**Depends:** `repair`, `purchase_stock`
**Inherits From:** `purchase.order`, `repair.order`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/purchase_order.py` | `purchase.order` | `repair_count`, navigation to repairs |
| `models/repair_order.py` | `repair.order` | `purchase_count`, navigation to POs |

---

## Models Reference

### `purchase.order` (models/purchase_order.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `repair_count` | Integer (compute) | Count of repair orders whose source stock move is linked to this PO's lines |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_repair_count()` | Counts `repair_id` on `order_line.move_dest_ids` |
| `action_view_repair_orders()` | Opens repair order list/form for this PO |

---

### `repair.order` (models/repair_order.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `purchase_count` | Integer (compute) | Count of POs linked via `move_ids.created_purchase_line_ids` |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_purchase_count()` | Counts distinct POs via `move_ids.created_purchase_line_ids.order_id` |
| `action_view_purchase_orders()` | Opens PO list/form for this repair |

---

## Linkage Mechanism

The repair↔PO link is established through `stock.move` chains:

```
purchase.order.line
  → stock.move (incoming: receipt from vendor)
      → move_dest_id (forwarded move, e.g., to repair location)
          → repair.order (via repair_id on move)
```

When a repair order is created and uses a product that was received via a PO, `purchase_stock` links the repair's outgoing move back to the PO line via `created_purchase_line_ids`. `purchase_repair` then exposes this link at the document level.

---

## Security File

No security file.

---

## Data Files

None.

---

## Critical Behaviors

1. **Navigation from PO**: `_compute_repair_count()` traces `move_dest_ids` from PO lines to find repairs that used those received products. `action_view_repair_orders()` provides a button to jump directly to the repair.

2. **Navigation from Repair**: `_compute_purchase_count()` traces `move_ids.created_purchase_line_ids` from the repair to find POs that supplied the parts used in the repair. `action_view_purchase_orders()` provides a button to jump to the PO.

3. **Count = 0 vs > 0**: The navigation action adapts — if exactly one document is found, opens the form directly; if multiple, opens a list view with domain filter.

4. **Group-Based Security**: `repair_count` is computed with `groups='stock.group_stock_user'` and `purchase_count` with `groups='purchase.group_purchase_user'` — navigation is only shown to users with relevant access rights.

---

## v17→v18 Changes

- No significant changes from v17 to v18
- Module structure and cross-navigation logic remain consistent

---

## Notes

- `purchase_repair` is a thin cross-navigation module — the actual link is created by `purchase_stock`'s `created_purchase_line_ids` on stock moves
- Use case: A company receives parts on PO, sends parts for repair, and wants to trace which PO supplied the parts being repaired
- The bidirectional navigation helps both procurement (which repairs used my POs?) and repair workshop (which PO supplied these parts?) teams
