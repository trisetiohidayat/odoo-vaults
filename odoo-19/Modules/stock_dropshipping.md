---
type: module
module: stock_dropshipping
tags: [odoo, odoo19, stock, dropshipping, purchase, sale, supply_chain]
created: 2026-04-11
---

# Stock Dropshipping

## Overview

| Property | Value |
|----------|-------|
| **Name** | Drop Shipping |
| **Technical** | `stock_dropshipping` |
| **Category** | Supply Chain/Inventory |
| **Version** | 1.0 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Odoo Version** | 19.0 |

## Description

The `stock_dropshipping` module configures **Drop Shipping** -- a supply chain mode where goods flow **directly from vendor to customer**, bypassing the retailer's own warehouse entirely. No internal stock transfer is created at the retailer's location.

It adds a pre-configured **Dropship operation type** and the **`stock_dropshipping.route_drop_shipping`** procurement route. The module does not stand alone: it depends on `sale_purchase_stock`, which provides the SO -> PO -> Stock chain that drives the dropship flow.

```
Normal flow:         Vendor → Retailer Warehouse → Customer
Dropship flow:       Vendor ──────────────────────→ Customer
                     (no warehouse stop)
```

## Dependencies

```
stock_dropshipping
    └── sale_purchase_stock
            ├── sale
            ├── purchase
            └── stock
```

## Business Flow

When a sale order line uses the **Drop Shipping** route:

1. **Sale Order confirmed** -> triggers procurement via `sale_purchase_stock`
2. **Purchase Order auto-created** targeting the vendor, with `dest_address_id` set to the customer's shipping address
3. **Receipt picking** created with type `dropship` -- source = vendor/supplier location, destination = customer
4. **When PO vendor confirms/validates the shipment** -> the receipt is validated and the `stock.move` is marked done, which also marks the Sale Order line as delivered
5. **No stock is held** at the retailer's warehouse at any point

Key linking mechanism: the `stock.move` in the receipt has `sale_line_id` set, which connects it back to the original `sale.order.line`. This enables correct delivered-quantity computation on the sales order.

## Data Files

| File | Purpose |
|------|---------|
| `data/stock_data.xml` | Dropship route, per-company sequence/picking type/rule creation functions |
| `data/stock_dropshipping_demo.xml` | Demo data for testing |
| `views/sale_order_views.xml` | Dropship smart button on SO form |
| `views/purchase_order_views.xml` | Dropship smart button on PO form + picking_type_id domain |
| `views/stock_picking_views.xml` | Dropships filter, dedicated menu, kanban label |

## Dropship Route Configuration

The route record in `stock_data.xml`:

```xml
<record id="route_drop_shipping" model='stock.route'>
    <field name="name">Dropship</field>
    <field name="sequence">20</field>
    <field name="company_id"></field>          <!-- GLOBAL / multi-company -->
    <field name="sale_selectable" eval="True"/>
    <field name="product_selectable" eval="True"/>
    <field name="product_categ_selectable" eval="True"/>
</record>
```

`company_id` is **empty** (global), making the route available across all companies. However, per-company `stock.rule` records are auto-created via `_create_dropship_rule()`, one per company. This means the dropship route is selectable on products in any company, but the rule used for procurement is scoped to the current company via the rule's `company_id`.

## Models

### `sale.order` (Extension)

**File:** `models/sale.py`

| Field | Type | Description |
|-------|------|-------------|
| `dropship_picking_count` | `Integer` (computed) | Count of dropship pickings linked to this SO |

#### `_compute_picking_ids()`

Extends the parent from `sale_stock`. For every confirmed SO, Odoo pre-computes all linked pickings. This extension:

1. Counts dropship pickings: `len(picking_ids.filtered(lambda p: p.is_dropship))`
2. Subtracts that count from `delivery_count` -- so the regular delivery smart button shows **only** non-dropship pickings
3. Stores the dropship count in `dropship_picking_count`

The decrement is critical: without it, both buttons would show the same total count.

#### `action_view_delivery()`

```python
return self._get_action_view_picking(self.picking_ids.filtered(lambda p: not p.is_dropship))
```

Returns the standard delivery action, filtered to exclude dropship pickings. This is a direct override of the inherited smart button target.

#### `action_view_dropship()`

```python
return self._get_action_view_picking(self.picking_ids.filtered(lambda p: p.is_dropship))
```

Returns the dropship-specific action filtered to dropship pickings only. This action is registered in `sale_order_views.xml` as a button positioned **before** `action_view_delivery`.

---

### `sale.order.line` (Extension)

**File:** `models/sale.py`

#### `_compute_is_mto()`

Extends the parent MTO (Make to Order) detection. The parent already checks warehouse-level MTO routes. This extension additionally scans **all** product routes (via `product_id.route_ids` and `product_id.categ_id.total_route_ids`) for any rule whose picking type has:

```python
picking_type.default_location_src_id.usage == 'supplier'
AND
picking_type.default_location_dest_id.usage == 'customer'
```

If found, `is_mto = True` is set on the line. The `.sudo()` call on `picking_type_id` bypasses record rules for the location lookup. The check skips if `line.is_mto` is already `True` (short-circuit) or if `display_qty_widget` is `False` (service product with no stock view).

**Why this matters:** `is_mto` controls whether the sale order line triggers the procurement group / automatic PO creation. Without marking the line as MTO via the dropship route, dropship products might not auto-procure.

#### `_get_qty_procurement()`

Used to compute how much has been procured (i.e., purchased) for this sale line. For dropship:

```python
if any(pol._is_dropshipped() and pol.state != 'cancel' for pol in purchase_lines_sudo)
   and self.product_id == purchase_lines_sudo.product_id:
    qty = sum(
        po_line.product_uom_id._compute_quantity(po_line.product_qty, self.product_uom_id)
        for po_line in purchase_lines_sudo.filtered(lambda r: r.state != 'cancel')
    )
    return qty
```

The `.sudo()` call runs as superuser to allow users without purchase rights to see procurement quantities. The guard `self.product_id == purchase_lines_sudo.product_id` prevents aggregating across kit-type products with dropshipped subcomponents. Returns `0` if the PO line was cancelled.

#### `_compute_product_updatable()`

Overridden to lock the SOL once a linked purchase order line exists, **but only for purchase users**. The parent method locks the line when `purchase_line_count > 0`. This extension adds the same check for purchase users, ensuring the product cannot be changed after a PO has been created from it:

```python
if line.env.user.has_group('purchase.group_purchase_user'):
    if line.purchase_line_count > 0:
        line.product_updatable = False
```

Users without purchase rights can still modify the line (useful for sales-only workflows where purchase rights are not granted).

#### `_purchase_service_prepare_order_values()`

Used when a **service product** with `service_to_purchase = True` is confirmed. This extension adds dropship semantics to the auto-created PO:

```python
dropship_operation = self.env['stock.picking.type'].search([
    ('company_id', '=', res['company_id']),
    ('default_location_src_id.usage', '=', 'supplier'),
    ('default_location_dest_id.usage', '=', 'customer'),
], limit=1, order='sequence')
res['dest_address_id'] = self.order_id.partner_shipping_id.id
res['picking_type_id'] = dropship_operation.id
```

The `order='sequence'` ensures the first (lowest sequence) dropship picking type is chosen in multi-company/multi-warehouse setups. `dest_address_id` is set to the **customer's shipping address**, not the warehouse. The search uses the `company_id` from `res['company_id']` (from the supplierinfo), which avoids cross-company issues.

---

### `purchase.order` (Extension)

**File:** `models/purchase.py`

| Field | Type | Description |
|-------|------|-------------|
| `dropship_picking_count` | `Integer` (computed) | Count of dropship pickings on this PO |

#### `_compute_incoming_picking_count()`

Extends the parent from `purchase` (which computes `incoming_picking_count`). The same subtraction pattern as SO is applied: dropship count is subtracted from `incoming_picking_count` and stored separately in `dropship_picking_count`.

#### `action_view_picking()`

```python
return self._get_action_view_picking(self.picking_ids.filtered(lambda p: not p.is_dropship))
```

Note: This is an **override** of the purchase base action. It excludes dropship pickings from the regular incoming picking button.

#### `action_view_dropship()`

```python
return self._get_action_view_picking(self.picking_ids.filtered(lambda p: p.is_dropship))
```

#### `_prepare_reference_vals()`

Adds `sale_ids` to the stock move's `reference_ids` (stock.reference) when exactly one sale order is linked to the PO:

```python
sale_orders = self.order_line.sale_order_id
if len(sale_orders) == 1:
    res['sale_ids'] = [Command.link(sale_orders.id)]
```

The `stock.reference` record is Odoo's way of tracking cross-document provenance for stock moves. This allows the procurement group to be linked back to the SO from the stock move level.

#### `_is_dropshipped()`

```python
return self.picking_type_id and self.picking_type_id.code == 'dropship'
```

Returns `True` if the PO's picking type is dropship. Used by `sale.order.line._get_qty_procurement()` and `purchase.order.line._is_dropshipped()` as the dropship detection gate.

---

### `purchase.order.line` (Extension)

**File:** `models/purchase.py`

#### `_is_dropshipped()`

```python
return self.order_id._is_dropshipped()
```

Delegates to the parent PO. This method is called by `sale.order.line._get_qty_procurement()` to detect whether the linked purchase line is dropshipped, enabling the dropship procurement quantity aggregation.

---

### `stock.rule` (Extension)

**File:** `models/stock.py`

#### `_get_procurements_to_merge_groupby()`

This is the most architecturally significant override in the module. The base method in `stock.rule` returns a tuple used to decide which procurement orders should be merged into a single purchase order line. The base returns something like `(location_id, partner_id, ...)`.

This override changes the groupby to **sale_line_id**:

```python
return procurement.values.get('sale_line_id'), super()._get_procurements_to_merge_groupby(procurement)
```

**Why this matters for L4 correctness:** Without this change, two SOLs from the same SO with the same product, same vendor, same location could be merged into a single PO line. That would cause the `qty_delivered` on each SOL to be incorrectly computed (they would share the same PO line's quantity). By grouping on `sale_line_id`, each SOL gets its own PO line, and `_get_qty_procurement()` can correctly attribute delivered quantities per line.

**Performance note:** The `sale_line_id` is passed in `procurement.values` when the procurement originates from a sale order line. This requires `sale_purchase_stock` to populate that value during `_run_buy()`.

#### `_get_partner_id()`

```python
route = self.env.ref('stock_dropshipping.route_drop_shipping', raise_if_not_found=False)
if route and rule.route_id == route:
    return False
return super()._get_partner_id(values, rule)
```

For dropship rules, returns `False` for the vendor/partner. The vendor is instead resolved from the product's seller list (the standard `procurement` flow in `_run_buy()`). Returning `False` here prevents the default partner-from-route logic from overriding the vendor selection based on `min_qty` and `delay`.

#### `_compute_picking_type_code_domain()`

```python
if rule.action == 'buy':
    rule.picking_type_code_domain += ['dropship']
```

Adds `'dropship'` to the picking type domain for buy-type rules. This makes dropship picking types available in the stock rule configuration UI when the rule action is "Buy". Without this, the dropship picking type would not appear in the dropdown and users could not configure a dropship-specific rule.

#### `_get_rule_domain()`

```python
if 'sale_line_id' in values and values.get('company_id'):
    domain = Domain.AND([domain, [('company_id', '=', values['company_id'].id)]])
```

Adds a `company_id` filter to the stock rule search when `sale_line_id` is present in procurement values. This ensures that when a procurement originates from a sale order, only rules belonging to the same company are considered. This prevents cross-company procurement rule leakage.

---

### `stock.picking` (Extension)

**File:** `models/stock.py`

| Field | Type | Description |
|-------|------|-------------|
| `is_dropship` | `Boolean` (computed) | `True` when the picking represents a dropship transfer |

#### `_compute_is_dropship()`

```python
picking.is_dropship = (
    source.usage == 'supplier' or (source.usage == 'transit' and not source.company_id)
) and (
    dest.usage == 'customer' or (dest.usage == 'transit' and not dest.company_id)
)
```

**Three conditions for dropship:**

| Source usage | Source company | Dest usage | Dest company | Result |
|---|---|---|---|---|
| `supplier` | any | `customer` | any | `is_dropship = True` |
| `supplier` | any | `transit` | `False` | `is_dropship = True` |
| `transit` | `False` | `customer` | any | `is_dropship = True` |
| `supplier` | any | `customer` | any | `is_dropship = True` |

The `transit` + no-company condition captures **inter-company dropship** scenarios: goods that move through a transit location without an assigned company between the vendor and customer are still treated as dropship transfers. This is relevant for multi-company configurations where a parent company coordinates cross-subsidiary dropships.

The computation depends on `location_dest_id.usage`, `location_dest_id.company_id`, `location_id.usage`, and `location_id.company_id`.

#### `_is_to_external_location()`

```python
return super()._is_to_external_location() or self.is_dropship
```

Returns `True` for dropship pickings in addition to any picking already classified as going to an external location. This affects:
- Transfer validation rules (external transfers may have different validation requirements)
- Reporting and analytics categorization
- The picking's visibility in the Moves to Report dashboard

---

### `stock.picking.type` (Extension)

**File:** `models/stock.py`

| Field | Modification | Description |
|-------|-------------|-------------|
| `code` | Selection add | Added `('dropship', 'Dropship')`; `ondelete={'dropship': ...}` sets `code='outgoing'`, `active=False` on deletion |

#### `_compute_default_location_src_id()`

When a picking type has `code == 'dropship'`, its `default_location_src_id` is forced to `stock.stock_location_suppliers`. This overrides any warehouse-based default. The parent method (called for non-dropship types) uses the warehouse's location logic.

#### `_compute_default_location_dest_id()`

When `code == 'dropship'`, `default_location_dest_id` is forced to `stock.stock_location_customers`. This ensures dropship pickings always have the correct source/destination semantics regardless of the warehouse configuration.

#### `_compute_warehouse_id()`

```python
for picking_type in self:
    if picking_type.code == 'dropship':
        picking_type.warehouse_id = False
```

Dropship picking types are **not associated with any warehouse** (`warehouse_id = False`). This means:
- They do not appear in per-warehouse inventory reports
- They are excluded from warehouse-scoped picking type domains
- They are not affected by warehouse-level route rules

#### `_compute_show_picking_type()`

```python
for record in self:
    if record.code == "dropship":
        record.show_picking_type = True
```

Forces `show_picking_type = True` for dropship codes. The base method's logic may hide some picking type codes from certain UIs; this ensures dropship types are always shown.

#### On Delete Behaviour

If a user (or data migration) deletes a dropship picking type record, the `ondelete` policy sets `code = 'outgoing'` and `active = False` on the record. This prevents orphan pickings and maintains referential integrity. The `uninstall_hook` in `__init__.py` uses this same logic programmatically:

```python
env['stock.picking.type'].search([('code', '=', 'dropship')]).active = False
```

---

### `stock.lot` (Extension)

**File:** `models/stock.py`

#### `_compute_partner_ids()`

For tracked (lot/serial) products delivered via dropship, the lot's `partner_ids` must reflect the **customer** (not the internal warehouse):

```python
lot.partner_ids = list(
    p.sale_id.partner_shipping_id.id if p.is_dropship else p.partner_id.id
    for p in picking_ids
)
```

The base method calls `_find_delivery_ids_by_lot()` to get all picking IDs involving the lot, then sorts them by `date_done` descending. This extension branches on `p.is_dropship` to use the SO's shipping address for dropship pickings instead of the picking's `partner_id` (which would be the vendor).

**L4 security note:** This is critical for lot traceability compliance (e.g., EU FMD). The lot's responsible party must be the entity that owns the goods at the point of the transfer, which in a dropship is the customer (even though the physical goods never touched the retailer's warehouse).

#### `_get_outgoing_domain()`

Extends the lot's outgoing stock moves domain:

```python
return Domain.OR([res, [
    ('location_dest_id.usage', '=', 'customer'),
    ('location_id.usage', '=', 'supplier'),
]])
```

Adds the dropship outgoing domain (supplier -> customer) to the existing outgoing domain. This ensures that lots traced through dropship deliveries are included in outgoing move searches, enabling correct stock reporting for dropshipped tracked products.

---

### `stock.replenish.mixin` (Extension)

**File:** `models/stock_replenish_mixin.py`

#### `_get_allowed_route_domain()`

```python
return Domain.AND([domains, [('id', '!=', self.env.ref('stock_dropshipping.route_drop_shipping').id)]])
```

Excludes the dropship route from the manual replenish wizard's route selection. The replenish wizard (`stock.replenish`) is designed for warehouse replenishment (procure to stock), which is fundamentally incompatible with dropship: dropship has no warehouse involvement, so launching a replenish for a dropship product would create a meaningless procurement. The `raise_if_not_found=False` guard prevents errors if the route is missing.

---

### `res.company` (Extension)

**File:** `models/res_company.py`

Three per-company objects are auto-created when a new company is initialized or when the module is installed for an existing company.

#### `_create_dropship_sequence()`

```python
{
    'name': 'Dropship (%s)' % company.name,
    'code': 'stock.dropshipping',
    'company_id': company.id,
    'prefix': 'DS/',
    'padding': 5,
}
```

Creates a sequence `DS/00001`, `DS/00002`, ... per company. The `code` field is `stock.dropshipping` (distinct from the route's technical name). This sequence is used by the dropship picking type.

#### `_create_dropship_picking_type()`

```python
{
    'name': 'Dropship',
    'company_id': company.id,
    'warehouse_id': False,                              # No warehouse association
    'sequence_id': sequence.id,
    'code': 'dropship',
    'default_location_src_id': stock_location_suppliers,
    'default_location_dest_id': stock_location_customers,
    'sequence_code': 'DS',
    'use_existing_lots': False,                         # Lots not used in dropship by default
}
```

Creates one dropship picking type per company. `use_existing_lots = False` means lot numbers do not need to be pre-created before validating a dropship picking -- new lot names can be entered at validation time.

#### `_create_dropship_rule()`

```python
{
    'name': 'Suppliers → Customers',
    'action': 'buy',
    'location_dest_id': customer_location.id,
    'location_src_id': supplier_location.id,
    'procure_method': 'make_to_stock',
    'route_id': dropship_route.id,
    'picking_type_id': dropship_picking_type.id,
    'company_id': company.id,
}
```

**Critical `procure_method` note:** `make_to_stock` (not `make_to_order`) is used. In the dropship context, "make to stock" means the PO triggers immediate procurement rather than waiting for a sale order confirmation (since the sale order has already been confirmed). The `make_to_stock` procurement method on the dropship rule is what causes the scheduler to immediately create the purchase order when the SO is confirmed.

#### Standalone Migration Functions

Three `@api.model` functions exist to backfill missing records for existing companies (migration safety):

| Function | Use case |
|----------|---------|
| `create_missing_dropship_sequence()` | Called post-install; creates sequences for companies that already existed |
| `create_missing_dropship_picking_type()` | Creates picking types for pre-existing companies |
| `create_missing_dropship_rule()` | Creates rules for pre-existing companies |

These are called twice in `stock_data.xml` (noupdate block) to ensure idempotent execution:
1. Once before the route is defined (creates sequences and picking types)
2. Once after the route is defined (creates the rule, which depends on the route record)

---

### `product.product` (Extension)

**File:** `models/product.py`

#### `_get_description()`

```python
if picking_type_id.code == 'dropship':
    return self.description_pickingout or self.display_name
```

When a dropship picking generates a stock move description, it uses `description_pickingout` (the "description on delivery order" field) rather than the standard description. If `description_pickingout` is empty, it falls back to `display_name`. The parent method (`stock` module) is called for all other picking types. This ensures the vendor-facing delivery description is used for dropship transfers.

---

## Views and UI

### SO Form (`views/sale_order_views.xml`)

The dropship smart button is placed **before** `action_view_delivery`:

```xml
<button name="action_view_dropship" type="object"
    class="oe_stat_button" icon="fa-truck"
    invisible="dropship_picking_count == 0"
    groups="stock.group_stock_user">
    <field name="dropship_picking_count" widget="statinfo" string="Dropship"/>
</button>
```

The `purchase.group_purchase_user` group condition on the `<t>` wrapper means the dropship button is only visible to users who also have purchase rights (relevant because processing a dropship requires viewing/acting on the PO).

### PO Form (`views/purchase_order_views.xml`)

The dropship smart button is placed before `action_view_picking`:

```xml
<button name="action_view_dropship" ...>
```

Additionally, the `picking_type_id` domain is extended to include `dropship`:

```xml
<field name="picking_type_id" domain="[
    ('code', 'in', ('incoming', 'dropship')),
    '|', ('warehouse_id', '=', False), ('warehouse_id.company_id', '=', company_id)
]"/>
```

This allows users to manually select the dropship picking type when creating a PO that should use dropship semantics.

### Picking Search (`views/stock_picking_views.xml`)

A `dropships` named filter is added to `stock.picking` search:

```xml
<filter name="dropships" invisible="1" string="Dropships"
    domain="[('picking_type_code', '=', 'dropship')]"/>
```

A dedicated menu item and window action (`action_picking_tree_dropship`) provide a standalone Dropships view at **Inventory > Operations > Dropships**, accessible to `stock.group_stock_manager` and `stock.group_stock_user`.

The kanban view is patched to show "To Validate" for dropship pickings (matching incoming transfer terminology, since a dropship receipt needs validation).

## Uninstall Hook

```python
def uninstall_hook(env):
    env['stock.picking.type'].search([('code', '=', 'dropship')]).active = False
```

On module uninstall, all dropship picking types are **archived** (not deleted) via `active = False`. This preserves all historical dropship picking records while preventing new dropship operations. The `active=False` approach avoids FK violations from cascade-preventing deletes while still making the picking types invisible in the UI.

## L4: Performance Implications

| Pattern | Implication |
|---------|-------------|
| `is_dropship` computed field | Recomputes on every read of `location_id.usage`, `location_id.company_id`, `location_dest_id.usage`, `location_dest_id.company_id`. The field is cheap (pure boolean from 4 foreign key reads) but called on every picking browse. |
| `_get_procurements_to_merge_groupby` override | Adding `sale_line_id` as the primary groupby key means more granular PO line splitting. In high-volume scenarios with many SOLs, this creates more PO lines but ensures correct delivered qty attribution. |
| `_purchase_service_prepare_order_values` search | A `search()` call with `order='sequence'` on `stock.picking.type` is executed per service line confirmation. If a company has many picking types, this could be a minor bottleneck. The `limit=1` mitigates this. |
| `dropship_picking_count` subtraction from `delivery_count` | The `delivery_count` on SO and `incoming_picking_count` on PO both require filtering and counting all linked pickings. On SOs/POs with many pickings, this is an O(n) operation that runs in the `compute` method. |
| `_compute_partner_ids()` on `stock.lot` | Sorts all pickings for a lot by `date_done` descending and iterates to build partner list. For lots with many deliveries, this could be slow. The `_find_delivery_ids_by_lot()` base method uses a raw SQL join for efficiency. |

## L4: Edge Cases

### Multi-vendor with different pricing/delays

If a product has multiple sellers with different `min_qty`, `delay`, and `price` values, and the dropship route is set:
- The procurement rule selects the **lowest total cost** vendor that meets `min_qty` at the time of order (standard Odoo vendor selection logic)
- `date_planned` on the PO is set based on the selected vendor's `delay` (tested in `test_correct_vendor_dropship`)

### Dropship + Subcontracted Service on same PO

A PO created from a subcontracted service SO can have a dropship product manually added (tested in `test_add_dropship_product_to_subcontracted_service_po`). When the PO is confirmed, the dropship line creates its own dropship picking. The SO line for the service product is unaffected by the dropship picking. The dropship SOL gets a new auto-created SOL entry on the SO when the picking is processed.

### Return of a Dropship Picking

A return from a dropship picking is created as a new picking (reverse transfer). The return picking **is also a dropship** (source = customer, dest = vendor). When validated, it correctly decrements both `qty_delivered` on the SOL and `qty_received` on the original POL (tested in `test_sol_reserved_qty_wizard_dropship` and `test_return_dropship_vendor_is_other_company`).

### MTSO + Dropship on same product

When a product has both a warehouse MTSO route and a dropship route, and the product has existing stock:
- The MTSO route handles the "in stock" portion (creates internal delivery only)
- The dropship route handles the "shortfall" portion (creates dropship PO)
- The two are separate procurement orders and do not interfere (tested in `test_non_dropship_mtso_unaffected_by_dropship_logic`)

### Lot-tracked dropship product

When a dropship product uses `tracking = 'lot'`:
- The lot's `partner_ids` correctly reflects the **customer** (via `_compute_partner_ids()`), not the vendor
- The `stock.lot` record is created at picking validation time
- Lot serial number search via the customer's `action_view_stock_serial()` includes dropship lots (tested in `test_search_lot_partner_from_dropship`)

### Inter-company dropship

If the vendor belongs to a different company than the retailer (`test_return_dropship_vendor_is_other_company`), the dropship flow still works: the PO is created, confirmed, and the dropship picking is processed. The return flow also works correctly.

### PO picking type changed to dropship after creation

If a PO is created with a regular incoming picking type but the user manually changes `picking_type_id` to a dropship type, the subsequent picking will be classified as `is_dropship = True` (because its source/dest locations match the dropship pattern). This will also affect the `dropship_picking_count` on the SO.

### Kit (phantom) products with dropship components

The `_get_qty_procurement()` guard `self.product_id == purchase_lines_sudo.product_id` prevents dropshipped kit subcomponents from being aggregated into the kit's SOL delivered quantity. This ensures kit lines are not falsely credited with dropship deliveries.

## L4: Historical Changes (Odoo 17 → 19)

| Area | Change |
|------|--------|
| `is_dropship` field | Previously the dropship indicator was derived from picking type code alone. Odoo 19 introduced the `is_dropship` computed boolean on `stock.picking` to support dropship detection based on location semantics (including transit locations), not just the picking type code. |
| `_get_procurements_to_merge_groupby` | This override existed in earlier versions but was updated in Odoo 19 to properly handle the `sale_line_id`-based grouping that enables per-line delivered quantity computation. |
| Stock valuation tests | `test_stockvaluation.py` and `test_purchase_order.py` contain `@skip('Temporary to fast merge new valuation')` decorators, indicating ongoing changes to the Anglo-Saxon valuation layer for dropship pickings in Odoo 19. The dropship flow's interaction with `stock_account` (valuation entries from dropship receipts) is actively being refined. |
| `stock.lot._compute_partner_ids` | Extended in Odoo 19 to handle dropship lots correctly (previously the base method only handled warehouse partner logic). |

## Security Considerations

| Aspect | Detail |
|--------|--------|
| Smart button visibility | The dropship smart button on SO requires both `purchase.group_purchase_user` (for the button wrapper) AND `stock.group_stock_user` (for the button itself). This ensures non-purchase users see only the dropship count if they have stock rights, and purchase users see it as well. |
| `sudo()` in `_get_qty_procurement` | Uses `self.sudo().purchase_line_ids` to allow users without purchase rights to see dropship procurement quantities. This is a deliberate privilege elevation scoped to the single operation. |
| `sudo()` in `_compute_is_mto` | Uses `pull_rule.picking_type_id.sudo()` to read picking type locations without ACL enforcement. This avoids access errors when a sales user does not have read rights on picking types. |
| Per-company rule domain | `_get_rule_domain` adds `company_id` filter to prevent cross-company rule selection when a procurement originates from a sale order with a company context. |

## Related

- [Modules/sale_purchase_stock](modules/sale_purchase_stock.md) -- Provides the SO->PO->Stock procurement chain that drives dropship
- [Modules/Stock](modules/stock.md) -- Base warehouse, location, and inventory management
- [Modules/Purchase](modules/purchase.md) -- Purchase order management
- [Modules/Sale](modules/sale.md) -- Sale order management
- [Modules/mrp_subcontracting_dropshipping](modules/mrp_subcontracting_dropshipping.md) -- Subcontracting combined with dropshipping
- [Modules/stock_account](modules/stock_account.md) -- Valuation layer; dropship receipts create valuation entries
