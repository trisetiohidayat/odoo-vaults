# stock_dropshipping — Dropship Supply Chain Integration

**Module:** `stock_dropshipping`
**Odoo Version:** 18
**Source:** `~/odoo/odoo18/odoo/addons/stock_dropshipping/`

---

## Overview

The `stock_dropshipping` module enables dropship workflows — purchasing products from a supplier and having them shipped directly to the customer, bypassing the seller's warehouse entirely. It extends stock rules, procurement groups, stock pickings, and sale/purchase order models to recognize and handle dropship operations.

---

## Architecture

### Model Structure

```
stock.rule              # Extended: dropship route detection, partner override
procurement.group       # Extended: dropship company domain filtering
stock.picking           # Extended: is_dropship computed field
stock.picking.type      # Extended: 'dropship' code + default locations
stock.lot               # Extended: last delivery partner for dropship lots
stock.move              # Extended: layer candidates for dropship stock valuation
purchase.order          # Extended: dropship picking count
purchase.order.line     # Extended: (inherited from stock)
sale.order              # Extended: dropship picking count
sale.order.line         # Extended: MTO detection for dropship, qty procurement
```

### File Map

| File | Purpose |
|------|---------|
| `models/stock.py` | Stock rule, procurement group, picking, lot, move extensions |
| `models/purchase.py` | Purchase order dropship count |
| `models/sale.py` | Sale order dropship count + MTO detection |
| `models/product.py` | Product extensions |
| `models/res_partner.py` | Partner extensions |
| `models/stock_warehouse.py` | Warehouse dropship route rules |

### Dropship Route

The module references the dropship route via:
```python
self.env.ref('stock_dropshipping.route_drop_shipping')
# External ID: stock_dropshipping.route_drop_shipping
```

This route must be configured on products or product categories to trigger dropship behavior.

---

## Core Extensions

### stock.rule — Dropship Extension

**Model:** `stock.rule`
**Inheritance:** Extends with dropship-specific overrides

#### `_get_procurements_to_merge_groupby(procurement)`

Prevents merging procurement groups for purchase order lines linked to different sale order lines. This ensures delivered quantities are computed correctly when a dropship order has multiple SOLs.

#### `_get_partner_id(values, rule)`

Returns `False` (no partner) for dropship rules. Normal rules return the `sale_order_id.partner_id`, but dropship rules bypass this because the supplier ships directly to the customer — the partner_id would be set on the purchase order's destination address instead.

```python
route = self.env.ref('stock_dropshipping.route_drop_shipping', raise_if_not_found=False)
if route and rule.route_id == route:
    return False  # Supplier partner comes from vendor, not customer
return super()._get_partner_id(values, rule)
```

---

### procurement.group — Dropship Extension

**Model:** `procurement.group`

#### `_get_rule_domain(location, values)`

Extends rule domain filtering to include `company_id` when `sale_line_id` is in `values`. This ensures dropship POs are matched in the correct company context:

```python
domain = super()._get_rule_domain(location, values)
if 'sale_line_id' in values and values.get('company_id'):
    domain = expression.AND([domain, [('company_id', '=', values['company_id'].id)]])
return domain
```

---

### stock.picking — Dropship Extension

**Model:** `stock.picking`

#### `is_dropship` (computed)

Determines whether a picking is a dropship operation:

```python
source = picking.location_id       # Supplier location
dest = picking.location_dest_id     # Customer location

picking.is_dropship = (
    (source.usage == 'supplier' or (source.usage == 'transit' and not source.company_id))
    and
    (dest.usage == 'customer' or (dest.usage == 'transit' and not dest.company_id))
)
```

**Logic breakdown:**
- **Source from supplier:** `location_id.usage == 'supplier'` OR (`transit` with no company — meaning inter-company transit)
- **Destination to customer:** `location_dest_id.usage == 'customer'` OR (`transit` with no company)

#### `_is_to_external_location()`

Extends the parent method to return `True` for dropship pickings, allowing them to proceed to external (non-internal) locations.

---

### stock.picking.type — Dropship Extension

**Model:** `stock.picking.type`

#### `code` (extends selection)

Adds `'dropship'` as a picking type code:
```python
selection_add=[('dropship', 'Dropship')]
```

When deleted, the code falls back to `'outgoing'` and the type is deactivated.

#### Default Location Computation

- **Source:** `stock.stock_location_suppliers` (the Suppliers virtual location)
- **Destination:** `stock.stock_location_customers` (the Customers virtual location)

```python
dropship_types.default_location_src_id = ref('stock.stock_location_suppliers')
dropship_types.default_location_dest_id = ref('stock.stock_location_customers')
```

#### Warehouse Dissociation

For dropship picking types, `warehouse_id` is `False` — dropship operations are not tied to any specific warehouse.

---

### stock.lot — Dropship Extension

**Model:** `stock.lot`

#### `_compute_last_delivery_partner_id()`

Extends lot delivery tracking: if the last delivery for a lot was a dropship picking, the `last_delivery_partner_id` is set to the sale order's partner (the customer), not the dropship supplier.

---

### stock.move — Dropship Extension

**Model:** `stock.move`

#### `_get_layer_candidates()`

Filters stock valuation layer candidates for dropship moves:
- **Dropshipped moves:** Only negative-quantity SVLs (outbound from supplier)
- **Dropshipped returns:** Only positive-quantity SVLs (return to supplier)

```python
if self._is_dropshipped():
    layer_candidates = layer_candidates.filtered(lambda svl: svl.quantity < 0)
elif self._is_dropshipped_returned():
    layer_candidates = layer_candidates.filtered(lambda svl: svl.quantity > 0)
```

This ensures correct stock valuation for dropship products that are tracked by lot/serial.

---

### sale.order — Dropship Extension

**Model:** `sale.order`

#### `dropship_picking_count` (computed)

Count of pickings linked to this SO that have `is_dropship == True`.

#### `_compute_picking_ids()`

Extends the parent method:
1. Calls `super()` to compute normal delivery count
2. Subtracts dropship pickings from `delivery_count`
3. Sets `dropship_picking_count` to the dropship picking count

```python
for order in self:
    dropship_count = len(order.picking_ids.filtered(lambda p: p.is_dropship))
    order.delivery_count -= dropship_count
    order.dropship_picking_count = dropship_count
```

#### Actions

| Method | Behavior |
|--------|----------|
| `action_view_delivery()` | Shows only non-dropship pickings |
| `action_view_dropship()` | Shows only dropship pickings |

---

### sale.order.line — Dropship Extension

**Model:** `sale.order.line`

#### `_compute_is_mto()`

Extends MTO (Make To Order) detection for dropship:
- If a product's route has a rule where `picking_type_id.default_location_src_id.usage == 'supplier'` AND `default_location_dest_id.usage == 'customer'` → marks line as `is_mto = True`
- This triggers direct PO creation without warehouse stock involvement

#### `_purchase_service_prepare_order_values(supplierinfo)`

When creating a PO from an SOL for a dropship product:
- Sets `dest_address_id` to `order_id.partner_shipping_id` (ship directly to customer)
- Sets `picking_type_id` to the dropship operation type (company's dropship incoming picking type)

---

## Dropship Flow

```
Sale Order Confirmation
         |
         v
Procurement Group Created
         |
         v
Stock Rule Evaluation (route = dropshipping)
         |
         v
Procurement Launched
  - sale_line_id passed in values
  - company_id enforced via _get_rule_domain
         |
         v
Purchase Order Created (auto)
  - Vendor = product's preferred supplier
  - dest_address_id = SO partner_shipping_id
  - picking_type_id = dropship operation type
  - No warehouse linked
         |
         v
Dropship Picking Created
  - Type: 'dropship'
  - Source: stock_location_suppliers
  - Dest: stock_location_customers
  - is_dropship = True
         |
         v
Supplier Ships Directly to Customer
         |
         v
Picking Done
  - Delivered to customer
  - Sale Order Delivered
  - Vendor Bill Received
```

---

## Key Design Decisions

1. **Route-based activation:** Dropshipping is triggered by assigning the `stock_dropshipping.route_drop_shipping` route to products. This is the standard Odoo routing mechanism — no special flags on orders.

2. **No intermediate warehouse:** The PO created by the dropship rule has `dest_address_id` set to the customer's shipping address, and the picking goes directly from the supplier location to the customer location. There is no incoming receipt at the seller's warehouse.

3. **`is_dropship` computed dynamically:** Rather than storing a flag, `is_dropship` is computed from the picking's location configuration. This means any picking matching the supplier→customer pattern is automatically recognized as dropship.

4. **Separated picking counts:** Dropship pickings are counted separately from regular delivery pickings in both sale and purchase orders, allowing clean separation in reporting.

5. **Stock valuation for dropship lots:** The `_get_layer_candidates()` override ensures that dropship products tracked by lot/serial get correct negative SVL entries for the "cost of goods sold" side of the valuation.

6. **`_get_partner_id` returns `False` for dropship:** The supplier partner comes from the vendor on the purchase order, not from the sale order's partner. Returning `False` prevents the rule from imposing the customer's partner as the PO vendor.

---

## Notes

- The dropship picking type (`code = 'dropship'`) is used for internal Odoo operations but represents an external physical flow (supplier → customer).
- When a dropship purchase order is confirmed, Odoo's procurement engine creates the dropship picking automatically via the stock rule.
- `stock_location_suppliers` and `stock_location_customers` are virtual (non-physical) locations used to represent the endpoints of the dropship chain in stock operations.
- The dropship route is typically combined with MTO (Make To Order) to create a pull/PUSH system where the SO triggers the PO directly to the vendor.
