---
tags:
  - odoo
  - odoo19
  - modules
  - purchase
  - mrp
  - manufacturing
---

# purchase_mrp

> Bridges Purchase and Manufacturing: when a Manufacturing Order (MO) needs components that are not in stock, `purchase_mrp` automatically creates procurement orders (POs) to buy them, and tracks the resulting POs back from each Purchase Order to its source MOs. Also handles phantom kit product invoicing and cost-share distribution for AVCO-valuation kits purchased through PO.

## Quick Facts

| Property | Value |
|----------|-------|
| **Module ID** | `purchase_mrp` |
| **Type** | Community Edition (CE) |
| **Location** | `odoo/addons/purchase_mrp/` |
| **Odoo Version** | 19+ |
| **License** | LGPL-3 |
| **Category** | Supply Chain / Purchase |
| **Depends** | `mrp`, `purchase_stock` |
| **Auto-install** | True |
| **ERP Usage** | MO component procurement via PO; phantom kit qty received; AVCO cost-share for kits |
| **Manifest version** | `1.0` (minor-only versioning for bridge module) |

---

## L1 - Complete Model & Field Inventory

### File Structure

```
purchase_mrp/
├── __init__.py               imports models + report sub-packages
├── __manifest__.py            depends: [mrp, purchase_stock], auto_install: True
├── models/
│   ├── __init__.py            imports: purchase, mrp_production, mrp_bom, stock_move, stock_rule
│   ├── purchase.py            extends: purchase.order, purchase.order.line
│   ├── mrp_production.py       extends: mrp.production
│   ├── mrp_bom.py             extends: mrp.bom, mrp.bom.line
│   ├── stock_move.py          extends: stock.move
│   └── stock_rule.py          extends: stock.rule
├── report/
│   ├── __init__.py
│   ├── mrp_report_bom_structure.py   extends: report.mrp.report_bom_structure
│   └── mrp_report_mo_overview.py    extends: report.mrp.report_mo_overview
├── views/
│   ├── mrp_production_views.xml        Purchase Orders smart button on MO form
│   ├── purchase_order_views.xml        Manufacturing smart button on PO form
│   ├── mrp_bom_views.xml              cost_share column on BOM line tree
│   └── stock_orderpoint_views.xml     route_id optional="show" on orderpoint
├── security/
│   └── ir.model.access.csv            read-only ACL for BOM/BOM-line to purchase users
├── data/
│   └── purchase_mrp_demo.xml           adds buy route to MRP demo product
└── tests/
    ├── test_purchase_mrp_flow.py       orderpoint route resolution
    ├── test_anglo_saxon_valuation.py cost_share, AVCO kit valuation, constraint
    └── test_replenishment.py          orderpoint route placeholders
```

---

## Models

### `mrp.production` - Extended

**File:** `models/mrp_production.py`

#### Fields Added

| Field | Type | Groups | Description |
|-------|------|--------|-------------|
| `purchase_order_count` | `Integer` (computed) | `purchase.group_purchase_user` | Count of POs linked via `reference_ids`. Non-purchase users see it as inaccessible. Not stored - evaluated on demand. |

#### `@api.depends` - `_compute_purchase_order_count()`

`depends: [reference_ids, reference_ids.purchase_ids]`

Reads the many2many `purchase_ids` on the `procurement.group`. Inexpensive - no full record traversal.

#### Methods

**`_get_purchase_orders()`**

```python
def _get_purchase_orders(self):
    self.ensure_one()
    return self.reference_ids.purchase_ids
```

`reference_ids` is the `procurement.group` created by `purchase_stock`. Its `purchase_ids` field holds all POs linked to this MO.

**`action_view_purchase_orders()`**

Smart-button action. Single PO -> form view; multiple -> list/domain view filtered to PO IDs. Uses `ensure_one()` so multi-record calls open list view.

**`_get_document_iterate_key(move_raw_id)`**

```python
def _get_document_iterate_key(self, move_raw_id):
    iterate_key = super(MrpProduction, self)._get_document_iterate_key(move_raw_id)
    if not iterate_key and move_raw_id.created_purchase_line_ids:
        iterate_key = 'created_purchase_line_ids'
    return iterate_key
```

The base MRP method returns a key used by the procurement merge engine. When a raw material move has purchase lines but no upstream stock.move chain, this override injects `'created_purchase_line_ids'` as the iteration key, preventing PO merges for procurements with different PO lines.

**`_prepare_merge_orig_links()`**

```python
def _prepare_merge_orig_links(self):
    origs = super()._prepare_merge_orig_links()
    for move in self.move_raw_ids:
        if not move.move_orig_ids or not move.created_purchase_line_ids:
            continue
        origs[move.bom_line_id.id].setdefault('created_purchase_line_ids', set()).update(
            move.created_purchase_line_ids.ids
        )
    for vals in origs.values():
        if vals.get('created_purchase_line_ids'):
            vals['created_purchase_line_ids'] = [Command.set(vals['created_purchase_line_ids'])]
        else:
            vals['created_purchase_line_ids'] = []
    return origs
```

When multiple raw-material moves share the same `bom_line_id`, their purchase line IDs are merged via `Command.set`. Skips moves with no `move_orig_ids`. `Command` is imported from `odoo.api`.

---

### `purchase.order` - Extended

**File:** `models/purchase.py`

#### Fields Added

| Field | Type | Groups | Description |
|-------|------|--------|-------------|
| `mrp_production_count` | `Integer` (computed) | `mrp.group_mrp_user` | Count of MOs linked via `reference_ids`. |

#### `@api.depends` - `_compute_mrp_production_count()`

`depends: [reference_ids, reference_ids.production_ids]`

#### Methods

**`_get_mrp_productions(**kwargs)`**

Returns `self.reference_ids.production_ids`. Mirrors `_get_purchase_orders()` on the PO side.

**`action_view_mrp_productions()`**

Same smart-button pattern as `action_view_purchase_orders()` on the MO side.

---

### `purchase.order.line` - Extended

**File:** `models/purchase.py`

This is the most operationally significant extension: handles phantom kit received-qty computation and cost-share propagation.

#### Methods

**`_prepare_qty_received()`**

```python
def _prepare_qty_received(self):
    kit_invoiced_qties = defaultdict(float)
    kit_lines = self.env['purchase.order.line']
    lines_stock = self.filtered(
        lambda l: l.qty_received_method == 'stock_moves'
                   and l.move_ids
                   and l.state != 'cancel'
    )
    product_by_company = defaultdict(OrderedSet)
    for line in lines_stock:
        product_by_company[line.company_id].add(line.product_id.id)
    kits_by_company = {
        company: self.env['mrp.bom']._bom_find(
            self.env['product.product'].browse(product_ids),
            company_id=company.id,
            bom_type='phantom'
        )
        for company, product_ids in product_by_company.items()
    }
    for line in lines_stock:
        kit_bom = kits_by_company[line.company_id].get(line.product_id)
        if kit_bom:
            moves = line.move_ids.filtered(
                lambda m: m.state == 'done'
                          and m.location_dest_usage != 'inventory'
            )
            order_qty = line.product_uom_id._compute_quantity(
                line.product_uom_qty, kit_bom.product_uom_id
            )
            filters = {
                'incoming_moves': lambda m:
                    m._is_incoming() and (
                        not m.origin_returned_move_id
                        or (m.origin_returned_move_id and m.to_refund)
                    ),
                'outgoing_moves': lambda m:
                    m._is_outgoing() and m.to_refund,
            }
            kit_invoiced_qties[line] = moves._compute_kit_quantities(
                line.product_id, order_qty, kit_bom, filters
            )
            kit_lines += line
    invoiced_qties = super(
        PurchaseOrderLine, self - kit_lines
    )._prepare_qty_received()
    invoiced_qties.update(kit_invoiced_qties)
    return invoiced_qties
```

Logic:
1. Filters to lines using `stock_moves` received method with non-cancelled moves.
2. Groups by company for multi-company-safe `_bom_find` calls.
3. `_bom_find(..., bom_type='phantom')` returns only phantom BOMs for each product.
4. For kit lines: filters done moves (excluding inventory-adjustment drops), computes kit order qty in BOM UoM, delegates to `stock.move._compute_kit_quantities()`.
5. Non-kit lines fall through to `super()`.
6. Results merged; returns dict of `{pol_id: qty_received}`.

**`_prepare_stock_moves(picking)`**

```python
def _prepare_stock_moves(self, picking):
    res = super()._prepare_stock_moves(picking)
    if len(self.order_id.reference_ids.move_ids.production_group_id) == 1:
        for re in res:
            re['production_group_id'] = (
                self.order_id.reference_ids.move_ids.production_group_id.id
            )
    sale_line_product = self._get_sale_order_line_product()
    if sale_line_product:
        bom = self.env['mrp.bom']._bom_find(
            self.env['product.product'].browse(sale_line_product.id),
            company_id=picking.company_id.id,
            bom_type='phantom'
        )
        bom_kit = bom.get(sale_line_product)
        if bom_kit:
            _dummy, bom_sub_lines = bom_kit.explode(
                sale_line_product, self.sale_line_id.product_uom_qty
            )
            bom_kit_component = {
                line['product_id'].id: line.id
                for line, _ in bom_sub_lines
            }
            for vals in res:
                if vals['product_id'] in bom_kit_component:
                    vals['bom_line_id'] = bom_kit_component[vals['product_id']]
    return res
```

Two responsibilities:
- **MO-side**: If PO references exactly one production group, all incoming moves get `production_group_id` set, linking receipt to MO.
- **Kit-side**: For kit products with a `sale_line_id`, resolves which BOM line each component belongs to via `explode()`, then sets `bom_line_id` on each move vals for proper back-flushing.

**`_get_upstream_documents_and_responsibles(self, visited)`**

```python
def _get_upstream_documents_and_responsibles(self, visited):
    return [(self.order_id, self.order_id.user_id, visited)]
```

Returns the PO itself, not individual MOs. Anchors the traceability chain at the PO level for buyers.

**`_get_qty_procurement()`**

```python
def _get_qty_procurement(self):
    self.ensure_one()
    bom = self.env['mrp.bom'].sudo()._bom_find(
        self.product_id, bom_type='phantom'
    )[self.product_id]
    if bom and 'previous_product_qty' in self.env.context:
        return self.env.context['previous_product_qty'].get(self.id, 0.0)
    return super()._get_qty_procurement()
```

Detects kit qty changes on PO (Odoo sets `previous_product_qty` in context during `_update_procurement_quantity`). Returns the quantity before the change, preventing procurement cascades during intermediate edits. Uses `sudo()` scoped only to `_bom_find` - buyer's ACL is respected for all other operations.

**`_get_move_dests_initial_demand(move_dests)`**

```python
def _get_move_dests_initial_demand(self, move_dests):
    kit_bom = self.env['mrp.bom']._bom_find(
        self.product_id, bom_type='phantom'
    )[self.product_id]
    if kit_bom:
        filters = {
            'incoming_moves': lambda m: True,
            'outgoing_moves': lambda m: False,
        }
        return move_dests._compute_kit_quantities(
            self.product_id, self.product_qty, kit_bom, filters
        )
    return super()._get_move_dests_initial_demand(move_dests)
```

Returns kit-level demand for downstream destination moves (e.g., an MO consuming the kit), instead of raw component quantities. `incoming_moves: lambda m: True` counts all downstream moves.

**`_get_sale_order_line_product()`**

```python
def _get_sale_order_line_product(self):
    return False
```

Returns `False` unconditionally. Prevents `purchase_stock`'s parent method from returning a sale product and triggering sale-based routing for kit components purchased for manufacturing.

---

### `stock.move` - Extended

**File:** `models/stock_move.py`

#### Methods

**`_get_cost_ratio(quantity)`**

```python
def _get_cost_ratio(self, quantity):
    self.ensure_one()
    if self.bom_line_id.bom_id.type == "phantom":
        uom_quantity = self.product_uom._compute_quantity(
            self.quantity, self.product_id.uom_id
        )
        if not self.product_uom.is_zero(uom_quantity):
            return (self.cost_share / 100) * quantity / uom_quantity
    return super()._get_cost_ratio(quantity)
```

Used in Anglo-Saxon (real-time) valuation. For phantom kit component moves, distributes cost proportionally via `cost_share / 100`. The `(quantity / uom_quantity)` normalizes for UoM differences. If `uom_quantity` is zero, returns `super()` (prevents division by zero).

**`_prepare_phantom_move_values(bom_line, product_qty, quantity_done)`**

```python
def _prepare_phantom_move_values(self, bom_line, product_qty, quantity_done):
    vals = super()._prepare_phantom_move_values(bom_line, product_qty, quantity_done)
    if self.purchase_line_id:
        vals['purchase_line_id'] = self.purchase_line_id.id
    return vals
```

When Odoo explodes a phantom kit during MO material consumption, it creates sub-moves for each component. This override preserves `purchase_line_id` on those sub-moves. Without it, MO sub-moves lose their PO link, breaking traceability and valuation.

**`_get_valuation_price_and_qty(related_aml, to_curr)`**

```python
def _get_valuation_price_and_qty(self, related_aml, to_curr):
    valuation_price_unit_total, valuation_total_qty = (
        super()._get_valuation_price_and_qty(related_aml, to_curr)
    )
    boms = self.env['mrp.bom']._bom_find(
        related_aml.product_id,
        company_id=related_aml.company_id.id,
        bom_type='phantom'
    )
    if related_aml.product_id in boms:
        kit_bom = boms[related_aml.product_id]
        order_qty = related_aml.product_id.uom_id._compute_quantity(
            related_aml.quantity, kit_bom.product_uom_id
        )
        filters = {
            'incoming_moves': lambda m:
                m.location_id.usage == 'supplier'
                and (not m.origin_returned_move_id
                     or (m.origin_returned_move_id and m.to_refund)),
            'outgoing_moves': lambda m:
                m.location_id.usage != 'supplier' and m.to_refund,
        }
        valuation_total_qty = self._compute_kit_quantities(
            related_aml.product_id, order_qty, kit_bom, filters
        )
        valuation_total_qty = kit_bom.product_uom_id._compute_quantity(
            valuation_total_qty, related_aml.product_id.uom_id
        )
        if (related_aml.product_uom_id.rounding
                or related_aml.product_id.uom_id.is_zero(valuation_total_qty)):
            raise UserError(_(
                'Odoo is not able to generate the anglo saxon entries. '
                'The total valuation of %s is zero.',
                related_aml.product_id.display_name
            ))
    return valuation_price_unit_total, valuation_total_qty
```

For a kit product received via PO with AVCO real-time valuation, computes the **kit-level quantity** for the valuation entry denominator. If total kit valuation qty rounds to zero (e.g., all components have zero cost_share and zero price), raises UserError because AVCO cannot post a zero-quantity valuation layer.

---

### `mrp.bom` - Extended

**File:** `models/mrp_bom.py`

#### Methods

**`_check_bom_lines()` - `@api.constrains`**

```python
@api.constrains('product_id', 'product_tmpl_id',
                'bom_line_ids', 'byproduct_ids', 'operation_ids')
def _check_bom_lines(self):
    res = super()._check_bom_lines()
    for bom in self:
        if all(not bl.cost_share for bl in bom.bom_line_ids):
            continue
        if any(bl.cost_share < 0 for bl in bom.bom_line_ids):
            raise UserError(_(
                "Components cost share have to be positive or equals to zero."
            ))
        for product in bom.product_tmpl_id.product_variant_ids:
            total_variant_cost_share = sum(
                bom.bom_line_ids.filtered(
                    lambda bl: not bl._skip_bom_line(product)
                               and not bl.product_uom_id.is_zero(bl.product_qty)
                ).mapped('cost_share')
            )
            if float_round(total_variant_cost_share, precision_digits=2) not in [0, 100]:
                raise UserError(_(
                    "The total cost share for a BoM's component have to be 100"
                ))
    return res
```

Two validation layers:
1. **Non-negative**: any `cost_share < 0` raises immediately.
2. **100% total**: for each variant (including archived), sum cost_share for applicable lines. Total must round to exactly 0.00 or 100.00. `precision_digits=2` means cost shares differing from 0 or 100 by less than 0.005 are accepted.

**`_round_last_line_done()` - `@api.model` class method**

```python
@api.model
def _round_last_line_done(self, lines_done):
    result = super()._round_last_line_done(lines_done)
    if result:
        result[-1][1]['line_cost_share'] = float_round(
            100.0 - sum(vals.get('line_cost_share', 0.0) for _, vals in result[:-1]),
            precision_digits=2
        )
    return result
```

Forces the last component line's `line_cost_share` to be exactly `100.00 - sum(previous)`, preventing floating-point rounding errors (e.g., `25 + 25 + 25 + 25 = 99.99`) from leaving the total short. The `precision_digits=2` ensures the forced value rounds to 2 decimal places.

---

### `mrp.bom.line` - Extended

**File:** `models/mrp_bom.py`

#### Fields Added

| Field | Type | Digits | Default | Groups | Description |
|-------|------|--------|---------|--------|-------------|
| `cost_share` | `Float` | `(5, 2)` | `0.0` | None | Percentage (0-999.99) of kit purchase price for this component. Optional; only enforced for phantom BOMs. |

No group restriction. Visibility controlled at view level: `column_invisible="parent.type != 'phantom'"`.

#### Methods

**`_get_cost_share()`**

```python
def _get_cost_share(self):
    self.ensure_one()
    product = self.env.context.get(
        'bom_variant_id', self.env['product.product']
    )
    variant_bom_lines = self.bom_id.bom_line_ids.filtered(
        lambda bl: not bl._skip_bom_line(product)
                   and not bl.product_uom_id.is_zero(bl.product_qty)
    )
    if (not float_is_zero(self.cost_share, precision_digits=2)
            or not len(variant_bom_lines)
            or all(float_is_zero(bom_line.cost_share, precision_digits=2)
                   for bom_line in variant_bom_lines)):
        return self.cost_share / 100
    return 1 / len(variant_bom_lines)
```

Returns component fraction (0.0-1.0) of kit cost:
- Explicit non-zero cost_share (not 0.00 at 2dp precision) -> use it directly.
- Only applicable line (`len == 1`) -> 100%.
- All applicable lines have zero cost_share -> equal split: `1/n`.
- `precision_digits=2` means `cost_share = 0.001` is treated as zero and gets equal distribution.

**`_prepare_bom_done_values()`** - adds `bom_cost_share` to result for nested kit propagation up the BOM hierarchy.

**`_prepare_line_done_values()`** - adds `line_cost_share` (rounded to 2dp) to each component move value dict.

**`_get_line_cost_share(product, boms_done)`**

```python
def _get_line_cost_share(self, product, boms_done):
    if not self:
        return 100.0
    self.ensure_one()
    parent_cost_share = next((
        vals.get('bom_cost_share', 100.0)
        for bom, vals in reversed(boms_done)
        if bom == self.bom_id
    ), 100)
    line_cost_share = (
        parent_cost_share
        * self.with_context(bom_variant_id=product)._get_cost_share()
    )
    return line_cost_share
```

Walks `boms_done` stack backwards to find the nearest ancestor BOM's `bom_cost_share` (default 100 for root kit). Multiplies by `self._get_cost_share()` which respects variant-specific equal splits via `bom_variant_id` context.

---

### `stock.rule` - Extended

**File:** `models/stock_rule.py`

#### Methods

**`_notify_responsible(procurement)`**

```python
def _notify_responsible(self, procurement):
    super()._notify_responsible(procurement)
    origin_orders = (
        procurement.values.get('group_id').mrp_production_ids
        if procurement.values.get('group_id')
        else False
    )
    if origin_orders:
        notified_users = (
            procurement.product_id.responsible_id.partner_id
            | origin_orders.user_id.partner_id
        )
        self._post_vendor_notification(
            origin_orders, notified_users, procurement.product_id
        )
```

In addition to the product's responsible (base method), also notifies the MO's assignee. Union via `|`. `_post_vendor_notification` posts a mail.message on the PO and emails `notified_users`.

---

## L2 - Field Types, Defaults, Constraints, Onchanges

### Complete Field Inventory

| Model | Field | Type | Digits | Default | Required | Groups | Store | Notes |
|-------|-------|------|--------|---------|---------|-------|-------|-------|
| `mrp.production` | `purchase_order_count` | Integer | - | - | - | `purchase.group_purchase_user` | No | Computed |
| `purchase.order` | `mrp_production_count` | Integer | - | - | - | `mrp.group_mrp_user` | No | Computed |
| `mrp.bom.line` | `cost_share` | Float | `(5, 2)` | `0.0` | No | None | Yes | Only enforced for phantom BOMs |

### Constraints

| Model | Decorator | Triggered On | Validation |
|-------|-----------|-------------|------------|
| `mrp.bom` | `@api.constrains('product_id', 'product_tmpl_id', 'bom_line_ids', 'byproduct_ids', 'operation_ids')` | Any listed field change | `cost_share >= 0`; total variant cost_share rounds to 0 or 100 |

### Onchanges

This module introduces **zero `@api.onchange` methods**. All behavior is reactive through computed fields or called explicitly by the ORM during procurement/stock move processing.

### Computed Field Dependencies

| Field | Depends |
|-------|---------|
| `mrp.production.purchase_order_count` | `reference_ids`, `reference_ids.purchase_ids` |
| `purchase.order.mrp_production_count` | `reference_ids`, `reference_ids.production_ids` |

Both use `procurement.group` as the join table - lightweight many2many reads.

---

## L3 - Cross-Module Interactions

### L3-a - cross_model: How PO Lines Link to Manufacturing

The link is always through `procurement.group` (`reference_ids` on both `mrp.production` and `purchase.order`):

```
mrp.production
  `- reference_ids  (procurement.group)
       |- production_ids  -> [mrp.production.id]
       `- purchase_ids   -> [purchase.order.id]
```

When `purchase_stock` fires a procurement for an MO component:
1. A `procurement.group` is created/updated linking the MO's stock moves to the PO.
2. The PO is assigned to `group_id.purchase_ids`.
3. Both sides expose their group's other side via `reference_ids`.

**Key consequence**: A single PO can serve multiple MOs if they share the same procurement group. There is **no direct field** on `purchase.order.line` referencing an MO or BOM line - the link is at the PO/procurement-group level only.

### L3-b - override_pattern: `stock.rule` MO Generation

This module does **not** override `_prepare_mo_vals` or any MO-creation method. MO creation (when `stock.rule.action == 'manufacture'`) is handled by `mrp` + `stock` modules. The only `stock.rule` override is `_notify_responsible()` for vendor notification.

However, `_prepare_stock_moves()` on `purchase.order.line` injects `production_group_id` into move vals so that stock moves carry the production group. This enables the `stock.move` -> `procurement.group` -> `mrp.production` trace when the MO consumes received components.

### L3-c - workflow_trigger: MO Creation from PO Receipt

There is **no direct MO creation from PO receipt** in this module. The direction is:

```
PO receipt -> stock.move (incoming)
    -> stock.move consumed by MO (backflush)
    -> mrp.production moves forward
```

`_get_document_iterate_key` and `_prepare_merge_orig_links` on `mrp.production` ensure PO line IDs are tracked as origin links on MO raw material moves. This enables correct MO move merge/split when PO quantities change, without losing the MO->PO link.

### L3-d - failure_mode: Supplier Lead Time vs. Manufacturing Lead Time

No explicit failure handling for lead-time conflicts exists in this bridge module. Failure modes are absorbed by base modules:

| Failure | Behavior | Mitigation |
|---------|----------|------------|
| Supplier lead time > MO urgency | PO is created; MO waits for components | `stock.warehouse.days_to_purchase`; orderpoint `lead_days` |
| PO quantity < required qty | Partial receipt; `_prepare_qty_received()` returns partial kit qty | MO's `availability_state` shows `partial` |
| Vendor cancels PO after MO confirmed | MO remains waiting | Use `procurement.group` to track; manual PO required |
| Kit BOM change after PO confirmed | `cost_share` on done SVLs is fixed at receipt time | New PO for revised kit must be created |

### L3-e - Phantom Kit Cost Share Flow (Complete Trace)

```
PO Line: Kit product @ 100/unit, qty=10
  |
  |- _prepare_stock_moves() -> sets production_group_id on moves
  |
  |- Vendor ships 10 kits worth of components
  |
  |- Receipt validated
  |    |- stock.move._get_valuation_price_and_qty() [purchase_mrp override]
  |    |     -> Computes kit qty for AVCO valuation layer
  |    |     -> Raises if total valuation qty = 0
  |    |
  |    |- mrp.bom.line._get_line_cost_share() [purchase_mrp override]
  |          -> For each component: parent_cost x (cost_share/100)
  |          -> Equal split if all cost_share = 0
  |
  |- MO marks kit as done
       |- mrp.bom._round_last_line_done() [purchase_mrp override]
             -> Last component gets remainder to sum to exactly 100.00%
```

---

## L4 - Performance, Version Changes, Security

### L4-a - performance: MO Generation from PO

**Batching**: The module implements no custom batching. All MO procurement creation is handled by `stock.rule` / `purchase_stock`. The potentially heavy operation is `_compute_kit_quantities()`, called:
- Once per PO line (not per move) during `_prepare_qty_received()`.
- Once per AML during `_get_valuation_price_and_qty()` (Anglo-Saxon mode only).

For complex nested phantom BOMs, the traversal is recursive but reuses `stock.move._compute_kit_quantities` - not duplicated code.

**Computed count fields** (`purchase_order_count`, `mrp_production_count`) are **not stored**. Evaluated on demand. They read the many2many `purchase_ids` / `production_ids` on the `procurement.group` - no full PO/MO record traversal. A form load with 1 MO and 10 linked POs triggers 1 extra query for `reference_ids.purchase_ids`. The many2many is already indexed by Odoo.

### L4-b - version_change: Odoo 18 -> 19 in purchase_mrp

No Odoo 18->19 API changes detected in this module's source files. All used APIs are stable:

| API | Status in 19 |
|-----|-------------|
| `@api.depends('reference_ids', ...)` | Unchanged |
| `@api.constrains(...)` | Unchanged |
| `mrp.bom._bom_find(..., bom_type='phantom')` | Unchanged signature |
| `stock.move._compute_kit_quantities(...)` | Unchanged signature |
| `procurement.group.mrp_production_ids` | Unchanged |
| `fields.Float(digits=(5,2))` | Unchanged |
| `procurement.group` model name | Unchanged |

**`cost_share` field**: Introduced in Odoo 17/18, persists unchanged in Odoo 19. The `_round_last_line_done` method and `_check_bom_lines` constraint were introduced alongside it.

**Report extensions**: Both abstract model overrides existed in Odoo 17+ and 19.

### L4-c - security: Buyer vs. Manufacturing User Access

#### ACL File: `security/ir.model.access.csv`

```
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_mrp_bom_purchase_user,mrp.bom,purchase.group_purchase_user,1,0,0,0,0
access_mrp_bom_line_purchase_user,mrp.bom.line,purchase.group_purchase_user,1,0,0,0,0
```

Only **read** access to `mrp.bom` and `mrp.bom.line` for `purchase.group_purchase_user`. Buyers can view BOM structures without modifying them.

#### Count Fields - Group Restrictions

| Field | Group | Result |
|-------|-------|--------|
| `mrp.production.purchase_order_count` | `purchase.group_purchase_user` | Purchase users see PO button on MO form; MRP users see it as inaccessible |
| `purchase.order.mrp_production_count` | `mrp.group_mrp_user` | MRP users see Manufacturing button on PO form; Purchase users see it as inaccessible |

Group restrictions are applied through `fields_view_get()` field metadata - users without the group see the value as 0, not an access error.

#### `cost_share` - No Group Restriction

The `cost_share` field has **no `groups` attribute**. All users with BOM form access can read and write it. Visibility is view-level only (`column_invisible`).

#### `sudo()` Usage

`_get_qty_procurement()` uses `self.env['mrp.bom'].sudo()._bom_find(...)`. `sudo()` is scoped to just the `_bom_find` call - the buyer's ACL is respected for all other operations in that method.

---

## Report Extensions

### `report.mrp.report_bom_structure` - Extended

Extends the BOM structure report to include buy route / supplier information.

| Method | Purpose |
|-------|---------|
| `_format_route_info()` | Adds `supplier_delay` = `supplier.delay + rules_delay + purchase_lead`. `purchase_lead` from `parent_bom.company_id.days_to_purchase` if set. Returns `route_type: 'buy'` dict with supplier detail. |
| `_is_resupply_rules()` | Returns `True` if any rule has `action == 'buy'` - causes report to show a Resupply row even without a manufacture route. |
| `_is_buy_route()` | Returns `True` if a rule with `action == 'buy'` and `product.seller_ids` exists. |
| `_get_resupply_availability()` | For `route_type == 'buy'`, returns `('estimated', supplier_delay)`. |

### `report.mrp.report_mo_overview` - Extended

Extends the MO overview report to show PO replenishments feeding MOs.

| Method | Purpose |
|-------|---------|
| `_get_extra_replenishments()` | Searches PO lines for draft/sent/to-approve lines matching the component. Traces `move_dest_ids` upward via `_rollup_move_dests()` to find linked MOs. Computes proportional `prod_qty` if the PO line feeds multiple MOs. |
| `_format_extra_replenishment()` | Builds replenishment dict with PO reference, tax-inclusive cost, quantity, UoM, and optional `production_id`. |
| `_get_replenishment_receipt()` | For PO: `estimated` from `date_planned` if not confirmed; `expected` from `max(in_pickings.scheduled_date)` if confirmed. |
| `_get_resupply_data()` | For buy routes: uses `product._select_seller()` + supplier price instead of manufactured product cost. |
| `_is_doc_in_done()` | PO is done when state=`purchase` AND all stock moves are `done` or `cancel`. |
| `_get_origin(move)` | Returns `move.purchase_line_id.order_id` for PO-linked moves. |
| `_get_replenishment_mo_cost()` | For moves with `purchase_line_id`, computes cost via `tax_ids.compute_all` + currency conversion. |

---

## Business Flow: Complete Trace

```
[MANUFACTURING SIDE]                          [PURCHASE SIDE]
1. Create & confirm MO
   |- mrp.production.action_confirm()
        -> checks component availability
        -> for shortage: stock.rule fires (purchase_stock)
             -> creates procurement
             -> creates/updates RFQ
             -> procurement.group created/updated
                |- .purchase_ids += purchase_order
                |- .production_ids += mrp_production

2. Buyer approves PO -> purchase.order.button_confirm()

3. Vendor ships components
   |- Incoming picking created
        |- _prepare_stock_moves() injects production_group_id

4. Goods received
   |- stock.picking.button_validate()
        |- _prepare_qty_received() computes kit qty via _compute_kit_quantities()
        |- stock.move._get_valuation_price_and_qty() for phantom kit AVCO

5. MO consumes received components
   |- mrp.production._update_stock_moves()
        -> matches by production_group_id
        -> backflushes received qty

6. Both sides see linked documents:
   |- Buyer opens PO -> Manufacturing smart button
        -> action_view_mrp_productions()
             lists mrp.production via reference_ids.production_ids
   |- Production Mgr opens MO -> Purchases smart button
        -> action_view_purchase_orders()
             lists purchase.order via reference_ids.purchase_ids

7. Vendor notification
   |- stock.rule._notify_responsible()
        -> notifies product.responsible_id.partner_id
             AND mrp_production.user_id.partner_id
```

---

## Views

### Smart Buttons

**MO Form** (`mrp_production_views.xml`):
Placed before `action_view_mrp_production_childs`:
```xml
<button name="action_view_purchase_orders" type="object"
         icon="fa-credit-card"
         groups="purchase.group_purchase_user"
         invisible="purchase_order_count == 0">
    <div class="o_field_widget o_stat_info">
        <span class="o_stat_value"><field name="purchase_order_count"/></span>
        <span class="o_stat_text">Purchases</span>
    </div>
</button>
```

**PO Form** (`purchase_order_views.xml`):
Inside `button_box` div:
```xml
<button name="action_view_mrp_productions" type="object"
         icon="fa-wrench"
         invisible="mrp_production_count == 0"
         groups="mrp.group_mrp_user">
    <div class="o_field_widget o_stat_info">
        <span class="o_stat_value"><field name="mrp_production_count"/></span>
        <span class="o_stat_text">Manufacturing</span>
    </div>
</button>
```

### BOM Line Tree (`mrp_bom_views.xml`)

```xml
<field name="cost_share" optional="hidden"
        column_invisible="parent.type != 'phantom'"/>
```
Hidden by default; user can show via column chooser. No group restriction.

### Orderpoint List (`stock_orderpoint_views.xml`)

Changes `route_id` from `optional="hide"` to `optional="show"`. Makes the route column visible by default on the orderpoint list, helping buyers see which route drives replenishment.

---

## Key Design Decisions

### Why `cost_share` on `mrp.bom.line`?

Cost share is a per-component attribute stored directly on `mrp.bom.line`. Using a separate model would require a join table and complicate `_get_line_cost_share` traversal. The field is optional: omitting it triggers equal split across all non-zero-qty components.

### Why `_round_last_line_done` on `mrp.bom` (class method)?

It is a `@api.model` class method called with the full `lines_done` list - all components at all BOM levels. It needs to see all lines to compute the remainder for the last one. A per-line instance method could not access sibling lines at the same level.

### Why `sudo()` only on `_bom_find` in `_get_qty_procurement`?

`_get_qty_procurement` runs as the buyer. A buyer may not have read access to `mrp.bom`. `sudo()` bypasses record rules for the BOM lookup only; writing to the PO line stays under the buyer's ACL.

### Why `_get_sale_order_line_product` returns `False`?

In `purchase_stock`, this returns `sale_line_id.product_id` to help `stock.rule` apply sale-specific routing. For phantom kits purchased for manufacturing, returning a sale product would incorrectly trigger MTO or sale_stock rules. Returning `False` ensures the kit follows its own product routes (manufacture or buy).

---

## See Also

- [[Modules/mrp]] - manufacturing core: `mrp.production`, `mrp.bom`, `_compute_kit_quantities`
- [[Modules/purchase_stock]] - procurement rules: `stock.rule` PO generation
- [[Modules/stock]] - stock moves, `procurement.group`, `production_group_id`
- [[Core/BaseModel]] - `reference_ids` / `procurement.group` pattern
- [[Modules/stock_account]] - Anglo-Saxon valuation, `_get_valuation_price_and_qty`
- [[Modules/quality_mrp]] - quality checks on manufacturing (Enterprise)
