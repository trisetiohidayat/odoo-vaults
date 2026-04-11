# purchase_mrp — Purchase MRP

**Tags:** #odoo #odoo18 #purchase #mrp #kit #cost-share #phantom-bom
**Odoo Version:** 18.0
**Module Category:** Purchase + MRP Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`purchase_mrp` bridges purchase orders with MRP manufacturing by tracking the PO→MO (Manufacturing Order) link and enabling kit (phantom BoM) purchasing with proportional component cost attribution. It also adds cross-navigation between POs and their linked manufacturing orders, and implements `cost_share` on `mrp.bom.line` for kit purchase price computation.

**Technical Name:** `purchase_mrp`
**Python Path:** `~/odoo/odoo18/odoo/addons/purchase_mrp/`
**Depends:** `mrp`, `purchase_stock`
**Inherits From:** `purchase.order`, `purchase.order.line`, `mrp.production`, `mrp.bom`, `mrp.bom.line`, `account.move.line`, `stock.move`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/purchase.py` | `purchase.order`, `purchase.order.line` | MO count/navigation, kit qty received, qty procurement |
| `models/mrp_production.py` | `mrp.production` | PO count/navigation, procurement group merge |
| `models/mrp_bom.py` | `mrp.bom`, `mrp.bom.line` | `cost_share` field + validation + `_get_cost_share()` |
| `models/account_move.py` | `account.move.line` | Kit valuation layer filtering for invoice corrections |
| `models/stock_move.py` | `stock.move` | Phantom kit price unit from PO, valuation for kits |

---

## Models Reference

### `purchase.order` (models/purchase.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `mrp_production_count` | Integer (compute) | Count of linked MOs via stock move chain |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_mrp_production_count()` | Counts MOs via `move_dest_ids.group_id.mrp_production_ids` |
| `_get_mrp_productions()` | Returns linked MOs: direct + rollup via `_rollup_move_dests()` |
| `action_view_mrp_productions()` | Opens the list/form of MOs linked to this PO |

---

### `purchase.order.line` (models/purchase.py)

#### Methods

| Method | Line | Behavior |
|--------|------|----------|
| `_compute_qty_received()` | 54 | Override: handles phantom kit receipt. Uses `_compute_kit_quantities()` to decompose received kit qty into component quantities |
| `_get_upstream_documents_and_responsibles()` | 80 | Returns PO as the upstream document for requisition traceability |
| `_get_qty_procurement()` | 83 | Override: for phantom kit, returns `previous_product_qty` from context (previous qty before change) |
| `_get_move_dests_initial_demand()` | 94 | Override: for phantom kit, uses `_compute_kit_quantities()` to roll up component demand to kit qty |

---

### `mrp.production` (models/mrp_production.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `purchase_order_count` | Integer (compute) | Count of linked POs via procurement group and move chain |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_purchase_order_count()` | Counts POs via `procurement_group_id` + rollup via `_rollup_move_origs()` |
| `action_view_purchase_orders()` | Opens PO list/form for this MO |
| `_get_document_iterate_key()` | Returns `'created_purchase_line_ids'` if the MO has created POs (enables procurement iteration) |
| `_get_purchase_orders()` | Returns linked POs: direct via `procurement_group_id` + rollup via `_rollup_move_origs()` |
| `_prepare_merge_orig_links()` | Override: includes `created_purchase_line_ids` in merge command so PO lines are tracked when MOs with PO links are merged |

---

### `mrp.bom` / `mrp.bom.line` (models/mrp_bom.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `cost_share` | Float | On `mrp.bom.line`: percentage (0-100) of kit cost attributed to this component. All non-zero cost shares must sum to 100 |

#### Methods

| Method | Behavior |
|--------|----------|
| `_check_bom_lines()` | Override (line 13): validates that all `cost_share` values are >= 0 and sum to exactly 100 if any are set |
| `_get_cost_share()` (line 33) | Returns `cost_share / 100` if set; otherwise equal split among lines without a cost share |

#### Cost Share Logic

```python
def _get_cost_share(self):
    if self.cost_share:
        return self.cost_share / 100  # e.g., 60% → 0.60
    bom = self.bom_id
    bom_lines_without_cost_share = bom.bom_line_ids.filtered(lambda bl: not bl.cost_share)
    return 1 / len(bom_lines_without_cost_share)  # equal split
```

When a kit product is purchased (not manufactured), `cost_share` determines what proportion of the kit's purchase price each component represents for margin and valuation purposes.

---

### `account.move.line` (models/account_move.py)

#### Methods

| Method | Line | Behavior |
|--------|------|----------|
| `_get_stock_valuation_layers()` | 10 | Filter: only return SVLs where `svl.product_id == self.product_id` — skips kit-level SVLs for component-level invoice lines |

---

### `stock.move` (models/stock_move.py)

#### Methods

| Method | Line | Behavior |
|--------|------|----------|
| `_prepare_phantom_move_values()` | 12 | Passes `purchase_line_id` through to component moves when a phantom kit is received into stock |
| `_get_price_unit()` | 18 | Override: for kit moves, computes price using the PO line's `kit_price_unit * cost_share * uom_factor * bom.product_qty / bom_line.product_qty` formula |
| `_get_valuation_price_and_qty()` | 44 | Override: for phantom kit SVL, uses `_compute_kit_quantities()` to get the component-level qty for valuation instead of the kit qty |

---

## Security File

No security file.

---

## Data Files

| File | Content |
|------|---------|
| `data/purchase_mrp_data.xml` | Default cost share configurations, if any |

---

## Critical Behaviors

1. **Phantom Kit Receipt**: When a kit product (phantom BoM) is received on a PO, `_compute_qty_received()` on `purchase.order.line` decomposes the kit qty into component quantities using `_compute_kit_quantities()`. This ensures the received qty is tracked at the component level for manufacturing.

2. **Cost Share for Kit Pricing**: When a kit is purchased (rather than manufactured), `_get_price_unit()` on `stock.move` uses the `cost_share` percentages from `mrp.bom.line` to proportionally distribute the kit's PO price across components. This is critical for margin accuracy on kit sales.

3. **MO↔PO Cross-Navigation**: `_get_mrp_productions()` traverses through `stock.move._rollup_move_dests()` to find MOs indirectly linked to the PO (e.g., MO generated from a component move that was itself linked to a PO line).

4. **Merge with PO Links**: `_prepare_merge_orig_links()` ensures that when MOs are merged, the `created_purchase_line_ids` links are preserved — without this, the procurement chain would break silently.

5. **Kit SVL Filtering**: `_get_stock_valuation_layers()` on `account.move.line` filters SVLs to only the component product, avoiding mismatches when posting kit invoices via Anglo-Saxon accounting.

---

## v17→v18 Changes

- `cost_share` field precision increased (digits (5,2) with explicit note about rounding importance)
- `_get_price_unit()` override added for more accurate kit component pricing from PO lines
- `_get_valuation_price_and_qty()` override added for correct phantom kit SVL quantity computation
- `_prepare_merge_orig_links()` added for MO merge with PO link preservation

---

## Notes

- `purchase_mrp` is the mirror of `sale_mrp` for the purchasing side
- `cost_share` on `mrp.bom.line` is the key feature for kit purchase price attribution — used by both `purchase_mrp` and `sale_mrp_margin`
- When a kit is purchased (not made), the full kit price is tracked in the PO; `cost_share` divides that price among components for valuation
- `stock_move._get_price_unit()` for kits requires the `purchase_line_id` to be passed through via `_prepare_phantom_move_values()`
