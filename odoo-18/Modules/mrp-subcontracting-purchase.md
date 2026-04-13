---
Module: mrp_subcontracting_purchase
Version: Odoo 18
Type: Integration
Tags: #mrp #purchase #subcontracting #procurement #bridge
Related: [Modules/MRP Subcontracting](Modules/MRP-Subcontracting.md), [Modules/Purchase](Modules/Purchase.md), [Modules/Stock](Modules/Stock.md)
---

# mrp_subcontracting_purchase — Subcontracting Purchase Integration

> **Odoo path:** `addons/mrp_subcontracting_purchase/`
> **Depends:** `mrp_subcontracting`, `purchase_mrp`
> **License:** LGPL-3
> **Auto-install:** True (bridge module — auto-installed with its dependencies)

## Overview

The `mrp_subcontracting_purchase` module is a **bridge integration** between the Purchase and Subcontracting modules. It adds smart-button navigation between Purchase Orders and Subcontracting records, computes subcontracting-aware lead times in procurement rules, and extends stock valuation to account for subcontracted product component costs. It does not introduce new core models but adds cross-module links, computed fields, and override logic to existing models.

---

## Models Extended

### `purchase.order` — Extended

Added fields and methods to link a Purchase Order to its subcontracting resupply pickings and source manufacturing orders.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `subcontracting_resupply_picking_count` | Integer | Count of subcontracting resupply pickings; computed via `_compute_subcontracting_resupply_picking_count` |

#### Methods Added / Overridden

| Method | Description |
|--------|-------------|
| `_compute_subcontracting_resupply_picking_count()` | `count(_get_subcontracting_resupplies())` |
| `action_view_subcontracting_resupply()` | Opens list/form of resupply pickings for this PO |
| `_get_subcontracting_resupplies()` | Returns `stock.picking` records: moves that are subcontracted (`is_subcontract=True`) → their `move_orig_ids.production_id` → those MOs' `picking_ids` (resupply ships) |
| `_get_mrp_productions(**kwargs)` | Extends parent to filter out archived picking types from linked MO domain |

---

### `stock.picking` — Extended

Added fields and methods to link a stock picking (receipt or internal) back to its source subcontracting Purchase Order.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `subcontracting_source_purchase_count` | Integer | Count of subcontracting PO sources for this picking |

#### Methods Added / Overridden

| Method | Description |
|--------|-------------|
| `_compute_subcontracting_source_purchase_count()` | `len(_get_subcontracting_source_purchase())` |
| `action_view_subcontracting_source_purchase()` | Opens PO form/list filtered to source POs |
| `_get_subcontracting_source_purchase()` | Traverses: `move_ids.move_dest_ids.raw_material_production_id.move_finished_ids.move_dest_ids` where `is_subcontract=True` → returns `purchase_line_id.order_id` |

#### Traversal Logic for Source PO

```
picking.move_ids                          # moves on this picking
  .move_dest_ids                          # dest moves (receipt moves)
  .raw_material_production_id             # MO that consumed these components
  .move_finished_ids                      # finished product moves of that MO
  .move_dest_ids                          # subcontract receipt moves (is_subcontract=True)
  .purchase_line_id.order_id              # the PO line → PO that triggered subcontracting
```

---

### `stock.rule` — Extended

Overrides `_get_lead_days()` to compute subcontracting-aware lead times for the `buy` procurement rule when the product is subcontracted.

#### `_get_lead_days` Override

**When called for a `buy` rule where the seller is a subcontractor:**

The method detects a subcontracting scenario by calling `mrp.bom._bom_subcontract_find()` with `bom_type='subcontract'` and the vendor's partner as subcontractor.

**Lead time formula for subcontracting:**

```
delays = super()._get_lead_days(product)  # non-buy rules
extra_delays = super()._get_lead_days(product)  # buy rule with bypass context

if seller.delay >= bom.produce_delay + bom.days_to_prepare_mo:
    # Vendor lead time dominates
    total_delay += seller.delay
    purchase_delay += seller.delay
    delay_description += (Vendor Lead Time, +N days)
else:
    # Manufacturing lead time dominates
    total_delay += bom.produce_delay
    purchase_delay += bom.produce_delay
    delay_description += (Manufacturing Lead Time, +N days)
    # Add days to prepare MO
    total_delay += bom.days_to_prepare_mo
    purchase_delay += bom.days_to_prepare_mo
    delay_description += (Days to Supply Components, +N days)

# Plus: Days to Purchase + Purchase security lead time (from extra_delays)
```

**Key context flags used:**
- `bypass_delay_description`: skips building delay description strings
- `ignore_vendor_lead_time=True`: do not include vendor lead time in extra delays (we handle it ourselves)
- `global_visibility_days=0`: ignore global lead time for the extra delays computation

---

### `stock.move` — Extended

#### Methods

| Method | Description |
|--------|-------------|
| `_is_purchase_return()` | Extended: returns `True` if `super()` is True OR `_is_subcontract_return()` is True. Allows subcontract return moves to be treated as purchase returns for return valuation purposes. |

---

### `account.move.line` — Extended

#### `_get_price_unit_val_dif_and_relevant_qty`

When a PO line delivers a subcontracted product with standard cost method:

1. Gets the subcontracted production via `purchase_line_id.move_ids._get_subcontract_production()`
2. Sums the component SVL values: `sum(move_raw_ids.stock_valuation_layer_ids.mapped('value'))`
3. Gets quantity from done MOs: `sum(product_uom_id._compute_quantity(mo.qty_producing, ...))`
4. Adjusts `price_unit_val_dif`: adds `components_cost / qty` to spread component cost across finished units

This ensures that when a vendor invoice is posted, the standard price variance accounts for the cost of components consumed during subcontracting.

#### `_get_valued_in_moves`

Extends the parent result with:
```python
res |= res.filtered(lambda m: m.is_subcontract).move_orig_ids
```

For subcontracted moves, the valued-in-moves includes the MO's finished move (the original move), not just the receipt move. This is needed for accurate cost layering on subcontracted products.

---

### `stock.valuation.layer` — Extended

#### `_get_layer_price_unit`

For subcontracted products:
- Finds `production_id` from `stock_move_id.production_id`
- If `production.subcontractor_id` and `production.state == 'done'`:
  - Iterates `production.move_raw_ids`
  - For each raw move, divides its SVL total value by `production.product_uom_qty` to get per-unit component cost
  - Subtracts total component cost per unit from the subcontracted product's layer price

```python
# Example: subcontracted product has layer price P (from PO vendor price)
# Component costs C = sum(|raw_move_svl.value| / mo_qty) for all raw moves
# layer_price_unit = P - C
```

This gives the **subcontracting service cost** (加工费), separating it from the component material cost.

---

## Purchase-MRP Bridge (`purchase_mrp` module)

> **Odoo path:** `addons/purchase_mrp/`
> **Full model reference here for completeness.**

The `purchase_mrp` module (not just the bridge) provides the primary PO↔MO linking:

### `purchase.order` (Extension)

| Field | Description |
|-------|-------------|
| `mrp_production_count` | Count of MOs linked to this PO |

`_get_mrp_productions()` logic:
```python
# Links via stock move chains
linked_mo = order_line.move_dest_ids.group_id.mrp_production_ids  # via procurement group
             | stock.move(...)._rollup_move_dests().group_id.mrp_production_ids  # via nested moves
group_mo = order_line.group_id.mrp_production_ids  # direct group link
return linked_mo | group_mo
```

`action_view_mrp_productions()`: Opens MO list/form for PO's linked manufacturing orders.

---

## Complete Subcontracting PO → MO → Flow

### Step-by-Step

1. **Product configured** with BoM type = `subcontract`, partner = subcontractor vendor
2. **Procurement triggered** (MO or direct need) → `stock.rule` with `action='buy'` fires
3. **StockRule._get_lead_days()** (overridden by `mrp_subcontracting_purchase`): computes combined lead time = max(vendor lead time, manufacturing lead time + DTPMO) + purchase security
4. **PO created** with vendor, planned date accounting for lead times
5. **PO confirmed** → receipt picking created with `is_subcontract=True` moves
6. **Receipt picking received** → triggers MO creation (via `mrp.subcontracting`):
   - MO `bom_id` = the subcontract BoM
   - MO `subcontractor_id` = vendor partner
   - MO `picking_type_id` = subcontracting receipt type
7. **Subcontracting Resupply**: `mrp_subcontracting` creates pickings to ship components to subcontractor (marked `is_subcontract`)
8. **MRP Subcontracting Purchase bridge**: `purchase.order.subcontracting_resupply_picking_count` tracks the resupply pickings; `_get_subcontracting_resupplies()` traverses from PO → subcontract moves → MOs → pickings
9. **MO done** → subcontracted receipt move confirms; SVL is created for the finished product
10. **SVL layer price** (`stock.valuation.layer._get_layer_price_unit`): component costs are deducted from the layer price, isolating the subcontracting service fee
11. **Invoice posting** (`account.move.line._get_price_unit_val_dif_and_relevant_qty`): PO line invoice variance is adjusted to include component costs

---

## L4: Material Supply to Subcontractor

### Resupply Flow

The subcontracting material flow is orchestrated by `mrp_subcontracting`:

1. When the subcontracted MO is confirmed, component moves (`move_raw_ids`) are created:
   - Source: company's warehouse location (or stock)
   - Destination: subcontractor's location (subcontracting location)
2. `stock.picking` of type `subcontracting` is created to ship components to subcontractor
3. This picking is the **resupply picking** — tracked via `subcontracting_resupply_picking_count` on the PO
4. The PO's `_get_subcontracting_resupplies()` method walks: PO lines → subcontract moves → MOs → picking_ids

### Stock Rule for Resupply

`mrp_subcontracting/models/stock_rule.py` has a minimal override: `stock.rule._push_prepare_move_copy_values()` sets `is_subcontract = False` on push-generated moves to prevent loop propagation.

### PO Line ↔ MO Link

The PO line is linked to the MO via the stock move chain:
- PO line creates a stock move (procurement)
- That move's `move_dest_ids` leads to the MO's raw material move
- The MO's finished move has `is_subcontract=True` and `purchase_line_id` pointing back to the PO line

```
purchase.order.line
  → stock.move (procurement)
  → stock.move.move_dest_ids (raw material for MO)
  → mrp.production (MO)
  → mrp.production.move_finished_ids (finished product)
  → stock.move (receipt, is_subcontract=True, purchase_line_id=PO line)
```

---

## L4: How PO Line → MO → Subcontracting Flow Works

### Procurement Chain

```
Replenish (MO or manual)
  → stock.rule (action='buy')
  → _get_lead_days() — sees subcontract BoM → compute combined lead time
  → purchase.order.line.create()
  → purchase.order (PO) confirmed
  → stock.picking (receipt, moves is_subcontract=True)
  → mrp_subcontracting.action_unreserve_subcontracting_moves()
    → creates/updates mrp.production (subcontracted)
  → mrp.production.move_raw_ids (component moves, source = company's warehouse)
  → stock.picking (resupply to subcontractor)
```

### Backorder in Subcontracting

When a subcontracted receipt is partially received:
1. The MO generates a backorder MO
2. The backorder MO's receipt move links to the original PO line
3. `stock.valuation.layer._get_layer_price_unit` on the backorder moves still deducts component costs (which may differ in quantity from the original MO)

### Lead Time Computation (Subcontracting-Specific)

The `_get_lead_days` override in `stock.rule` is critical because a simple vendor lead time would not account for:
- Time to manufacture the subcontracted product (if longer than vendor lead time)
- Days to prepare the MO (DTPMO) for component sourcing
- The fact that component lead times are internal (not purchase delays)

```
subcontracting_delay = max(
    vendor_lead_time,
    bom.produce_delay + bom.days_to_prepare_mo
) + purchase_delay_days + security_lead_time
```

---

## File Map

| File | Models |
|------|--------|
| `models/purchase_order.py` | `purchase.order` (ext) |
| `models/stock_picking.py` | `stock.picking` (ext) |
| `models/stock_rule.py` | `stock.rule` (ext — `_get_lead_days`) |
| `models/stock_move.py` | `stock.move` (ext — `_is_purchase_return`) |
| `models/account_move_line.py` | `account.move.line` (ext) |
| `models/stock_valuation_layer.py` | `stock.valuation.layer` (ext) |