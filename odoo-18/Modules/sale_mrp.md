# sale_mrp — Sale MRP

**Tags:** #odoo #odoo18 #sale #mrp #manufacturing #kit #anglo-saxon
**Odoo Version:** 18.0
**Module Category:** Sale + MRP Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_mrp` bridges Sale Orders and MRP Production orders. It enables sale-order-linked manufacturing, kit (phantom bom) exploded delivery tracking, sale-line-to-production-line linkage for MO traceability, and component-level COGS computation for manufactured products using the Anglo-Saxon method.

**Technical Name:** `sale_mrp`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_mrp/`
**Depends:** `sale_stock`, `mrp`
**Inherits From:** `sale.order`, `sale.order.line`, `mrp.production`, `account.move`, `stock.rule`, `stock.move.line`, `mrp.bom`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/sale_order.py` | `sale.order` | MRP production count, MO view action |
| `models/sale_order_line.py` | `sale.order.line` | Kit qty delivery, MTO procurement, bom component qty |
| `models/mrp_production.py` | `mrp.production` | Sale order linkage, sale count, MO→SO link |
| `models/mrp_bom.py` | `mrp.bom` | BoM lifecycle (active check, unlink protection) |
| `models/account_move.py` | `account.move` | Kit component COGS price for Anglo-Saxon |
| `models/stock_rule.py` | `stock.rule` | MO generation from procurement, component vals |
| `models/stock_move_line.py` | `stock.move.line` | Kit component sale price computation |

---

## Models Reference

### `sale.order.line` (models/sale_order_line.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_qty_to_deliver()` | Hides delivery widget for kit lines (`bom_id` with `type='phantom'`) |
| `_compute_qty_delivered()` | Full kit qty: finds bom, filters component moves, multiplies by bom line qty |
| `_get_bom_component_qty()` | Returns `{product_id: {uom, qty, bom_line_id}}` dict |
| `_get_incoming_outgoing_moves_filter()` | Filters moves for kit component tracking |
| `_get_qty_procurement()` | Gets procurement qty for kit component |
| `_action_launch_stock_rule()` | Excludes kit lines from stock rule (handled via MO) |
| `compute_uom_qty()` | Multiplies by bom_line qty for kit lines |
| `_prepare_procurement_values()` | Adds bom_line_id for component procurement |
| `_get_action_add_from_catalog_extra_context()` | Excludes kit products from catalog |
| `_get_product_catalog_lines_data()` | Excludes kit products from catalog |
| `_can_be_edited_on_portal()` | False for kit lines |

---

### `mrp.production` (models/mrp_production.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `sale_line_id` | Many2one | Linked sale order line |
| `sale_order_count` | Integer | Count of related SOs |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_sale_order_count()` | Counts distinct SOs via `sale_line_id.order_id` |
| `get_linked_sale_orders()` | Returns SOs via sale_line_ids |
| `action_view_sale_orders()` | Returns action for SO list |
| `action_confirm()` | Sets `sale_line_id` on component moves |
| `_post_run_manufacture()` | Sets `sale_id` on procurement_group for pickings |
| `_get_document_iterate_key()` | Adds `created_purchase_line_ids` to iteration |
| `_prepare_merge_orig_links()` | Preserves `sale_line_id` in move chain |

---

### `mrp.bom` (models/mrp_bom.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `toggle_active()` | Deactivates related BoMs |
| `write()` | Cascades active state to children |
| `unlink()` | Calls `_ensure_bom_is_free()` first |
| `_ensure_bom_is_free()` | Raises if phantom BoM is linked to active SOs |

---

### `account.move` (models/account_move.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `_stock_account_get_anglo_saxon_price_unit()` | For kit products: computes COGS from component average costs, recursively summing component SVLs |

---

### `stock.rule` (models/stock_rule.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `_prepare_mo_vals()` | Adds `sale_line_id` to MO vals |
| `_get_stock_move_values()` | Adds `bom_line_id` to component move vals |

---

## Security File

No security file (`security/` directory does not exist in this module).

---

## Data Files

No data file (`data/` directory does not exist in this module).

---

## Critical Behaviors

1. **Kit Explosion on Delivery**: For `type='phantom'` BoMs, `_compute_qty_delivered()` computes the kit quantity by summing component move quantities, multiplying by the bom line ratio. The finished product is never received — only its components are delivered.

2. **BoM Protection**: `_ensure_bom_is_free()` prevents unlinking a phantom BoM that is referenced by an active sale order line. This protects against broken kit delivery calculations.

3. **Kit COGS**: `_stock_account_get_anglo_saxon_price_unit()` on `account.move` recursively averages all component standard prices to get the kit's COGS price, enabling correct margin calculation for manufactured products.

4. **MO→SO Link**: When an MO is created from a sale order (via the `procurement.group.sale_id` link), `sale_line_id` is set on the MO for full traceability back to the SOL.

5. **MTO Kit Procurement**: Kit lines use a different procurement path — the MTO route triggers an MO generation via `stock.rule` rather than a direct stock move. `_prepare_mo_vals()` passes `sale_line_id` into the MO.

6. **Sale-Line-Level COGS**: On `action_confirm()`, component moves carry `sale_line_id` for cost attribution to the specific sale line.

---

## v17→v18 Changes

- `_get_incoming_outgoing_moves_filter()` method added for improved kit component move filtering
- `_get_action_add_from_catalog_extra_context()` and `_get_product_catalog_lines_data()` added to exclude kit products from product catalog
- `_can_be_edited_on_portal()` added to prevent portal editing of kit lines
- `_compute_qty_to_deliver()` now explicitly hides widget for kit lines

---

## Notes

- Kit products are a phantom BOM pattern: the finished product is never stocked, only its components are delivered
- The `sale_line_id` on `mrp.production` enables bidirectional traceability
- Component COGS averaging means a manufactured kit's margin reflects actual component costs at time of delivery
- `_ensure_bom_is_free()` runs a full check on `sale.order.line` to verify no active SOs reference the BoM
