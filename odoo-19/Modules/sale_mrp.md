---
type: module
module: sale_mrp
tags: [odoo, odoo19, sale, mrp, manufacturing, kit, bom, phantom, cogs, multi_step]
created: 2026-04-06
updated: 2026-04-11
---

# Sale MRP — L4 Documentation

## Overview

| Property | Value |
|----------|-------|
| **Name** | Sales and MRP Management |
| **Technical** | `sale_mrp` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Module Path** | `~/odoo/odoo19/odoo/addons/sale_mrp/` |
| **Odoo Version** | 19 CE |
| **Auto-install** | `True` (installed automatically when `mrp` + `sale_stock` present) |

---

## L1 — Complete Module Inventory

### File Structure

```
sale_mrp/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── account_move.py          # account.move.line COGS override
│   ├── mrp_bom.py               # mrp.bom phantom protection
│   ├── mrp_production.py        # mrp.production SO link
│   ├── sale_order.py           # sale.order MO link
│   ├── sale_order_line.py       # sale.order.line kit delivery logic
│   ├── stock_move.py            # stock.move kit price override
│   ├── stock_move_line.py       # stock.move.line kit sale_price
│   └── stock_rule.py           # stock.rule MO/bom_line propagation
├── views/
│   ├── mrp_production_views.xml # Smart button on MO form
│   ├── sale_order_views.xml     # Smart button on SO form
│   └── sale_portal_templates.xml # Portal MO display
├── security/
│   └── ir.model.access.csv
└── tests/
    ├── test_multistep_manufacturing.py
    ├── test_sale_mrp_anglo_saxon_valuation.py
    ├── test_sale_mrp_flow.py
    ├── test_sale_mrp_kit_bom.py
    ├── test_sale_mrp_lead_time.py
    ├── test_sale_mrp_procurement.py
    └── test_sale_mrp_report.py
```

### All Extended Models

| Model | File | Inheritance Type | Role |
|-------|------|-----------------|------|
| `sale.order` | `models/sale_order.py` | `_inherit` | Track linked MOs |
| `sale.order.line` | `models/sale_order_line.py` | `_inherit` | Kit delivery qty, BOM component qty |
| `mrp.production` | `models/mrp_production.py` | `_inherit` | Track origin SOL via `sale_line_id` |
| `mrp.bom` | `models/mrp_bom.py` | `_inherit` | Block phantom BoM deactivation |
| `stock.rule` | `models/stock_rule.py` | `_inherit` | Propagate `sale_line_id` into MO and component moves |
| `account.move.line` | `models/account_move.py` | `_inherit` | COGS for kit products via component costs |
| `stock.move` | `models/stock_move.py` | `_inherit` | Kit price unit for component moves |
| `stock.move.line` | `models/stock_move_line.py` | `_inherit` | Sale price for kit component lines |

### All Fields Added by sale_mrp

#### `sale.order` (extended)

| Field | Type | Stored | Groups | Description |
|-------|------|--------|--------|-------------|
| `mrp_production_count` | `Integer` | No | `mrp.group_mrp_user` | Count of linked first-level MOs |
| `mrp_production_ids` | `Many2many` | No | `mrp.group_mrp_user` | Recordset of linked MOs |

#### `mrp.production` (extended)

| Field | Type | Stored | Groups | Description |
|-------|------|--------|--------|-------------|
| `sale_line_id` | `Many2one` | Yes | — | Direct origin `sale.order.line` |
| `sale_order_count` | `Integer` | No | `sales_team.group_sale_salesman` | Count of unique SOs via `reference_ids` OR `sale_line_id` |

### All Methods Added/Overridden

| Model | Method | Location | Signature |
|-------|--------|----------|-----------|
| `sale.order` | `_compute_mrp_production_ids` | `sale_order.py:21` | `@api.depends('stock_reference_ids.production_ids')` |
| `sale.order` | `action_view_mrp_production` | `sale_order.py:28` | `self → dict` |
| `sale.order.line` | `_compute_qty_to_deliver` | `sale_order_line.py:12` | `@api.depends(...)` |
| `sale.order.line` | `_prepare_qty_delivered` | `sale_order_line.py:33` | `self → dict` |
| `sale.order.line` | `compute_uom_qty` | `sale_order_line.py:91` | `(new_qty, stock_move, rounding=True) → float` |
| `sale.order.line` | `_get_bom_component_qty` | `sale_order_line.py:97` | `(bom) → dict` |
| `sale.order.line` | `_get_incoming_outgoing_moves_filter` | `sale_order_line.py:120` | `@api.model → dict` |
| `sale.order.line` | `_get_qty_procurement` | `sale_order_line.py:154` | `(previous_product_uom_qty=False) → float` |
| `mrp.production` | `_compute_sale_order_count` | `mrp_production.py:17` | `@api.depends(...)` |
| `mrp.production` | `action_view_sale_orders` | `mrp_production.py:21` | `self → dict` |
| `mrp.production` | `action_confirm` | `mrp_production.py:41` | `self → res` |
| `mrp.bom` | `write` | `mrp_bom.py:11` | `(vals) → bool` |
| `mrp.bom` | `unlink` | `mrp_bom.py:16` | `self → bool` |
| `mrp.bom` | `_ensure_bom_is_free` | `mrp_bom.py:20` | `self → None` |
| `stock.rule` | `_prepare_mo_vals` | `stock_rule.py:7` | `(product_id, product_qty, product_uom, location_dest_id, name, origin, company_id, values, bom) → dict` |
| `stock.rule` | `_get_stock_move_values` | `stock_rule.py:13` | `(product_id, product_qty, product_uom, location_dest_id, name, origin, company_id, values) → dict` |
| `account.move.line` | `_get_cogs_value` | `account_move.py:9` | `self → float` |
| `stock.move` | `_get_price_unit` | `stock_move.py:9` | `self → float` |
| `stock.move.line` | `_compute_sale_price` | `stock_move_line.py:9` | `self → None` |

---

## L2 — Field Types, Defaults, Constraints, Compute Logic

### `sale.order` Fields

**`mrp_production_ids`** — `Many2many('mrp.production')`
- **Not stored**: computed on-the-fly via `_compute_mrp_production_ids`
- **Access**: `mrp.group_mrp_user`
- **No default**, no domain, no `ondelete`

**`mrp_production_count`** — `Integer`
- **Not stored**: count of `mrp_production_ids`
- **Access**: `mrp.group_mrp_user`

#### `_compute_mrp_production_ids()` — L2 Detail

```python
@api.depends('stock_reference_ids.production_ids')
def _compute_mrp_production_ids(self):
    for sale in self:
        mos = sale.stock_reference_ids.production_ids
        sale.mrp_production_ids = mos.filtered(
            lambda mo: not mo.production_group_id.parent_ids
            and mo.state != 'cancel'
        )
        sale.mrp_production_count = len(sale.mrp_production_ids)
```

**Dependencies**: `stock_reference_ids.production_ids`
- `stock_reference_ids` is a `stock.reference` one2many on `sale.order` — it links the SO to its procurement group (set by `sale_stock`)
- `production_ids` is a `mrp.production` one2many on `stock.reference`

**Filter logic**:
- `not mo.production_group_id.parent_ids` — selects only **root-level MOs** (first MO created directly from the SO). Sub-assembly MOs (created from another MO) have a `production_group_id.parent_id` pointing to the parent MO's group and are excluded. This prevents the SO smart button from showing every nested MO in a multi-level kit structure.
- `mo.state != 'cancel'` — excludes cancelled MOs
- No `active` filter — includes archived MOs

**`action_view_mrp_production()`** — Smart button action:
- 1 MO: opens `form` view directly on that MO
- N MOs: opens `list,form` view with domain `[('id', 'in', sale.mrp_production_ids.ids)]`
- Label: `"Manufacturing Orders Generated by {sale.name}"`

---

### `sale.order.line` Fields

No new fields added. This model override only adds methods.

#### `_compute_qty_to_deliver()` — L2 Detail

```python
@api.depends('product_uom_qty', 'qty_delivered', 'product_id', 'state')
def _compute_qty_to_deliver(self):
    super()._compute_qty_to_deliver()
    for line in self:
        boms = self.env['mrp.bom']
        if line.state == 'sale':
            boms = line.move_ids.mapped('bom_line_id.bom_id')
        elif line.state in ['draft', 'sent'] and line.product_id:
            boms = boms._bom_find(line.product_id,
                                   company_id=line.company_id.id,
                                   bom_type='phantom')[line.product_id]
        relevant_bom = boms.filtered(
            lambda b: b.type == 'phantom'
            and (b.product_id == line.product_id
                 or (b.product_tmpl_id == line.product_id.product_tmpl_id
                     and not b.product_id))
        )
        if relevant_bom:
            line.display_qty_widget = False
            continue
        if line.state == 'draft' and line.product_type == 'consu':
            components = line.product_id.get_components()
            if components and components != [line.product_id.id]:
                line.display_qty_widget = True
```

**Decision tree**:
1. If confirmed (`state == 'sale'`): find phantom BoMs from existing stock moves via `bom_line_id.bom_id`
2. If draft/sent: do a `_bom_find` lookup by product for `type='phantom'`
3. If phantom BoM exists for this product: **hide** inventory forecast widget (`display_qty_widget = False`)
4. If `consu` product with sub-components: **show** widget even in draft

**Why**: Phantom BoM kits cannot use the standard "forecast" inventory widget because the kit is not a real storable product in stock — it is exploded into components at the time of delivery. The widget would show zero stock for the kit itself, which is misleading.

#### `_prepare_qty_delivered()` — L2 Detail

```python
def _prepare_qty_delivered(self):
    delivered_qties = super()._prepare_qty_delivered()
    for order_line in self:
        if order_line.qty_delivered_method == 'stock_move':
            boms = order_line.move_ids.filtered(
                lambda m: m.state != 'cancel'
            ).bom_line_id.bom_id
            dropship = any(m._is_dropshipped() for m in order_line.move_ids)
            relevant_bom = boms.filtered(
                lambda b: b.type == 'phantom'
                and (b.product_id == order_line.product_id
                     or (b.product_tmpl_id == order_line.product_id.product_tmpl_id
                         and not b.product_id))
            )
            if not relevant_bom:
                relevant_bom = boms._bom_find(order_line.product_id,
                    company_id=order_line.company_id.id,
                    bom_type='phantom')[order_line.product_id]
            if relevant_bom:
                if dropship:
                    moves = order_line.move_ids.filtered(lambda m: m.state != 'cancel')
                    if any((m.location_dest_id.usage == 'customer' and m.state != 'done')
                           or (m.location_dest_id.usage != 'customer'
                           and m.state == 'done'
                           and float_compare(m.quantity, ..., precision_rounding=m.product_uom.rounding) > 0)
                           for m in moves) or not moves:
                        delivered_qties[order_line] = 0
                    else:
                        delivered_qties[order_line] = order_line.product_uom_qty
                    continue
                moves = order_line.move_ids.filtered(
                    lambda m: m.state == 'done'
                    and m.location_dest_usage != 'inventory'
                )
                filters = {
                    'incoming_moves': lambda m: m._is_outgoing() and
                        (not m.origin_returned_move_id or
                         (m.origin_returned_move_id and m.to_refund)),
                    'outgoing_moves': lambda m: m._is_incoming() and m.to_refund,
                }
                order_qty = order_line.product_uom_id._compute_quantity(
                    order_line.product_uom_qty, relevant_bom.product_uom_id)
                qty_delivered = moves._compute_kit_quantities(
                    order_line.product_id, order_qty, relevant_bom, filters)
                delivered_qties[order_line] += relevant_bom.product_uom_id._compute_quantity(
                    qty_delivered, order_line.product_uom_id)
            elif boms:  # Multi-level kit fallback
                if all(m.state == 'done' and m.location_dest_id.usage == 'customer'
                       for m in order_line.move_ids):
                    delivered_qties[order_line] = order_line.product_uom_qty
                else:
                    delivered_qties[order_line] = 0.0
    return delivered_qties
```

**Kit delivery quantity algorithm** (non-dropship):
1. Collect all non-cancelled stock moves from the SOL
2. Extract their `bom_line_id.bom_id` to find phantom BoMs
3. Filter to the relevant phantom BoM matching the sold product (either by `product_id` or by template without variant)
4. Get `done` moves where `location_dest_usage != 'inventory'` (excludes internal inventory adjustments)
5. Call `moves._compute_kit_quantities(product, order_qty, bom, filters)` — this explodes component moves back to kit units using the BOM ratio
6. Convert from BOM UoM back to the SOL's product UoM

**Dropship exception**: Kits sold as dropship (component shipped directly from vendor to customer) are all-or-nothing: all dropship component moves must reach `done` state before any quantity is considered delivered.

**Multi-level kit fallback**: When a kit's components include another kit (nested phantom BOMs), `_bom_find` may not find a direct phantom BOM match. In that case, if ALL component moves are done and destined for the customer, the full SOL quantity is marked as delivered.

#### `_get_bom_component_qty()` — L2 Detail

```python
def _get_bom_component_qty(self, bom):
    bom_quantity = self.product_id.uom_id._compute_quantity(1, bom.product_uom_id,
                                                          rounding_method='HALF-UP')
    boms, lines = bom.explode(self.product_id, bom_quantity)
    components = {}
    for line, line_data in lines:
        product = line.product_id.id
        uom = line.product_uom_id
        qty = line_data['qty']
        if components.get(product, False):
            if uom.id != components[product]['uom']:
                qty = uom._compute_quantity(qty,
                    self.env['uom.uom'].browse(components[product]['uom']))
            components[product]['qty'] += qty
        else:
            to_uom = self.env['product.product'].browse(product).uom_id
            if uom.id != to_uom.id:
                qty = uom._compute_quantity(qty, to_uom)
            components[product] = {'qty': qty, 'uom': to_uom.id}
    return components
```

Returns: `{product_id: {'qty': decimal_float, 'uom': uom_id}}`

**Normalization**: All quantities are converted to the product's **base UoM** (not the BOM line UoM). This is critical for `_get_cogs_value()` which sums `component_qty * component_cost` — the quantities must all be in the same UoM for correct arithmetic.

#### `_get_incoming_outgoing_moves_filter()` — L2 Detail

Returns `incoming_moves` and `outgoing_moves` lambdas used by `_compute_kit_quantities`.

Key complexity: handles multiple triggering rules (one per warehouse) and phantom BOM sub-moves:
- Iterates moves sorted by ID
- Tracks `seen_bom_id` to identify when a move belongs to a phantom BOM sub-kit
- Tracks `seen_wh_ids` to group by warehouse
- `incoming_moves`: outgoing moves (from warehouse perspective) linked to the triggering rule, going to customer, with no return or marked `to_refund`
- `outgoing_moves`: incoming moves from customer that are returns (`to_refund=True`)

#### `compute_uom_qty()` — L2 Detail

```python
def compute_uom_qty(self, new_qty, stock_move, rounding=True):
    if stock_move.bom_line_id:
        return new_qty * stock_move.bom_line_id.product_qty
    return super().compute_uom_qty(new_qty, stock_move, rounding)
```

Called when reserving stock. For a component move linked to a BOM line, the reserved quantity equals `new_qty * bom_line.product_qty`. For example, if the kit SOL has `product_uom_qty=10` and the BOM has `product_qty=2` per kit, the component move reserves `10 * 2 = 20` units.

#### `_get_qty_procurement()` — L2 Detail

Overrides the standard procurement quantity calculation for kit products when the SO quantity changes after confirmation. Called by `sale.order.line._update_move_quantity()` when the user changes the quantity on a confirmed SOL. Uses the same kit-explosion logic as `_prepare_qty_delivered`.

---

### `mrp.production` Fields

**`sale_line_id`** — `Many2one('sale.order.line')`
- **Stored**: `True`
- **No groups restriction** — visible to all (ACL on `mrp.production` controls write access)
- Populated by `stock.rule._prepare_mo_vals` during MO creation
- Propagated to finished move in `action_confirm()`

**`sale_order_count`** — `Integer`
- **Not stored**
- **Groups**: `sales_team.group_sale_salesman`
- Computed as union of `reference_ids.sale_ids` (via procurement group) and `sale_line_id.order_id` (direct link)

#### `action_confirm()` Override — L2 Detail

```python
def action_confirm(self):
    res = super().action_confirm()
    for production in self:
        if production.sale_line_id:
            production.move_finished_ids.filtered(
                lambda m: m.product_id == production.product_id
            ).sale_line_id = production.sale_line_id
    return res
```

**Purpose**: Propagates `sale_line_id` from the MO record to the **finished stock move** (the move that produces the kit product and is consumed into the delivery order).

**Why this matters**: When `sale_stock` creates a delivery order from the MO's `move_finished_ids`, those moves need `sale_line_id` set so that:
1. The delivery is linked to the SOL for `qty_delivered` tracking
2. The delivery can be invoiced correctly
3. The portal shows the delivery under the correct SO

The finished move must be the one where `product_id == production.product_id` (the kit product itself, not a byproduct or co-product).

---

### `mrp.bom` Extension — L2 Detail

#### `_ensure_bom_is_free()` — L2 Detail

```python
def _ensure_bom_is_free(self):
    product_ids = []
    for bom in self:
        if not bom.active or bom.type != 'phantom':
            continue
        product_ids += bom.product_id.ids or \
                      bom.product_tmpl_id.product_variant_ids.ids
    if not product_ids:
        return
    lines = self.env['sale.order.line'].sudo().search([
        ('state', '=', 'sale'),
        ('invoice_status', 'in', ('no', 'to invoice')),
        ('product_id', 'in', product_ids),
        ('move_ids.state', '!=', 'cancel'),
    ])
    if lines:
        product_names = ', '.join(lines.product_id.mapped('display_name'))
        raise UserError(_('As long as there are some sale order lines that must be '
                          'delivered/invoiced and are related to these bills of materials, '
                          'you can not remove them.\n'
                          'The error concerns these products: %s', product_names))
```

**Conditions that trigger the block** (ALL must be true):
1. `bom.active == False` OR `bom.type != 'phantom'` in the `write()` call
2. The BoM being deactivated/deleted is a **phantom** type
3. There exists at least one SOL with:
   - `state == 'sale'` (SO confirmed)
   - `invoice_status in ('no', 'to invoice')` (not yet fully invoiced — `invoiced` or `upselling` are OK)
   - `product_id` matches a product that uses this phantom BoM
   - `move_ids.state != 'cancel'` (at least one non-cancelled stock move exists — delivery not fully cancelled)

**Called in**:
- `write()` — when `active` is set to `False`, or when `type` is changed away from `'phantom'`
- `unlink()` — before any deletion

**Note**: Uses `sudo()` to search `sale.order.line` because MRP users may not have sales ACLs. The ACL on `sale.order.line` granted to `mrp.group_mrp_user` allows `read` (perm_read=1), which is sufficient for a search.

---

### `stock.rule` Extension — L2 Detail

#### `_prepare_mo_vals()` Override — L2 Detail

```python
def _prepare_mo_vals(self, product_id, product_qty, product_uom,
                     location_dest_id, name, origin, company_id, values, bom):
    res = super()._prepare_mo_vals(...)
    if values.get('sale_line_id'):
        res['sale_line_id'] = values['sale_line_id']
    return res
```

**Propagation chain**:
1. `sale.order.action_confirm()` triggers `_action_launch_stock_rule()` (in `sale_stock`)
2. `stock.rule._run_pull()` (or `_run_manufacture()`) creates procurement with `values['sale_line_id']` set
3. `_prepare_mo_vals()` writes `sale_line_id` into the MO's initial vals before creation

The `values` dict comes from the procurement group's `stock.rule` run context and contains the original `sale_line_id`.

#### `_get_stock_move_values()` Override — L2 Detail

```python
def _get_stock_move_values(self, product_id, product_qty, product_uom,
                         location_dest_id, name, origin, company_id, values):
    move_values = super()._get_stock_move_values(...)
    if (sol_id := values.get('sale_line_id')) is not None:
        sol = self.env['sale.order.line'].browse(sol_id)
        if move_values['product_id'] != sol.product_id.id:
            # Component move of a kit
            active_moves = sol.move_ids.filtered(lambda m: m.state != 'cancel')
            bom_line_id = active_moves.bom_line_id.filtered(
                lambda bl: bl.product_id.id == move_values.get('product_id')
            )[:1].id
            if bom_line_id:
                move_values['bom_line_id'] = bom_line_id
    return move_values
```

**Purpose**: For component moves of a kit (where `move_values['product_id'] != sol.product_id`), this sets `bom_line_id` on the move.

The lookup uses `sol.move_ids` (existing moves for this SOL) to find the already-resolved `bom_line_id` rather than re-querying the BOM, which ensures consistency if the BOM changed between moves.

---

### `account.move.line` — `_get_cogs_value()` — L2 Detail

```python
def _get_cogs_value(self):
    price_unit = super()._get_cogs_value()
    so_line = self.sale_line_ids and self.sale_line_ids[-1] or False
    if so_line:
        boms = so_line.move_ids.filtered(
            lambda m: m.state != 'cancel'
        ).mapped('bom_line_id.bom_id').filtered(lambda b: b.type == 'phantom')
        if boms:
            bom = boms.filtered(
                lambda b: b.product_id == so_line.product_id
                or b.product_tmpl_id == so_line.product_id.product_tmpl_id
            )
            if not bom:
                bom = self.env['mrp.bom']._bom_find(
                    products=so_line.product_id,
                    company_id=so_line.company_id.id,
                    bom_type='phantom')[so_line.product_id]
            is_line_reversing = self.move_id.move_type == 'out_refund'
            account_moves = so_line.invoice_lines.move_id.filtered(
                lambda m: m.state == 'posted'
                and bool(m.reversed_entry_id) == is_line_reversing)
            posted_invoice_lines = account_moves.line_ids.filtered(
                lambda l: l.display_type == 'cogs'
                and l.product_id == self.product_id
                and l.balance > 0)
            qty_invoiced = sum(x.product_uom_id._compute_quantity(
                x.quantity, x.product_id.uom_id) for x in posted_invoice_lines)
            reversal_cogs = posted_invoice_lines.move_id.reversal_move_ids.line_ids.filtered(
                lambda l: l.display_type == 'cogs'
                and l.product_id == self.product_id
                and l.balance > 0)
            qty_invoiced -= sum(line.product_uom_id._compute_quantity(
                line.quantity, line.product_id.uom_id) for line in reversal_cogs)
            moves = so_line.move_ids
            average_price_unit = 0
            components_qty = so_line._get_bom_component_qty(bom)
            storable_components = self.env['product.product'].search([
                ('id', 'in', list(components_qty.keys())),
                ('is_storable', '=', True)
            ])
            for product in storable_components:
                factor = components_qty[product.id]['qty']
                prod_moves = moves.filtered(lambda m: m.product_id == product)
                product = product.with_company(self.company_id)
                average_price_unit += factor * prod_moves._get_price_unit()
            price_unit = average_price_unit / bom.product_qty or price_unit
    return price_unit
```

**COGS calculation for kits**:
1. Locate the phantom BOM matching the sold kit product (by product or template)
2. Compute `components_qty` via `_get_bom_component_qty()` — quantities in product base UoM
3. Filter to **storable components only** — consumables/services are excluded from cost (they have no inventory value)
4. For each storable component, sum `component_cost * component_qty` across all relevant stock moves using `_get_price_unit()`
5. Divide by `bom.product_qty` (BOM denominator) to get the per-unit kit cost
6. Falls back to parent method (standard COGS) if no phantom BOM found

**Invoice reversal handling**: `qty_invoiced` is computed from posted invoices, subtracting quantities from reversal/credit note COGS lines to get the net quantity.

---

### `stock.move` — `_get_price_unit()` — L2 Detail

```python
def _get_price_unit(self):
    order_line = self.sale_line_id
    if (order_line
            and all(move.sale_line_id == order_line for move in self)
            and any(move.product_id != order_line.product_id for move in self)):
        # All moves share the same SOL but are different products (kit components)
        product = order_line.product_id.with_company(order_line.company_id)
        bom = product.env['mrp.bom']._bom_find(
            product, company_id=self.company_id.id, bom_type='phantom')[product]
        if bom:
            return self._get_kit_price_unit(product, bom, order_line.qty_delivered)
    return super()._get_price_unit()
```

**Purpose**: When a component move of a kit is priced (for transfers or valuations), return the kit's sale price instead of the component's price.

---

### `stock.move.line` — `_compute_sale_price()` — L2 Detail

```python
def _compute_sale_price(self):
    kit_lines = self.filtered(
        lambda move_line: move_line.move_id.bom_line_id.bom_id.type == 'phantom'
    )
    for move_line in kit_lines:
        unit_price = move_line.product_id.list_price
        qty = move_line.product_uom_id._compute_quantity(
            move_line.quantity, move_line.product_id.uom_id)
        move_line.sale_price = unit_price * qty
    super(StockMoveLine, self - kit_lines)._compute_sale_price()
```

**Purpose**: Sets `sale_price` on kit component move lines for delivery report/value calculations. Uses each component's own `list_price` (not the kit's price), multiplied by the done quantity.

---

## L3 — Cross-Module Integration, Override Patterns, Workflow Triggers, Failure Modes

### L3.1 — Cross-Model: How `sale_line_id` Links `mrp.production` to `sale.order.line`

The bidirectional link is established through two mechanisms that work together:

```
sale.order.line
    │
    ├── procurement group (via sale_stock)
    │       └── stock.reference (links SO to its procurement group)
    │               └── production_ids ──────────► mrp.production
    │                                                       │
    │                                                       └── sale_line_id ──► sale.order.line (direct)
    │
    └── [stock.move_chain for component tracking]
```

**Path 1 — Indirect via `stock_reference_ids`** (used by `_compute_mrp_production_ids`):
- When `sale_stock._action_confirm()` runs, it creates a `stock.reference` record linking the SO to the procurement group
- The procurement group has a `production_ids` one2many pointing to all MOs in that group
- `sale.mrp_production_ids = sale.stock_reference_ids.production_ids.filtered(root + not cancelled)`

**Path 2 — Direct via `sale_line_id`** (used by `action_confirm` propagation and `sale_order_count`):
- `stock.rule._prepare_mo_vals(values)` receives `sale_line_id` from the procurement values and writes it into the new MO's `sale_line_id` field
- `mrp.production.action_confirm()` propagates this to the finished stock move: `move_finished_ids.filtered(finished_product).sale_line_id = mo.sale_line_id`
- The finished move's `sale_line_id` then links the delivery back to the SOL

**Why both paths exist**: Path 1 uses the procurement group as a stable anchor (works even if `sale_line_id` is not set on the MO). Path 2 is the explicit link that allows downstream operations (delivery, invoice) to trace back to the originating SOL.

---

### L3.2 — Override Pattern: `stock.rule._prepare_mo_vals` and `_get_stock_move_values`

Both overrides are in `models/stock_rule.py` and work in a two-phase propagation:

**Phase 1 — MO Creation** (`_prepare_mo_vals`):
```python
# values comes from procurement context, populated by sale_stock
res = super()._prepare_mo_vals(...)
res['sale_line_id'] = values['sale_line_id']  # Direct write into MO vals dict
```

The `values` dict is the procurement context passed through `stock.rule._run_*` methods. When the procurement originates from a SO (via `sale_stock`), `sale_line_id` is already embedded in `values` by the time `_prepare_mo_vals` is called.

**Phase 2 — Component Move Creation** (`_get_stock_move_values`):
```python
# After MO is created, stock.rule creates component moves via _get_stock_move_values
move_values = super()._get_stock_move_values(...)
# For kit component moves (product_id != kit product):
if move_values['product_id'] != sol.product_id.id:
    # Look up the bom_line_id that was already resolved on existing moves
    bom_line_id = sol.move_ids.bom_line_id.filtered(
        bl: bl.product_id == component_id)[:1].id
    move_values['bom_line_id'] = bom_line_id
```

The `bom_line_id` lookup on `sol.move_ids` is key: when `_get_stock_move_values` is called for each component move, the `sol` already has its `move_ids` populated with earlier moves. By filtering on `sol.move_ids`, the override finds the already-resolved `bom_line_id` rather than re-querying the BOM, ensuring consistency with any subsequent BOM changes.

---

### L3.3 — Workflow Trigger: MO Creation from SO Confirmation

```
sale.order.action_confirm()
    │
    ├── sale_stock._action_launch_stock_rule()
    │       └── Iterates over order_line.move_ids
    │               └── stock.rule._run_pull() / _run_manufacture()
    │                       ├── _prepare_mo_vals() ← sale_line_id injected here
    │                       │       └── mrp.production.create()
    │                       │               └── MO created with sale_line_id set
    │                       └── _get_stock_move_values() ← bom_line_id injected
    │                               └── stock.move.create() for components
    │
    └── [MO remains in 'draft' until explicitly confirmed by user or scheduler]
```

**Key distinction**: The MO is created in `draft` state by the stock rule, not automatically confirmed. The manufacturing team reviews and confirms the MO separately.

**The `sale_line_id` injection happens at MO creation time (draft state)**, not at confirmation. This means the MO is linked to the SOL from the moment it appears in the system, even before manufacturing begins.

---

### L3.4 — Failure Modes

#### When an MO is Cancelled

**Test**: `test_mto_cancel_3_steps_mo` (`test_multistep_manufacturing.py:186-209`)

In 3-step manufacturing (`pbm_sam`):
```
SO confirmed → MO (draft) → [PBM picking] → [SAM picking] → [Delivery]
```
When the MO is cancelled after `action_confirm()`:
1. The finished move's `move_orig_ids` (which link to the MO's `move_finished_ids`) are cleared
2. The delivery picking (`out_type`) transitions from `waiting` → `confirmed`
3. The delivery picking's moves switch from `make_to_order` → can now be fulfilled from stock if inventory exists

**Critical behavior**: Cancelling the MO does NOT automatically cancel the delivery. The delivery remains open and can be fulfilled from existing stock. This is intentional — the customer still needs the goods even if manufacturing is cancelled.

**What happens to `sale_line_id`**: When the MO is cancelled, `sale_line_id` remains set on the MO record but the finished move is unlinked. The delivery picking remains linked to the SOL via the `stock.reference` procurement group mechanism, so the SO still shows the delivery.

#### When a SO is Cancelled

When `sale.order._action_cancel()` is called:
1. All linked pickings are cancelled
2. Linked MOs are **not** automatically cancelled — this is intentional. Manufacturing may already be in progress.
3. The `sale_line_id` on the MO remains set, but the SOL's state changes to `cancel`
4. The MO's `_compute_sale_order_count()` will still count the SO but the SOL is cancelled

**Manual intervention required**: The manufacturing team must manually cancel or rework MOs when a SO is cancelled. There is no automatic cascading cancellation from SO to MO.

#### When a Phantom BoM is Modified After MO Creation

**Scenario**: MO was created for a kit. Before MO confirmation, the phantom BOM is modified (different components or quantities).

**What happens**:
- The `stock.rule` override passes `sale_line_id` to the MO but does NOT lock the BOM version
- The MO's component moves are generated from the BOM at the time of creation
- If the BOM changes between MO creation and confirmation, the MO still references the original BOM state (Odoo's BOM is not versioned per MO)
- `action_confirm()` propagates `sale_line_id` to the finished move regardless of BOM state

---

## L4 — Performance, Version Changes, Security

### L4.1 — Performance: Move Chaining and `propagate_cancel` on MO Cancellation

**Move chaining in 3-step manufacturing with MTO**:

```
MRP Production
    └── move_finished_ids (kit product, location_src=WH/pbm, location_dest=WH/stock)
            │
            └── move_dest_ids ───────────► [SAM picking] move_finished_ids
                                                │
                                                └── move_dest_ids ───────────► [Delivery] move_finished_ids
                                                                                  (to customer)
```

When `mrp_production.action_confirm()` runs, it calls `stock.move._update_move_chained_picking()` which links moves via `move_dest_ids`. This creates the chain where the MO's finished product feeds into the SAM picking, which feeds into the delivery.

**`propagate_cancel=True` impact**: The `stock.rule` that created the MO sets `propagate_cancel=True` on the procurement. This means if the MO is cancelled, the cancellation cascades to the procurement's source moves (the component pickings inside the warehouse). However, the downstream moves (SAM picking, delivery) are NOT cancelled — instead their `move_orig_ids` are cleared, reverting them to `confirmed` state where they can be fulfilled from stock.

**Performance implication**: The `move_dest_ids` chaining in multi-level kit manufacturing creates a deep dependency graph. When `_compute_mrp_production_ids` runs, the filter `not mo.production_group_id.parent_ids` avoids traversing the full nested MO tree, which is critical for performance in environments with many sub-assembly MOs.

**Key performance-sensitive operations**:
1. `_compute_mrp_production_ids` — uses `stock_reference_ids.production_ids` which is indexed via the procurement group; the `parent_ids` filter avoids loading sub-MOs
2. `_prepare_qty_delivered` — called frequently on SOLs; the `_compute_kit_quantities` call on component moves can be expensive with many component moves
3. `_get_cogs_value` — performs a `search()` for storable components on every COGS computation; this is a SQL query per invoice line

---

### L4.2 — Version Changes: Odoo 18 to Odoo 19 in sale_mrp

The `sale_mrp` module has been relatively stable between Odoo 18 and Odoo 19. No major API changes were introduced in this bridge module.

**Changes compared to prior versions (Odoo 16→17→18)**:
- The `stock.reference` model (introduced in Odoo 16 for better SO-stock linking) became the primary anchor for `_compute_mrp_production_ids` in Odoo 17+. The prior approach relied more heavily on `procurement_group_id.sale_id` lookup which is now deprecated.
- The `sale_line_id` field on `mrp.production` existed in Odoo 15+ but its propagation via `action_confirm()` has been consistent.
- `_get_stock_move_values` override uses a walrus operator (`:=`) introduced in Python 3.8 — this is compatible with Odoo 19's Python 3.10+ requirement.
- `is_storable` field (renamed from `type='product'`) — the test files use `is_storable=True` throughout, consistent with Odoo 19's field name.
- The `_compute_kit_quantities` method used by `_prepare_qty_delivered` is defined in `stock` module and may have been optimized in Odoo 19.

**No Odoo 18→19 specific changes detected in `sale_mrp` source code**. The module's core responsibility — bridging `sale_line_id` from SO to MO — has remained unchanged.

---

### L4.3 — Security: Access Rights for `sale_line_id` Linking

#### ACL Matrix

| ACL ID | Model | Group | R | W | C | D | Purpose |
|--------|-------|-------|---|---|---|---|---------|
| `access_mrp_bom_user` | `mrp.bom` | `sales_team.group_sale_salesman` | 1 | 0 | 0 | 0 | Salespeople can read BoMs to understand kit structures |
| `access_sale_order_manufacturing_user` | `sale.order` | `mrp.group_mrp_user` | 1 | 1 | 0 | 0 | MRP users can read/write SOs to link MOs |
| `access_sale_order_line_manufacturing_user` | `sale.order.line` | `mrp.group_mrp_user` | 1 | 1 | 0 | 0 | MRP users can update SOL for delivery linking |
| `access_mrp_production_salesman` | `mrp.production` | `sales_team.group_sale_salesman` | 1 | 1 | 1 | 0 | Salespeople can create MOs from SOs |
| `access_mrp_production_workcenter_line_salesman` | `mrp.workorder` | `sales_team.group_sale_salesman` | 1 | 0 | 1 | 0 | Salespeople can create work orders |
| `access_mrp_bom_line_salesman` | `mrp.bom.line` | `sales_team.group_sale_salesman` | 1 | 0 | 0 | 0 | Salespeople can read BOM lines |

#### Security Design Analysis

**Design pattern**: Cross-ACL delegation
- MRP users (`group_mrp_user`) can write to `sale.order` and `sale.order.line` (R+W)
- Sales users (`group_sale_salesman`) can create and write `mrp.production` (R+W+C, no D)
- The `sale_line_id` Many2one field on `mrp.production` is NOT protected by `groups` — it is writable by anyone who can write to `mrp.production`

**Potential security concern**: A user with MRP access (who cannot normally write to SOs) could manually set `sale_line_id` on an MO to point to any SOL in the system, creating a false link between an MO and a SO. This is mitigated by:
1. Only `sales_team.group_sale_salesman` can see the `sale_order_count` and `action_view_sale_orders` button (protected by group)
2. The smart buttons showing linked MOs/SOs are protected by `groups` attributes in XML
3. ACLs prevent MRP users from creating SOs (perm_create=0 on `sale.order`)

**Portal access**: `sale_portal_templates.xml` exposes `mrp_production_ids` on the customer portal. The portal ACL (`base.group_portal`) can see which MOs are associated with their SO, but cannot see MOs from other SOs. This is enforced by the portal's access rights on `mrp.production`.

**Data isolation**: The `sale_line_id` link does not bypass standard record rules. If a user has no access to a SO, they cannot see the linked MO through the smart button (the `sale_order_count` field returns 0 or an access error is raised).

**Audit consideration**: Changes to `sale_line_id` on an MO are NOT automatically tracked by `mail.thread` unless `mrp.production` inherits from it (it does not in `sale_mrp`). For audit purposes, the link is established but not independently audited.

---

## Kit Product Flow (Complete)

```
1. SO Line with kit product (phantom BoM) created
       │
2. SO Confirmed → _action_launch_stock_rule() (sale_stock)
       │
3. stock.rule._run_manufacture()
       ├── _prepare_mo_vals() → mrp.production created with sale_line_id
       └── _get_stock_move_values() → stock.move records created with bom_line_id
       │
4. MO action_confirm()
       ├── Propagates sale_line_id to finished move (move_finished_ids)
       └── Creates move chaining (move_dest_ids links)
       │
5. Manufacturing: components consumed (stock.move), kit produced
       │
6. Delivery: kit shipped via stock.picking (components from stock or MO)
       │
7. _prepare_qty_delivered() → uses _compute_kit_quantities() on component moves
       │
8. Invoice Validation: account.move.line._get_cogs_value()
       └── Computes kit COGS as sum(component_cost * component_qty) / bom_qty
```

---

## Extension Points

### Link MO to SOL from Custom Code

```python
# In custom code that creates MOs:
mo_vals['sale_line_id'] = sale_line_id
mo = env['mrp.production'].create(mo_vals)
mo.action_confirm()  # Propagates sale_line_id to finished move

# Or update existing draft MO:
mo.sale_line_id = sale_line_id
```

### Custom Kit Costing

Override `_get_cogs_value()` in `account.move.line` to use a different cost attribution model (e.g., standard cost instead of average, or custom analytic allocation).

### Protect Additional Phantom BoM Scenarios

Override `_ensure_bom_is_free()` in `mrp.bom` to add protection criteria (e.g., block if any project has the kit assigned, or if analytic lines exist).

### Modify Kit Component UoM Handling

Override `_get_bom_component_qty()` if custom UoM precision or rounding rules are needed for specific kit product categories.

---

## Related

- [Modules/mrp](modules/mrp.md) — Manufacturing orders, BOMs, work orders
- [Modules/sale_stock](modules/sale_stock.md) — Sale + Stock integration (procurement groups, MTO)
- [Modules/stock](modules/stock.md) — Stock moves, quant, picking
- [Modules/account](modules/account.md) — Invoice, COGS, Anglo-Saxon valuation
- [Core/API](core/api.md) — @api.depends, @api.onchange, computed fields
- [Patterns/Inheritance Patterns](patterns/inheritance-patterns.md) — _inherit vs _inherits vs mixin
