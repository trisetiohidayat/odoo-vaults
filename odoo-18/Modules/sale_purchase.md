# sale_purchase — Sale Purchase

**Tags:** #odoo #odoo18 #sale #purchase #procurement #mto
**Odoo Version:** 18.0
**Module Category:** Sale + Purchase Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_purchase` creates purchase orders from sale order service lines. For service products that cannot be stock-managed, it automatically finds vendors, creates POs, and links them back to the original SOL. It handles quantity increase/decrease propagation, PO cancellation with activity notifications, and full bidirectional traceability.

**Technical Name:** `sale_purchase`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_purchase/`
**Depends:** `sale`, `purchase`
**Inherits From:** `sale.order`, `sale.order.line`, `purchase.order`, `product.template`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/sale_order.py` | `sale.order` | PO count, confirm/cancel actions |
| `models/sale_order_line.py` | `sale.order.line` | PO lines, generation, qty sync |
| `models/purchase_order.py` | `purchase.order` | PO count from linked SOs |
| `models/product_template.py` | `product.template` | Service-to-purchase toggle |

---

## Models Reference

### `sale.order.line` (models/sale_order_line.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `purchase_line_ids` | One2many | Linked POLs |
| `purchase_line_count` | Integer | Count of linked POLs |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_purchase_count()` | Counts linked POLs |
| `_onchange_service_product_uom_qty()` | Warns when decreasing qty below already-ordered |
| `_purchase_service_generation()` | Orchestrates full PO generation/update |
| `_purchase_service_create()` | Creates new PO per vendor with all matching SOLs |
| `_purchase_increase_ordered_qty()` | Updates existing POL qty |
| `_purchase_decrease_ordered_qty()` | Schedules activity on SO when qty decreased |
| `_purchase_service_get_company()` | Determines which company handles the PO |
| `_purchase_service_prepare_order_values()` | Builds PO header vals |
| `_purchase_service_prepare_line_values()` | Builds POL line vals |
| `_purchase_service_get_price_unit_and_taxes()` | Gets vendor price and applicable taxes |
| `_purchase_service_get_product_name()` | Gets vendor product name/description |
| `_purchase_service_match_supplier()` | Finds matching seller/address record |
| `_purchase_service_match_purchase_order()` | Finds or creates PO for vendor |
| `_create_purchase_order()` | Creates new PO |
| `_match_or_create_purchase_order()` | Route to find or create |
| `_retrieve_purchase_partner()` | Gets vendor partner from product seller |
| `_purchase_get_date_order()` | Sets PO date_order from SO |

---

### `sale.order` (models/sale_order.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `purchase_order_count` | Integer | Count of linked POs |

#### Methods

| Method | Behavior |
|--------|----------|
| `_action_confirm()` | Calls `_purchase_service_generation()` on SOLs |
| `_action_cancel()` | Schedules activities on linked POs |
| `action_view_purchase_orders()` | Returns action for PO list |
| `_get_purchase_orders()` | Returns all POs linked via POLs |
| `_activity_cancel_on_purchase()` | Logs cancellation on PO and schedules follow-up |

---

### `product.template` (models/product_template.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `service_to_purchase` | Boolean | Company-dependent: generate PO from SOL (compute+store) |

#### Methods

| Method | Behavior |
|--------|----------|
| `_check_service_to_purchase()` | Constrains: if True, `type` must be 'service' |
| `_onchange_service_to_purchase()` | Warns when enabling on a product already used in confirmed SOs |

---

## Security File

No security file.

---

## Data Files

No data file.

---

## Critical Behaviors

1. **PO Generation from SOL**: When `service_to_purchase=True` on a service product, `_purchase_service_generation()` creates POs from the SOL. One PO per vendor — if multiple SOLs use the same vendor, they are consolidated into a single PO.

2. **Vendor Selection**: `_purchase_service_match_supplier()` finds the best seller record using `seller_ids` (preferred vendor, quantity discount, delivery lead time). Falls back to the first available seller.

3. **Qty Propagation**: Increases on SOL call `_purchase_increase_ordered_qty()` to update POL. Decreases call `_purchase_decrease_ordered_qty()` which schedules a warning activity on the SO (not auto-cancel — requires manager decision).

4. **Company Matching**: `_purchase_service_get_company()` ensures the PO is created in the same company as the SOL's sale order, handling multi-company scenarios.

5. **PO↔SO Link via Procurement Group**: Each SOL's procurement is placed in a procurement group that carries the `sale_id` for traceability.

6. **Cancel Cascade**: `sale.order._action_cancel()` calls `_activity_cancel_on_purchase()` to post a note on the PO and schedule a follow-up activity, rather than hard-canceling the PO.

---

## v17→v18 Changes

- `_purchase_service_get_company()` method added for multi-company handling
- `_purchase_get_date_order()` added for PO date management
- `_activity_cancel_on_purchase()` method added for improved cancel UX
- `service_to_purchase` field now supports company-dependent values

---

## Notes

- `sale_purchase` is the service equivalent of `purchase_stock` for stockable products
- Only service products (`type='service'`) can use the service-to-purchase flow
- The `service_to_purchase` flag is a per-company setting allowing different behaviors per subsidiary
- `_purchase_service_match_purchase_order()` is the consolidation point: if a PO exists for the vendor+company combination, the new SOL is added to it
