---
tags: [odoo, odoo17, module, mrp_subcontracting, subcontracting]
research_depth: medium
---

# MRP Subcontracting Module — Deep Reference

**Source:** `addons/mrp_subcontracting/models/`

## Overview

Manufacturing orders sent to external vendors (subcontractors) who receive components and return finished goods. Subcontracted MOs do not have workorders (the vendor does the work off-site). Components are tracked as they are shipped to and consumed at the subcontractor's location, and the finished product is received back into the warehouse.

## Key Concept: Subcontracting vs Regular Manufacturing

| Aspect | Regular MRP | Subcontracting |
|--------|-------------|----------------|
| Location | Own warehouse | Vendor's `property_stock_subcontractor` location |
| Components | Stored at own WH | Shipped to vendor then consumed |
| Finished goods | Produced in-house | Returned from vendor |
| Workorders | Yes | No (`_has_workorders` returns False) |
| BoM type | `normal` | `subcontract` |
| Cost | `standard_price` | Subcontracting cost on BoM |

## File Map

| File | Purpose |
|------|---------|
| `mrp_bom.py` | `type = 'subcontract'` on BoM, `subcontractor_ids` M2M |
| `mrp_production.py` | Subcontract MO extensions, component recording, portal access |
| `res_partner.py` | Subcontractor location, `is_subcontractor` compute |
| `stock_picking.py` | Subcontract picking flow, MO creation on receipt |
| `stock_move.py` | `is_subcontract` flag, BOM detection, component auto-record |
| `stock_move_line.py` | Serial number onchange for subcontract locations |
| `stock_location.py` | Subcontracting location flag |
| `product.py` | Route inclusion for subcontracting |

## Key Models

### mrp.bom (Extended)

```python
type = fields.Selection(selection_add=[('subcontract', 'Subcontracting')])
subcontractor_ids = fields.Many2many('res.partner', ...)
```

**Constraint:** Subcontract BoMs cannot have operations or by-products.

**Finding a subcontract BoM:**
```python
MrpBom._bom_subcontract_find(product, picking_type, company_id, bom_type='subcontract', subcontractor)
```

### mrp.production (Extended)

```python
subcontracting_has_been_recorded = fields.Boolean(copy=False)
subcontractor_id = fields.Many2one('res.partner')  # restricts portal access
bom_product_ids = fields.Many2many('product.product', compute=...)
incoming_picking = fields.Many2one(related='move_finished_ids.move_dest_ids.picking_id')
move_line_raw_ids = fields.One2many(...)  # inverse for portal editing
```

**Portal-user writeable fields:** `move_line_raw_ids`, `lot_producing_id`, `subcontracting_has_been_recorded`, `qty_producing`, `product_qty`

**`_get_subcontract_move()`** — returns the `stock.move` (finished move, `is_subcontract=True`) whose `move_dest_ids` links back to the subcontract receipt.

**`_has_workorders()`** — returns `False` when `subcontractor_id` is set, because the vendor performs the work.

**`subcontracting_record_component()`** — key action: marks `move_raw_ids.picked = True`, calls `_update_finished_move()` to sync move lines on the subcontract receipt picking, then sets `subcontracting_has_been_recorded = True`. Handles backorders for quantity discrepancies.

**`_subcontracting_filter_to_done()`** — filters MOs where `subcontracting_has_been_recorded == True` and state is not done/cancel. Used by `stock.picking._action_done()` to auto-complete MOs.

**`_subcontract_sanity_check()`** — validates serial/lot tracking on both the finished product and all tracked component move lines before marking done.

### stock.picking (Extended)

**`_is_subcontract()`** — `picking_type_id.code == 'incoming'` AND any move has `is_subcontract == True`.

**`_subcontracted_produce(subcontract_details)`** — called during `_action_confirm` on incoming pickings. For each subcontract move, creates a procurement group and an MO via `_prepare_subcontract_mo_vals()`, then calls `action_confirm()` and `action_assign()`. Links the finished move's `move_dest_ids` to the receipt move.

**`_prepare_subcontract_mo_vals(move, bom)`** — builds MO vals:
- `location_src_id` / `location_dest_id` = subcontractor's `property_stock_subcontractor` location (or company fallback)
- `subcontractor_id` = `picking_id.partner_id.commercial_partner_id`
- `picking_ids` = receipt picking
- `date_start` = `move.date - relativedelta(days=bom.produce_delay)`

**`action_record_components()`** — opens the produce wizard for the subcontract MO from within the picking.

**`_action_done()` override** — handles the auto-completion logic: if MOs were not manually recorded, splits and records them based on move line quantities; then calls `button_mark_done()` on filtered productions.

### res.partner (Extended)

```python
property_stock_subcontractor = fields.Many2one('stock.location')  # company_dependent
is_subcontractor = fields.Boolean(compute='_compute_is_subcontractor', search='_search_is_subcontractor')
bom_ids = fields.Many2many('mrp.bom', compute=...)
production_ids = fields.Many2many('mrp.production', compute=...)
picking_ids = fields.Many2many('stock.picking', compute=...)
```

**`_compute_is_subcontractor()`** — `True` if user is portal and partner appears in any subcontract BoM's `subcontractor_ids`. Used to grant sudo access to their own records.

### stock.move (Extended)

```python
is_subcontract = fields.Boolean('The move is a subcontract receipt')
```

**`_action_confirm` override** — detects subcontract moves by checking for a subcontract BoM. Sets `is_subcontract = True`, `location_id = subcontracting_location`. Then calls `_subcontracted_produce()` to create the MO.

**`_subcontrating_should_be_record()`** — returns productions that are unrecorded AND have tracked components (mandatory wizard).

**`_subcontrating_can_be_record()`** — returns productions that are unrecorded AND have non-strict consumption (optional wizard).

**`_auto_record_components(qty)`** — auto-fills the component wizard when the done quantity is set directly on the move line (skips the manual wizard step for flexible/consumable BoMs).

**`_reduce_subcontract_order_qty(quantity_to_remove)`** — called when done qty is reduced; cancels or adjusts MOs to match.

**`_is_subcontract_return()`** — `True` if this is a return move of a subcontracted product back to the subcontractor.

## Subcontracting Flow (Full Sequence)

```
1. Purchase Order confirmed for subcontracted product
   → creates stock.picking (receipt, type=incoming)
2. Receipt Move._action_confirm():
   → detects subcontract BoM via _get_subcontract_bom()
   → sets is_subcontract=True, location_id = subcontractor location
   → calls _subcontracted_produce() → creates mrp.production
3. Components shipped TO subcontractor:
   → separate outgoing picking (covered by mrp_subcontracting_purchase)
4. Subcontractor manufactures
5. Incoming receipt validated:
   → action_record_components() or _action_done() auto-record
   → _update_finished_move() syncs finished move lines
   → MO.button_mark_done() triggered
6. Finished goods quants created at warehouse
7. Component costs tracked via subcontractor's account_move
```

## BoM for Subcontracting

On `mrp.bom`:
```python
type = 'subcontract'
subcontractor_ids = [(6, 0, [vendor_id])]
bom_line_ids = [
    (0, 0, {'product_id': component1, 'product_qty': 1}),
    (0, 0, {'product_id': component2, 'product_qty': 2}),
]
# NO operations (forbidden)
# NO by-products (forbidden)
```

## See Also

- [Modules/mrp](mrp.md) — mrp.production, BoM types
- [Modules/purchase](purchase.md) — PO creates the incoming receipt
- [Modules/stock](stock.md) — stock.picking, stock.location
- [Modules/stock_account](stock_account.md) — subcontracting cost posting
