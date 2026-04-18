---
type: module
module: mrp_repair
tags: [odoo, odoo19, mrp, repair, manufacturing, stock, phantom-bom, mto]
created: 2026-04-11
updated: 2026-04-11
---

# Mrp Repairs (`mrp_repair`)

## Overview

| Property | Value |
|----------|-------|
| **Module** | `mrp_repair` |
| **Category** | Supply Chain/Inventory |
| **License** | LGPL-3 |
| **Edition** | Community (CE) |
| **Depends** | `repair`, `mrp` |
| **Author** | Odoo S.A. |
| **Auto-install** | `True` |

`mrp_repair` is a thin auto-install bridge module that integrates Manufacturing Orders (MRP) with Repair Orders. When both `repair` and `mrp` are installed, `mrp_repair` activates automatically, enabling:
1. **Phantom BOM explosion** within repair orders (kit/consumable products as repair parts are decomposed into component moves)
2. **MTO → MO procurement**: Repair part moves can trigger manufacturing orders via `make_to_order` procurement
3. **Bidirectional navigation** between repair orders and their linked manufacturing productions
4. **SN/lot traceability** unblocking: removing tracked components in repair does not block reusing those components in subsequent MOs

---

## File Structure

```
mrp_repair/
├── __init__.py
├── __manifest__.py          # depends: ['repair', 'mrp'], auto_install: True
├── models/
│   ├── __init__.py          # imports: repair, production, stock_move
│   ├── repair.py            # repair.order extensions + action_explode()
│   ├── production.py        # mrp.production extensions + repair_count
│   └── stock_move.py        # stock.move phantom prep + _prepare_phantom_line_vals
├── views/
│   ├── repair_views.xml    # Smart button "Manufacturing Orders" on repair order
│   └── production_views.xml  # Smart button "Repairs" on MO form
└── tests/
    ├── test_mrp_repair_flow.py  # MTO integration, kit explosion tests
    └── test_tracability.py       # SN traceability unblocking tests
```

---

## Architecture: How `repair` and `mrp` Connect

### Core Insight

The `mrp_repair` module does **not** create its own database tables. It adds behavior to two existing models:
- `repair.order` (from `repair`)
- `stock.move` (extended by `repair`, further extended by `mrp_repair`)
- `mrp.production` (from `mrp`)

The central mechanism is **`action_explode()`**, called on every `repair.order` create/write, which decomposes kit products into their BOM component moves. When those component products have `make_to_order` procurement rules, Odoo's standard procurement engine generates `mrp.production` records.

### Data Flow

```
repair.order (with kit product in move_ids)
    └→ action_explode() [on create/write]
            ├→ For each kit move: bom = mrp.bom._bom_find(product)
            │       └→ If phantom BOM found: explode → component moves
            └→ Replace kit move with component moves

Component move (with make_to_order rule)
    └→ _trigger_scheduler() [from repair stock_move create hook]
            └→ stock.rule procurement engine
                    └→ Creates mrp.production (if route=manufacture)

mrp.production (completed)
    └→ Move dest linked to repair via move_dest_ids
            └→ mrp.production.action_view_repair_orders() navigates back
```

---

## Model Extensions

### `repair.order` (from `repair`, further extended)

```python
# mrp_repair/models/repair.py
class RepairOrder(models.Model):
    _inherit = 'repair.order'

    production_count = fields.Integer(
        'Count of MOs generated',
        compute='_compute_production_count',
        groups='mrp.group_mrp_user',
    )
```

**`_compute_production_count`**:
```python
@api.depends('reference_ids.production_ids')
def _compute_production_count(self):
    for repair in self:
        repair.production_count = len(repair.reference_ids.production_ids)
```

The count traverses: `repair.reference_ids` (Many2many `stock.reference`) → `production_ids` (computed on `stock.reference`). This requires `stock.reference` to have a computed field linking back to `mrp.production` records.

### `mrp.production` (from `mrp`)

```python
# mrp_repair/models/production.py
class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    repair_count = fields.Integer(
        string='Count of source repairs',
        compute='_compute_repair_count',
        groups='stock.group_stock_user',
    )

    @api.depends('move_dest_ids.repair_id')
    def _compute_repair_count(self):
        for production in self:
            production.repair_count = len(production.move_dest_ids.repair_id)
```

**Key traversal path**: `mrp.production` → `move_dest_ids` (downstream stock moves) → `repair_id` (links to `repair.order`). This works because repair part moves created via procurement have `move_dest_ids` pointing back to the MO's consumption moves.

### `stock.move` (from `repair`, further extended)

```python
# mrp_repair/models/stock_move.py
class StockMove(models.Model):
    _inherit = 'stock.move'

    def _prepare_phantom_line_vals(self, bom_line, qty):
        self.ensure_one()
        product = bom_line.product_id
        return {
            'repair_id': self.repair_id.id,
            'repair_line_type': self.repair_line_type,
            'product_id': product.id,
            'price_unit': self.price_unit,
            'product_uom_qty': qty,
            'location_id': self.location_id.id,
            'location_dest_id': self.location_dest_id.id,
            'state': 'draft',
        }
```

This method overrides the base `mrp` implementation to carry `repair_id` and `repair_line_type` through the phantom explosion, ensuring component moves remain properly linked to the repair order.

---

## `action_explode()` — Phantom BOM Explosion

This is the central method that handles kit/consumable products added as repair parts.

```python
def action_explode(self):
    lines_to_unlink_ids = set()
    line_vals_list = []
    for op in self.move_ids:
        bom = self.env['mrp.bom'].sudo()._bom_find(
            op.product_id, company_id=op.company_id.id, bom_type='phantom'
        )[op.product_id]
        if not bom:
            continue
        factor = op.product_uom._compute_quantity(
            op.product_uom_qty, bom.product_uom_id
        ) / bom.product_qty
        _boms, lines = bom.sudo().explode(op.product_id, factor, picking_type=bom.picking_type_id)
        for bom_line, line_data in lines:
            if bom_line.product_id.type != 'service':
                line_vals_list.append(op._prepare_phantom_line_vals(bom_line, line_data['qty']))
        lines_to_unlink_ids.add(op.id)

    self.env['stock.move'].browse(lines_to_unlink_ids).sudo().unlink()
    if line_vals_list:
        self.env['stock.move'].create(line_vals_list)
```

### Trigger Points

```python
@api.model_create_multi
def create(self, vals_list):
    orders = super().create(vals_list)
    orders.action_explode()   # ← Explode on create
    return orders

def write(self, vals):
    res = super().write(vals)
    self.action_explode()     # ← Explode on write (e.g., adding kit as new part)
    return res
```

**Important**: `action_explode()` is called on every `write()`. This means adding a kit product to an existing confirmed repair triggers re-explosion. The method unlinks the kit move and replaces it with component moves.

### Phantom Explosion vs. MO Backflush

The `mrp` module's `_prepare_phantom_move_values()` is also overridden to propagate `repair_id`:

```python
def _prepare_phantom_move_values(self, bom_line, product_qty, quantity_done):
    vals = super()._prepare_phantom_move_values(bom_line, product_qty, quantity_done)
    if self.repair_id:
        vals['repair_id'] = self.repair_id.id
    return vals
```

This ensures that when the MO generates backflush moves (component consumption during MO done), those moves carry the `repair_id` link, enabling traceability and `_compute_repair_count` to work.

### BOM Type Handling

Only `bom_type='phantom'` BOMs are exploded. Other BOM types (`kit`, `normal`, `subassembly`) are not handled — they follow standard MRP procurement logic.

```python
bom_type='phantom'  # Only this type triggers repair explosion
# bom_type='normal' → creates MO procurement, no explosion
# bom_type='subassembly' → creates MO procurement, no explosion
```

---

## Smart Buttons and Navigation

### Repair Order → Manufacturing Orders

On `repair.order` form, a smart button shows `production_count` (number of linked MOs). Clicking it opens:

```python
def action_view_mrp_productions(self):
    self.ensure_one()
    production_order_ids = self.reference_ids.production_ids
    action = {
        'type': 'ir.actions.act_window',
        'res_model': 'mrp.production',
        'views': `False, 'form'`,
    }

    if self.production_count == 1:
        action['res_id'] = production_order_ids.id
    elif self.production_count > 1:
        action['name'] = _("Manufacturing Orders generated by %s", self.name)
        action['views'] = `False, 'list'`
        action['domain'] = [('id', 'in', production_order_ids.ids)]

    return action
```

### Manufacturing Order → Repair Orders

On `mrp.production` form, a smart button shows `repair_count`. Clicking it opens:

```python
def action_view_repair_orders(self):
    self.ensure_one()
    repair_ids = self.move_dest_ids.repair_id
    action = {
        'type': 'ir.actions.act_window',
        'res_model': 'repair.order',
        'views': `False, 'form'`,
    }

    if self.repair_count == 1:
        action['res_id'] = repair_ids.id
    elif self.repair_count > 1:
        action['name'] = _("Repair Source of %s", self.name)
        action['views'] = `False, 'list'`
        action['domain'] = [('id', 'in', repair_ids.ids)]

    return action
```

---

## Cross-Module Integration

### Procurement Chain: Repair → MRP

```
repair.order.move_ids (component with MTO route)
    └→ repair: stock_move.create()
            └→ _trigger_scheduler() [from repair stock_move hook]
                    └→ stock.rule._run() [procure_method='make_to_order']
                            └→ mrp.production.create()
                                    └→ move_dest_ids linked back to repair move
```

The `stock.reference` model acts as the linking record: when a repair move is confirmed, it is linked to `repair.reference_ids`, and the MO generated via procurement carries those references forward.

### Product Catalog Integration

When a repair order opens the Product Catalog to add parts:

```python
def _get_action_add_from_catalog_extra_context(self):
    bom = self.env['mrp.bom']._bom_find(
        self.product_id, company_id=self.company_id.id
    )[self.product_id]
    product_ids = [line.product_id.id for line in bom.bom_line_ids] if bom else []
    return {
        **super()._get_action_add_from_catalog_extra_context(),
        'catalog_bom_product_ids': product_ids,
        'search_default_bom_parts': bool(product_ids)
    }
```

This pre-populates the catalog with the product's BOM components, making it easier to add all needed parts at once.

---

## `sudo()` Usage and Security

`action_explode()` and its helper methods use `sudo()`:

```python
bom = self.env['mrp.bom'].sudo()._bom_find(op.product_id, ...)
_boms, lines = bom.sudo().explode(op.product_id, factor, ...)
self.env['stock.move'].browse(lines_to_unlink_ids).sudo().unlink()
```

**Rationale**: BOM data and product data are considered safe to read across companies in multi-company setups — BOMs are typically company-independent or filtered by `company_id`. The `sudo()` avoids ACL permission errors when the repair order user (stock group) does not have explicit read access to `mrp.bom` records.

**Security consideration**: The `sudo()` does NOT bypass company restrictions on the BOM search itself — `_bom_find()` respects `company_id` filtering. So a repair order in Company A cannot inadvertently explode BOMs from Company B.

---

## Test Coverage

### `test_mrp_repair_flow.py`

**`test_repair_with_manufacture_mto_link`**: Verifies that a repair order with a product using MTO + Manufacture routes correctly generates an MO, and that the MO is bidirectionally linked to the repair order.

```
1. Set product route: MTO + Manufacture (make_to_order)
2. Create repair order with 'add' move for that product
3. action_validate() → triggers procurement
4. Assert: mrp.production created, linked via move_dest_ids
5. Assert: repair.production_count = 1
6. Assert: production.repair_count = 1
```

**`test_adding_kit_parts_to_confirmed_repair`**: Verifies phantom BOM explosion works on confirmed repair orders.

```
1. Create confirmed repair (no moves yet)
2. Add kit product via stock.move.create() with repair_id
3. action_explode() decomposes kit into component moves
4. Assert: repair.move_ids contains only component moves (kit move unlinked)
5. Assert: component moves match BOM line products
```

### `test_tracability.py`

**`test_tracking_repair_production`**: Key test for SN unblocking. Creates an MO that consumes a tracked SN component, then creates a repair that removes the same SN from the finished product, then creates another MO using the same SN — which must succeed.

**`test_mo_with_used_sn_component`**: Tests the full cycle: produce → repair (recycle) → produce again. The recycled component must be available for reuse.

**`test_mo_with_used_sn_component_02`**: Tests: repair removed component → used in MO → MO unbuilt → used again in new MO. Ensures unbuild doesn't re-block the SN.

**`test_mo_with_unscrapped_tracked_component`**: Tests the "remove to scrap then move back to stock" workflow. After a repair sends a tracked component to scrap, a manual move can return it to stock, and it can then be used in an MO.

**`test_repair_with_consumable_kit`**: Tests that a consumable-type kit product (type='consu', not type='product') with a phantom BOM can be repaired end-to-end.

---

## Odoo 18 to 19 Changes

The `mrp_repair` module has remained structurally stable between Odoo 18 and Odoo 19. Key observations:

1. **`_prepare_phantom_line_vals` signature**: The method signature changed in Odoo 19 to accept `(self, bom_line, qty)` — previously it accepted `(self, bom_line, qty, data)`. The third `data` argument was dropped; the override in `mrp_repair` correctly uses the new signature.
2. **`action_explode()` implementation**: Unchanged between 18 and 19. The `bom.sudo().explode()` call and the `sudo().unlink()` pattern remains the same.
3. **`stock.reference` integration**: The `reference_ids` Many2many on `repair.order` is the primary link for referencing MOs from repairs. In earlier versions, this was done differently (or not at all). The `production_count` traversal through `reference_ids.production_ids` assumes `stock.reference` has a `production_ids` computed field pointing to `mrp.production`. This field is defined in the `stock` or `mrp` module (not in `mrp_repair` itself).
4. **`product.catalog.mixin` integration**: The `_get_action_add_from_catalog_extra_context()` method was likely added in Odoo 19 to support the new Product Catalog UI on repair orders, replacing older BOM-aware catalog integration.

---

## Performance Considerations

| Concern | Detail |
|---------|--------|
| **`sudo()` on every explode** | `action_explode()` calls `bom.sudo().explode()` and `unlink().sudo()`. For large repair orders with many kit products, this avoids ACL checks on BOM reads. Safe because BOMs are company-scoped |
| **Re-explosion on every write** | `action_explode()` is called on every `repair.order.write()`. If a repair has many component moves, this could cause redundant unlink+create cycles. Mitigation: the method only processes moves that have a phantom BOM — non-kit moves are skipped |
| **`_compute_repair_count` traversal** | Goes through `move_dest_ids.repair_id`. On MOs with many downstream moves, this could trigger N+1. The compute uses `@api.depends('move_dest_ids.repair_id')` so it only recomputes when downstream moves change |
| **BOM explosion with many components** | For kits with 20+ BOM lines, the `explode()` method creates that many new `stock.move` records synchronously. Consider async/cron for extremely large BOMs |

---

## Failure Mode Diagnostics

### Kit product not exploding

**Symptoms**: Adding a kit product to a repair order does not create component moves.

**Diagnosis**:
```
1. Is the product type 'consu' (consumable)?
   └→ Repair orders only accept consumable products
   └→ Kits with type='product' cannot be added directly

2. Does the product have a phantom BOM?
   └→ bom = mrp.bom._bom_find(product, bom_type='phantom')
   └→ If no phantom BOM found, action_explode() skips the product
   └→ Check: Manufacturing → Products → Bill of Materials for the kit
   └→ Verify: Type = "Kit (phantom)"

3. Is the BOM active and for the right company?
   └→ BOM has company_id filter in _bom_find
   └→ Check: BOM company matches repair order company
```

### MO not generated from repair

**Symptoms**: Repair order with a component product that has MTO+Manufacture routes, but no MO is created.

**Diagnosis**:
```
1. Is the route active?
   └→ MTO route must have active=True
   └→ Check: Inventory → Configuration → Routes → MTO

2. Is the repair move confirmed?
   └→ MO is created when _trigger_scheduler() is called
   └→ _trigger_scheduler() fires when move goes to 'confirmed' state
   └→ Is the move in 'confirmed' state? (check repair.move_ids.state)

3. Is there a manufacturing rule for the product's warehouse?
   └→ stock.rule with action='manufacture' and route_id=manufacture route
   └→ Check: Inventory → Configuration → Routes → Manufacture
   └→ Verify rule exists for the repair warehouse's picking type
```

### Smart button shows 0 despite MO being created

**Symptoms**: An MO exists that was created from a repair order, but `production_count` on the repair order shows 0.

**Diagnosis**:
```
1. Is the MO linked via move_dest_ids?
   └→ The MO's move_dest_ids must contain the repair's stock.move
   └→ Check: MO → Components → downstream move link

2. Is the repair linked via reference_ids?
   └→ production_count traverses reference_ids.production_ids
   └→ Is there a stock.reference record linking repair ↔ production?
   └→ Check: repair.reference_ids

3. Is the product route correctly configured?
   └→ MTO alone (without Manufacture route) creates procurement, not MO
   └→ Need BOTH MTO and Manufacture routes active
```

---

## Related Documentation
- [Modules/repair](Modules/repair.md) — Base repair module
- [Modules/Stock](Modules/Stock.md) — Locations, moves, stock rules, procurement
- [Modules/MRP](Modules/MRP.md) — Manufacturing orders, BOM, phantom explosion
- [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) — State machine and approval flows
- [Core/Fields](Core/Fields.md) — Field types: Many2one, One2many, Many2many, computed fields
- [Core/API](Core/API.md) — @api.depends, @api.model_create_multi, @api.depends context
