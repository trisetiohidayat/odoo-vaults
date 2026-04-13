---
type: module
module: mrp_subcontracting_dropshipping
tags: [odoo, odoo19, mrp, subcontracting, dropshipping, purchase]
created: 2026-04-06
updated: 2026-04-11
---

# MRP Subcontracting Dropshipping

## Overview
| Property | Value |
|----------|-------|
| **Name** | Dropship and Subcontracting Management |
| **Technical** | `mrp_subcontracting_dropshipping` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Category** | Supply Chain/Purchase |
| **Version** | 0.1 |
| **Auto-install** | `True` |

## Description

A **bridge module** that unifies `mrp_subcontracting` and `stock_dropshipping` into a single coordinated flow. It enables two simultaneous dropship legs:

1. **Component dropship**: Components needed by a subcontractor are dropshipped from an external vendor directly to the subcontractor's receiving location.
2. **Finished-goods dropship**: The completed subcontracted product is dropshipped from the subcontractor directly to the end customer.

Both legs are triggered by a single Purchase Order (PO) or Sale Order (SO) confirmation. The module manages the cross-talk between purchase rules, stock moves, and subcontracting manufacturing orders so that all three parties (vendor, subcontractor, customer) are correctly wired.

## Dependencies

```
depends = ['mrp_subcontracting', 'stock_dropshipping']
```

Both dependencies are themselves framework modules, not business-specific. The auto-install flag means this module activates automatically when both dependencies are present.

## Architecture

This module does **not** define its own concrete models. It extends nine existing models across `stock`, `purchase`, `mrp`, and `res.company` to handle the combined flow. The core logic lives in:

- `stock.rule` / `stock.move` — routing decisions for dropship+subcontract combinations
- `purchase.order` — PO-level destination address logic for subcontracting dropship pickings
- `stock.picking` — computing `is_dropship` for subcontracted delivery pickings
- `stock.warehouse` — activating/deactivating the "Dropship Subcontractor on Order" global route per warehouse
- `res.company` — creating per-company picking types, sequences, and rules on first install

## Models Extended

---

### `stock.move` — `models/stock_move.py`

Extends the dropship identity predicates to cover the subcontracting location as a dropship endpoint.

#### `_is_dropshipped()`
```python
def _is_dropshipped(self)
```
**Logic**: Returns `True` if the move originates from a subcontracting location and terminates at a customer location.

The check uses `parent_path` prefix matching rather than direct ID comparison:
```
partner_id.property_stock_subcontractor.parent_path in location_id.parent_path
and location_dest_id.usage == 'customer'
```
This works even when the subcontractor has a **sub-location** under the canonical company subcontracting location — the `parent_path` prefix match captures the hierarchy.

**L3 — Why parent_path?** Direct Many2one comparison would break if a partner's `property_stock_subcontractor` is a custom sub-location (e.g., `Subcontracting/Semifinal/A`). Using `parent_path` prefix matching handles arbitrary depth.

**L3 — Dropshipped from subcontractor to customer**: This covers the finished-goods dropship leg. When a PO with a dropship picking type and a customer `dest_address_id` is confirmed, the resulting stock move is flagged as dropshipped so Odoo treats it like a vendor→customer delivery.

#### `_is_dropshipped_returned()`
```python
def _is_dropshipped_returned(self)
```
**Logic**: Returns `True` for return moves where the destination is a subcontracting location and the origin is `customer`. This enables correct return-to-subcontractor processing (e.g., a customer returns a dropshipped finished good, which goes back to the subcontractor).

#### `_is_purchase_return()`
```python
def _is_purchase_return(self)
```
Overrides the parent method to also consider `_is_dropshipped_returned()` as a purchase return path. This is required so that return-to-subcontractor moves are treated as inverse purchase receipts, correctly adjusting `qty_received` on the PO line.

---

### `stock.picking` — `models/stock_picking.py`

#### `_compute_is_dropship()`
```python
def _compute_is_dropship(self)
```
**Override pattern**: Pre-filters pickings where `location_dest_id.is_subcontract()` is `True` AND `location_id.usage == 'supplier'` — these are dropship pickings where the subcontractor acts as the supplier delivering directly to the customer (no intermediate warehouse receipt).

These are assigned `is_dropship = True` **before** calling `super()`, so the parent computation only runs on the remaining non-subcontract picks. This ensures subcontracted dropship pickings are correctly flagged without being overwritten.

**L3 — Why pre-filter?** The base `_compute_is_dropship()` resets the flag for all records. By assigning the correct value before calling `super()`, the override wins.

#### `_get_warehouse(subcontract_move)`
```python
def _get_warehouse(self, subcontract_move)
```
**Override pattern**: If the subcontract move has a `sale_line_id`, the warehouse is taken from `sale_line_id.order_id.warehouse_id` instead of the default heuristic. This ensures the correct warehouse is used when a subcontracting MO is generated from a sale order that routes to a specific dropship warehouse.

#### `_prepare_subcontract_mo_vals(subcontract_move, bom)`
```python
def _prepare_subcontract_mo_vals(self, subcontract_move, bom)
```
**Override pattern**: Fills in the missing `picking_type_id` on the subcontracting MO vals dict when the move destination is `customer` (dropship destination) or a subcontracting location (no warehouse assignment).

**L3 — Failure mode it solves**: Without this, confirming a PO with a subcontracted product that should be dropshipped to a customer (no warehouse receipt planned) would leave `picking_type_id` blank on the MO, causing a `ValidationError` when Odoo tries to assign a picking type.

```python
if not res.get('picking_type_id') and (
        subcontract_move.location_dest_id.usage == 'customer'
        or subcontract_move.location_dest_id.is_subcontract()
):
    default_warehouse = self.env['stock.warehouse'].search(
        [('company_id', '=', subcontract_move.company_id.id)], limit=1
    )
    res['picking_type_id'] = default_warehouse.subcontracting_type_id.id
```

---

### `purchase.order` — `models/purchase.py`

Extends the PO form to handle the subcontracting dropship destination address.

#### `default_location_dest_id_is_subcontracting_loc`
```
type: Boolean (computed)
depends: picking_type_id.default_location_dest_id
```
**L2 — Field type**: Read-only computed boolean. Returns `True` when the PO's picking type's default destination location is a subcontracting location (i.e., `is_subcontract()` returns `True`).

This field is stored in the view as an `invisible="1"` field so it can drive visibility and requiredness of `dest_address_id`.

#### `_compute_dest_address_id()`
```python
@api.depends('default_location_dest_id_is_subcontracting_loc')
def _compute_dest_address_id(self)
```
**Override pattern**: When `default_location_dest_id_is_subcontracting_loc` is `True` and exactly **one** subcontractor is associated with the destination location's picking type, the `dest_address_id` is auto-populated with that subcontractor.

```python
dropship_subcontract_pos = self.filtered(
    lambda po: po.default_location_dest_id_is_subcontracting_loc
)
for order in dropship_subcontract_pos:
    subcontractor_ids = order.picking_type_id.default_location_dest_id.subcontractor_ids
    if len(subcontractor_ids) == 1:
        order.dest_address_id = subcontractor_ids
super(PurchaseOrder, self - dropship_subcontract_pos)._compute_dest_address_id()
```

**L3 — Why `len(subcontractor_ids) == 1`?** Auto-populating with a single unambiguous subcontractor prevents accidentally assigning the wrong partner. When multiple subcontractors share the same subcontracting location, the user must manually set `dest_address_id`.

**L3 — Unusual pattern**: This method both reads from and writes to `dest_address_id` within the same compute. Odoo's ORM allows this in a compute method as long as the field being written is the field being computed (not a cross-field dependency loop).

#### `onchange_picking_type_id()`
```python
@api.onchange('picking_type_id')
def onchange_picking_type_id(self)
```
**L2 — Trigger**: Fires when the user changes the picking type on a PO. If the new picking type routes to a subcontracting location, displays a warning:
```
"Please note this purchase order is for subcontracting purposes."
```
This is a user-facing alert, not a blocking constraint.

#### `_get_destination_location()`
```python
def _get_destination_location(self)
```
**Override pattern**: When `default_location_dest_id_is_subcontracting_loc` is `True`, returns the subcontractor's `property_stock_subcontractor` location instead of the default picking-type destination.

```python
if self.default_location_dest_id_is_subcontracting_loc:
    return self.dest_address_id.property_stock_subcontractor.id
return super()._get_destination_location()
```

**L3 — Purpose**: Ensures that dropship component POs (POs created by stock rules to supply the subcontractor) have their destination set to the subcontractor's dedicated stock location, not a generic picking-type default. This is critical for the stock move `_is_dropshipped()` predicate to work correctly.

---

### `stock.rule` — `models/stock_rule.py`

#### `_prepare_purchase_order(company_id, origins, values)`
```python
def _prepare_purchase_order(self, company_id, origins, values)
```
**Override pattern**: When creating a PO for a component to be dropshipped to a subcontractor, if no `partner_id` is set in `values[0]` and the rule's `location_dest_id` is a subcontracting location (or its parent path contains the company subcontracting location), the method reaches back to the destination MO to pull the `subcontractor_id`.

```python
if not values[0].get('partner_id') \
    and (company_id.subcontracting_location_id.parent_path in self.location_dest_id.parent_path
         or self.location_dest_id.is_subcontract()):
    move = values[0].get('move_dest_ids')
    if move and move.raw_material_production_id.subcontractor_id:
        values[0]['partner_id'] = move.raw_material_production_id.subcontractor_id.id
```

**L3 — Chain traversal**: `move_dest_ids` is the stock move that triggered this rule (the MO component move). From there, `raw_material_production_id` is the parent MO. This chain is only valid for subcontracting MOs where components are consumed.

**L4 — Performance**: This does a reverse lookup via `move_dest_ids` at PO creation time. If `move_dest_ids` is a large recordset, iterating it could be expensive. The code defensively assumes `values[0]` is the leading value dict.

#### `_make_po_get_domain(company_id, values, partner)`
```python
def _make_po_get_domain(self, company_id, values, partner)
```
**Override pattern**: When the rule is a dropship-to-subcontractor rule (`location_src_id.usage == 'supplier'` AND `location_dest_id.is_subcontract()`), adds a `dest_address_id` filter to the PO merge domain:

```python
if self.location_src_id.usage == 'supplier' \
   and self.location_dest_id.is_subcontract() \
   and values.get('partner_id', False):
    domain += (('dest_address_id', '=', values.get('partner_id')),)
```

**L3 — Purpose**: Prevents PO merging across different subcontractors. Normally, Odoo merges PO lines for the same product/vendor. But when dropshipping components to specific subcontractors, you need separate POs per subcontractor. Adding `dest_address_id` to the domain breaks the merge for different subcontractors.

---

### `stock.warehouse` — `models/stock_warehouse.py`

Manages the "Dropship Subcontractor on Order" global route and its per-warehouse pull rule.

#### `subcontracting_dropshipping_pull_id`
```
type: Many2one(stock.rule)
name: Subcontracting-Dropshipping MTS Rule
copy: False
```
A warehouse-level pull rule on the `Dropship` route (`stock_dropshipping.route_drop_shipping`). Created by `_generate_global_route_rules_values()` and managed by `_update_dropship_subcontract_rules()`.

**Rule values**:
| Field | Value |
|-------|-------|
| `procure_method` | `make_to_order` |
| `action` | `pull` |
| `auto` | `manual` |
| `route_id` | `stock_dropshipping.route_drop_shipping` |
| `location_src_id` | Subcontracting location |
| `location_dest_id` | Production location |
| `picking_type_id` | Warehouse's `subcontracting_type_id` |

#### `_generate_global_route_rules_values()`
Extends the parent's global route generation to add the `subcontracting_dropshipping_pull_id` rule. The rule is `make_to_order` (MTO) because components dropshipped to a subcontractor must be procured exactly when the MO demands them.

#### `create(vals_list)` / `write(vals)`
Warehouse creation/update triggers route activation logic. When `subcontracting_to_resupply` is set to `True` on any warehouse, the module calls `update_global_route_dropship_subcontractor()` to activate the global route.

**L3 — `subcontracting_to_resupply`**: This is a warehouse flag (inherited from `mrp_subcontracting`) that controls whether the warehouse's subcontracting location should receive dropshipped components. Setting it to `True` on any warehouse activates the Dropship Subcontractor route globally.

#### `_update_dropship_subcontract_rules()`
```python
def _update_dropship_subcontract_rules(self)
```
**L3 — Archive/unarchive logic**: When a warehouse toggles `subcontracting_to_resupply`, this method:
- Unarchives pull rules for warehouses **with** the flag
- Archives pull rules for warehouses **without** the flag
- Only affects rules where `action == 'pull'` and `location_src_id` is a subcontracting location

This avoids creating/deleting rules and instead toggles `active`, which preserves rule configuration.

#### `update_global_route_dropship_subcontractor()`
```python
def update_global_route_dropship_subcontractor(self)
```
**L3 — Route activation cascade**:
1. For each company, checks if any active `pull` rules exist for that company. Sets `company.dropship_subcontractor_pick_type_id.active` accordingly.
2. Sets `route_id.active` to `True` only if at least one active `pull` rule exists anywhere.

**L4 — Global route vs. per-company picking type**: The `Dropship Subcontractor on Order` route is a global (company-independent) route, but the picking type (`dropship_subcontractor_pick_type_id`) is per-company. This method keeps both in sync.

---

### `res.company` — `models/res_company.py`

Creates and manages per-company infrastructure for dropship-subcontract operations.

#### `dropship_subcontractor_pick_type_id`
```
type: Many2one(stock.picking.type)
```
Points to the company's dropship subcontractor picking type. Created by `_create_subcontracting_dropshipping_picking_type()`.

**Picking type values**:
| Field | Value |
|-------|-------|
| `name` | `Dropship Subcontractor` |
| `code` | `dropship` |
| `default_location_src_id` | `stock.stock_location_suppliers` (vendor) |
| `default_location_dest_id` | `company.subcontracting_location_id` |
| `use_existing_lots` | `False` |
| `sequence_code` | `DSC` |

The sequence uses prefix `DSC/` (e.g., `DSC/00001`).

#### `_create_subcontracting_dropshipping_rules()`
Creates a `stock.rule` on the `stock_dropshipping.route_drop_shipping` route with:
- `action = 'buy'`
- `location_src_id = stock_location_suppliers`
- `location_dest_id = company.subcontracting_location_id`
- `procure_method = make_to_stock`
- `picking_type_id` = the dropship picking type found for this company (supplier source, subcontracting destination)

**L3 — Why `make_to_stock` for the company-level rule?** This rule is used when the company-level dropship route is triggered from a warehouse without a specific subcontracting-dropshipping rule. It represents buying from any supplier and having goods drop-shipped to the company's central subcontracting location.

#### `_create_missing_*` (API model methods)

Three `@api.model` methods called at install time via `mrp_subcontracting_dropshipping_data.xml`:

- `_create_missing_subcontracting_dropshipping_sequence()`: Creates sequences for companies that don't have one.
- `_create_missing_subcontracting_dropshipping_picking_type()`: Creates picking types for companies that don't have a dropship picking type pointing to their subcontracting location.
- `_create_missing_subcontracting_dropshipping_rules()`: Creates rules for companies that have the dropship route but not the subcontracting-specific rule.

These are idempotent safe nets for multi-company setups where new companies are added after module installation.

#### `_create_per_company_*` (Override hooks)

- `_create_per_company_sequences()`: Adds the dropship subcontracting sequence alongside the parent's per-company sequence creation.
- `_create_per_company_rules()`: Adds the dropship subcontracting rule alongside the parent's per-company rule creation.
- `_create_per_company_picking_types()`: Adds the dropship subcontractor picking type alongside the parent's per-company picking type creation.

---

### `stock.orderpoint` (a.k.a. `stock.warehouse.orderpoint`) — `models/stock_orderpoint.py`

#### `_prepare_procurement_values(date=False)`
```python
def _prepare_procurement_values(self, date=False)
```
**Override pattern**: When an orderpoint triggers for a subcontracting location with exactly one subcontractor, pre-populates `partner_id` in the procurement values:

```python
if not vals.get('partner_id') \
   and self.location_id.is_subcontract() \
   and len(self.location_id.subcontractor_ids) == 1:
    vals['partner_id'] = self.location_id.subcontractor_ids.id
```

**L3 — Purpose**: Without this, the stock rule's `_prepare_purchase_order()` would not know which vendor to use for resupplying the subcontractor. By injecting `partner_id` at the orderpoint level, the entire procurement chain gets the correct vendor.

**L4 — Edge case — multiple subcontractors**: When `len(subcontractor_ids) > 1`, the field is left blank, and the standard vendor selection logic (via `product.supplierinfo`) applies. This is correct because the orderpoint cannot make a unambiguous choice.

---

### `stock.replenish.mixin` — `models/stock_replenish_mixin.py`

#### `_get_allowed_route_domain()`
```python
def _get_allowed_route_domain(self)
```
**Override pattern**: Excludes the plain `route_drop_shipping` route (Dropship) from the replenish mixin's route selection dropdown. The mixin is used in the manual replenishment UI; excluding the plain dropship route prevents users from accidentally triggering a standalone dropship from this interface.

```python
domains = super()._get_allowed_route_domain()
return Domain.AND([
    domains,
    [('id', '!=', self.env.ref('stock_dropshipping.route_drop_shipping').id)]
])
```

**L3 — Why exclude only `route_drop_shipping`?** The `stock_dropshipping` module defines the "Dropship" route. The dropship-subcontracting logic instead uses the "Dropship Subcontractor on Order" global route (also in `stock_dropshipping`). Only the plain vendor→customer dropship route is excluded; the subcontracting-aware route is not.

---

## Data Files

### `data/mrp_subcontracting_dropshipping_data.xml`

Post-install data (noupdate=1) that bootstraps the module on existing databases:

```xml
<function model="res.company" name="_create_missing_subcontracting_dropshipping_sequence"/>
<function model="res.company" name="_create_missing_subcontracting_dropshipping_picking_type"/>
<function model="res.company" name="_create_missing_subcontracting_dropshipping_rules"/>
```

Also forces all existing warehouses to have `subcontracting_to_resupply = True`:
```xml
<function model="stock.warehouse" name="write">
    <value eval="obj().env['stock.warehouse'].search([]).ids"/>
    <value eval="{'subcontracting_to_resupply': True}"/>
</function>
```

**L4 — Why force `subcontracting_to_resupply = True`?** This module only makes sense when the subcontracting-to-resupply flow is enabled on warehouses. Setting it to `True` on all existing warehouses ensures the Dropship Subcontractor route is activated immediately after install without requiring manual configuration.

### `views/purchase_order_views.xml`

Extends `purchase.order.form` to manage `dest_address_id` visibility in the dropship-subcontract context:

```xml
<field name="default_location_dest_id_is_subcontracting_loc" invisible="1"/>

<field name="dest_address_id" position="attributes">
    <attribute name="invisible">
        default_location_dest_id_usage != 'customer'
        and not default_location_dest_id_is_subcontracting_loc
    </attribute>
    <attribute name="required">
        default_location_dest_id_usage == 'customer'
        or default_location_dest_id_is_subcontracting_loc
    </attribute>
</field>
```

**L3 — Visibility logic**:
- `dest_address_id` is **required** when the destination is a customer (standard dropship) OR when the destination is a subcontracting location (dropship-subcontract PO).
- `dest_address_id` is **invisible** only when it's neither a customer nor a subcontracting destination (i.e., a normal PO to stock).

---

## Complete Flow Walkthrough

### Scenario: Subcontracted product with dropshipped components, delivered direct to customer

**Setup**:
- Product `P` (finished, subcontracted) with a BOM containing Component `C`
- `C` has route: `Dropship` + vendor `V`
- `P` has route: `Dropship` + subcontractor `S` as vendor
- SO or PO created for `P` to `S`, delivered to customer `X`

**Step 1 — PO/SO confirmation**:
- PO line for `P` → `S` triggers `stock.rule` on `Dropship` route
- `stock.picking` created: supplier `S` → customer `X` (the finished-goods dropship leg)
- `stock.move` flagged as `_is_dropshipped()` = `True`
- `_prepare_subcontract_mo_vals()` ensures MO gets a valid `subcontracting_type_id`

**Step 2 — MO created**:
- Subcontracting MO for `P` created, state `confirmed`
- MO's component move for `C` triggers the `stock_dropshipping` buy rule
- `_prepare_purchase_order()` detects subcontracting context, injects `subcontractor_id` from MO
- `_make_po_get_domain()` adds `dest_address_id` filter → separate PO per subcontractor

**Step 3 — Component PO confirmed**:
- PO for `C` from vendor `V`, destination = `S.property_stock_subcontractor`
- `_get_destination_location()` on PO returns `S.property_stock_subcontractor`
- `stock.picking` created: supplier `V` → subcontractor's stock location

**Step 4 — Delivery to subcontractor**:
- Vendor ships `C` directly to `S`
- `stock.picking` (component delivery) validated

**Step 5 — Subcontractor ships to customer**:
- `stock.picking` (finished goods dropship) validated
- MO state → `done`
- PO `qty_received` for `P` updated

**Step 6 — Returns**:
- Return to stock: `_is_dropshipped_returned()` = `False` (customer → stock), normal return flow
- Return to subcontractor: `_is_dropshipped_returned()` = `True` (customer → subcontractor location), adjusts `qty_received`

---

## Test Suite

Tests live in `tests/` and are organized into three files. Note: two test classes are currently `@skip`ed pending Odoo 19's new valuation layer rewrite.

### `test_purchase_subcontracting.py`

| Test | Scenario |
|------|----------|
| `test_mrp_subcontracting_dropshipping_1` | SO confirmation with dropship finished product + MTO/Buy/Replenish component routes. Verifies finished-goods dropship PO and component delivery to subcontractor. (SKIPPED) |
| `test_mrp_subcontracting_purchase_2` | PO to subcontractor with resupply-on-order component; qty change from 1→2 on PO line propagates correctly to a single resupply delivery. |
| `test_dropshipped_component_and_sub_location` | Component dropshipped to a subcontractor's sub-location. Verifies PO `dest_address_id` is set to the subcontractor partner (not the location). |
| `test_po_to_customer` | PO with dropship picking type and customer destination. Validates MO picking type assignment, delivery processing, and two return paths (return-to-stock and return-to-supplier). |
| `test_po_to_subcontractor` | PO with `dropship_subcontractor_pick_type_id` (Dropship Subcontractor) and `dest_address_id` = super-subcontractor. Verifies the finished product is correctly dropshipped to the super-subcontractor's `property_stock_subcontractor` location and flagged as `is_dropship`. |
| `test_two_boms_same_component_supplier` | Two subcontracted products from different subcontractors sharing a component with its own vendor. When `group_propagation_option = 'none'` on the buy rule, verifies separate POs are created per subcontractor (PO merge prevented by `dest_address_id` domain filter). |
| `test_subcontracted_bom_routes` | BoM report route display: verifies that for subcontracted BoMs, a `Dropship`-routed component shows "Dropship" route in the report (not "Buy"), while for non-subcontracted BoMs the same component shows "Buy". |
| `test_partner_id_no_overwrite` | Resupply orderpoint with a manually-set `partner_address_id` on the rule. Verifies the scheduler uses the rule's address, not the first subcontractor alphabetically. |
| `test_portal_subcontractor_record_production_with_dropship` | Portal subcontractor can set serial numbers on finished product with dropshipped components. Verifies the dropship picking type is `dropship_subcontractor_pick_type_id` and is linked to the subcontracted MO's picking. (SKIPPED — but partially) |
| `test_shared_purchase_from_so` | Two SOs with different finished products sharing a common MTO component from a single vendor. Verifies that a single PO with one line is created for qty=4 total, and that `move_dest_ids.production_group_id` correctly links to both MOs. |

### `test_sale_dropshipping.py`

Tests the phantom-kit-with-dropship-component interaction. These tests are not skips and cover the `mrp_subcontracting_dropshipping` → `stock_dropshipping` interaction at the kit level:

| Test | Scenario |
|------|----------|
| `test_dropship_with_different_suppliers` | Kit with 3 dropshipped components from 3 vendors. Canceling one vendor's picking should mark the kit as fully delivered (all-or-nothing qty_delivered policy). |
| `test_return_kit_and_delivered_qty` | Kit delivered then returned, then re-delivered. `qty_delivered` correctly reflects 1.0 at each step. |
| `test_partial_return_kit_and_delivered_qty` | Complex multi-pick sequence with backorders and partial returns; final `qty_delivered` should be 1.0. |
| `test_cancelled_picking_and_delivered_qty` | All pickings cancelled → `qty_delivered` = 0. |
| `test_sale_kit_with_dropshipped_component` | Kit with one dropshipped + one regular component. Both deliveries processed → `qty_delivered` = 1.0. |
| `test_kit_dropshipped_change_qty_SO` | SO qty changed from 25→10 after PO lines created. Both PO lines update to 10. |
| `test_dropship_move_lines_have_bom_line_id` | Verifies `bom_line_id` is correctly set on stock moves for dropshipped kit components. |

### `test_anglo_saxon_valuation.py`

Tests real-time valuation through the dropship-subcontract flow. Both tests are `@skip`'d pending the Odoo 19 valuation rewrite:

| Test | Scenario |
|------|----------|
| `test_valuation_subcontracted_and_dropshipped` | FIFO-auto subcontracted product dropshipped to customer. Validates the AML sequence: dropship compensation → subcontractor receipt → component delivery → initial dropship value. Tests return-to-subcontractor and return-to-stock AMLs. |
| `test_avco_valuation_subcontract_and_dropshipped_and_backorder` | AVCO-auto, backorder on dropship transfer, invoice-per-delivery. Validates SVL values across two dropship transfers with accurate per-quantity costs. |
| `test_account_line_entry_kit_bom_dropship` | Phantom kit with two components (one storable, one product_c), both dropshipped. Manual PO cost edits reflected in expense account entries on the vendor bill. |

---

## Odoo 18 → Odoo 19 Changes

Key changes relevant to this module in the Odoo 18→19 transition:

| Area | Change |
|------|--------|
| **Valuation layer** | The Anglo-Saxon valuation code is being rewritten. Two test classes (`TestSubcontractingDropshippingFlows` and `TestSubcontractingDropshippingValuation`) are `@skip`'d with comment `"Temporary to fast merge new valuation"`. This indicates the valuation AML/SVL logic is expected to change in Odoo 19. |
| **`is_storable`** | In Odoo 19, `is_storable` replaces `type == 'product'` as the storable product discriminator. The test files use `is_storable = True` in product definitions. |
| **`stock.replenish.mixin`** | New in `stock`; this module extends it to filter out the plain dropship route from manual replenishment. |
| **Portal subcontractor support** | `test_portal_subcontractor_record_production_with_dropship` validates that portal subcontractors can assign serial numbers to finished products even when components are dropshipped. |
| **`make_to_order` for dropship-pull rule** | The `subcontracting_dropshipping_pull_id` rule in `stock.warehouse` uses `procure_method = make_to_order`, ensuring component dropship moves are triggered precisely when the MO demands them rather than by minimum stock rules. |

---

## Security Considerations

- **Field-level**: `dest_address_id` on a PO controls where dropship pickings terminate. Users with PO write access can redirect dropship deliveries — this should be restricted to procurement managers.
- **Record rules**: No custom `ir.rule` records are defined; security relies on the base `purchase.order` and `stock.picking` access groups.
- **Portal access**: Subcontractors with portal access can view and validate pickings linked to their `property_stock_subcontractor` location. The `test_portal_subcontractor_record_production_with_dropship` test verifies that portal lot assignment works correctly.
- **Multi-company**: The `_create_missing_*` idempotent methods respect `company_id` scoping. Rules and picking types are created per company, preventing cross-company leaks.

---

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Multiple subcontractors at same location** | `_compute_dest_address_id()` and `_prepare_procurement_values()` both require exactly one subcontractor; otherwise they leave the field/value blank for manual selection. |
| **Subcontractor with custom sub-location** | `_is_dropshipped()` uses `parent_path` prefix matching so the dropship identity check works for any depth of subcontracting location. |
| **PO merge across subcontractors** | `_make_po_get_domain()` adds `dest_address_id` to the merge domain, ensuring different subcontractors get separate POs even for the same product/vendor. |
| **No warehouse assignment (PO to customer)** | `_prepare_subcontract_mo_vals()` searches for any warehouse in the company to borrow `subcontracting_type_id` when the move goes directly to `customer`. |
| **Component vendor mismatch** | The `stock.route` `group_propagation_option = 'none'` on the buy rule (tested in `test_two_boms_same_component_supplier`) forces separate PO lines per subcontractor destination, preventing incorrect vendor assignment. |
| **Anglo-Saxon valuation with backorder** | The `test_avco_valuation_subcontract_and_dropshipped_and_backorder` test verifies that SVL values are correctly split across backordered quantities when the dropship transfer is split. |
| **Dropship kit with cancelled component picking** | `test_dropship_with_different_suppliers` confirms the all-or-nothing `qty_delivered` policy handles cancellations correctly for phantom kits. |

---

## Related Modules

- [Modules/mrp_subcontracting](Modules/mrp_subcontracting.md) — Core subcontracting MO management; this module is the direct parent
- [Modules/stock_dropshipping](Modules/stock_dropshipping.md) — Core dropship routing; provides `route_drop_shipping` and dropship rule logic
- [Modules/mrp_subcontracting_purchase](Modules/mrp_subcontracting_purchase.md) — Subcontracting PO to subcontractor (no dropship)
- [Modules/mrp_subcontracting_account](Modules/mrp_subcontracting_account.md) — Subcontracting valuation and bill processing
- [Modules/Stock](Modules/Stock.md) — `stock.move`, `stock.picking`, `stock.rule`, `stock.warehouse`, `stock.location`
- [Modules/Purchase](Modules/Purchase.md) — `purchase.order`, `purchase.order.line`
