# stock_delivery — Stock Delivery

**Tags:** #odoo #odoo18 #stock #delivery #shipping #carrier
**Odoo Version:** 18.0
**Module Category:** Stock + Delivery Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`stock_delivery` extends the base `delivery` module with physical shipping infrastructure for stock pickings. It manages carrier assignment on pickings, package weight computation, label generation, return label handling, tracking URL display, and shipping cost posting to the sale order.

**Technical Name:** `stock_delivery`
**Python Path:** `~/odoo/odoo18/odoo/addons/stock_delivery/`
**Depends:** `delivery`, `stock`
**Inherits From:** `delivery.carrier`, `stock.picking`, `stock.move`, `stock.route`, `stock.move.line`, `sale.order`, `stock.package.type`, `stock.quant.package`, `product.template`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/delivery_carrier.py` | `delivery.carrier` | Shipping API, commodity/package building, fixed/base_on_rule providers |
| `models/stock_picking.py` | `stock.picking` | Carrier fields, weight, tracking, label, shipment sending |
| `models/stock_move.py` | `stock.move`, `stock.route`, `stock.move.line` | Weight computation, carrier propagation to pickings |
| `models/sale_order.py` | `sale.order`, `sale.order.line` | Real-cost delivery line, route propagation |
| `models/product_template.py` | `product.template` | HS code, country of origin |
| `models/stock_package_type.py` | `stock.package.type` | Carrier codes, carrier type selection |
| `models/stock_quant_package.py` | `stock.quant.package` | Package weight computation |
| `models/delivery_request_objects.py` | None (pure Python data classes) | `DeliveryPackage`, `DeliveryCommodity` |

---

## Models Reference

### `stock.picking` (models/stock_picking.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `carrier_price` | Float | Shipping cost |
| `delivery_type` | Selection | Related from carrier |
| `carrier_id` | Many2one | `delivery.carrier` link |
| `weight` | Float | Compute from moves, store, digits='Stock Weight' |
| `carrier_tracking_ref` | Char | Tracking reference from carrier |
| `carrier_tracking_url` | Char | Computed tracking URL |
| `weight_uom_name` | Char | Unit of measure label |
| `is_return_picking` | Boolean | Compute from carrier + return moves |
| `return_label_ids` | One2many | IR attachments for return labels |
| `destination_country_code` | Char | Related from partner |

#### Methods

| Method | Behavior |
|--------|----------|
| `_get_default_weight_uom()` | Gets from product template config |
| `_compute_weight_uom_name()` | Sets UOM name |
| `_compute_carrier_tracking_url()` | Calls `carrier_id.get_tracking_link()` |
| `_compute_return_picking()` | True if carrier allows returns and has returned moves |
| `_compute_return_label()` | Searches for return label attachments |
| `get_multiple_carrier_tracking()` | Parses JSON tracking URL |
| `_cal_weight()` | Sums move weights |
| `_send_confirmation_email()` | Sends to shipper if level is 'rate_and_ship', handles errors with activity |
| `_pre_put_in_pack_hook()` | Validates single carrier per package |
| `_set_delivery_package_type()` | Opens package type wizard |
| `send_to_shipper()` | Calls carrier API, updates tracking ref, posts message, adds cost to SO |
| `_check_carrier_details_compliance()` | Hook for carrier-specific validation |
| `print_return_label()` | Calls carrier's return label generation |
| `_get_matching_delivery_lines()` | Finds zero-price delivery SOL matching carrier product |
| `_prepare_sale_delivery_line_vals()` | Prepares vals for delivery SOL |
| `_add_delivery_cost_to_so()` | Creates or updates delivery SOL with real cost |
| `open_website_url()` | Opens carrier tracking page |
| `cancel_shipment()` | Calls carrier cancel, clears tracking ref |
| `_get_estimated_weight()` | Computes weight from product qty × weight |
| `_should_generate_commercial_invoice()` | True if warehouse ≠ partner country |

---

### `delivery.carrier` (models/delivery_carrier.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `invoice_policy` | Selection | Adds 'real' option (real cost, updated after delivery) |
| `route_ids` | Many2many | Stock routes for carrier |

#### Methods

| Method | Behavior |
|--------|----------|
| `send_shipping(pickings)` | Generic dispatch: calls `'{delivery_type}_send_shipping'` method |
| `get_return_label(pickings, ...)` | Generates return label, grants portal access |
| `get_return_label_prefix()` | Returns `'LabelReturn-{delivery_type}'` |
| `_get_delivery_label_prefix()` | Returns `'LabelShipping-{delivery_type}'` |
| `_get_delivery_doc_prefix()` | Returns `'ShippingDoc-{delivery_type}'` |
| `get_tracking_link(picking)` | Dispatches to `'{delivery_type}_get_tracking_link'` |
| `cancel_shipment(pickings)` | Dispatches to `'{delivery_type}_cancel_shipment'` |
| `_get_default_custom_package_code()` | Dispatches to `'_{delivery_type}_get_default_custom_package_code'` |
| `_get_packages_from_order(order, type)` | Builds `DeliveryPackage` list for an order |
| `_get_packages_from_picking(picking, type)` | Builds `DeliveryPackage` list for a picking |
| `_get_commodities_from_order(order)` | Extracts consumable product lines as `DeliveryCommodity` |
| `_get_commodities_from_stock_move_lines(lines)` | Groups consumable move lines as commodities |
| `_product_price_to_company_currency(qty, product, company)` | Converts product cost using company currency |
| `fixed_send_shipping(pickings)` | Returns fixed price for each picking |
| `fixed_get_tracking_link(picking)` | Uses `tracking_url` template |
| `fixed_cancel_shipment(pickings)` | Raises `NotImplementedError` |
| `base_on_rule_send_shipping(pickings)` | Matches carrier rule and returns price |
| `base_on_rule_get_tracking_link(picking)` | Uses tracking_url template |
| `base_on_rule_cancel_shipment(pickings)` | Raises `NotImplementedError` |

---

### `stock.route` (models/stock_move.py)

| Field | Type | Notes |
|-------|------|-------|
| `shipping_selectable` | Boolean | Route applicable on shipping methods |

---

### `stock.move` (models/stock_move.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `weight` | Float | Computed from product_qty × product.weight, stored, auto-init via SQL |

#### Methods

| Method | Behavior |
|--------|----------|
| `_auto_init()` | Creates `weight` column if missing, backfills via SQL |
| `_cal_move_weight()` | Computes weight from product weight and qty |
| `_get_new_picking_values()` | Copies carrier_id from sale order |
| `_key_assign_picking()` | Adds `carrier_id` to grouping key |

---

### `stock.move.line` (models/stock_move.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `sale_price` | Float | Computed sale price from SO line or product list price |
| `destination_country_code` | Char | Related from picking |
| `carrier_id` | Many2one | Related from picking (stored) |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_sale_price()` | From `sale_line_id.price_reduce_taxinc` or product `list_price` |
| `_get_aggregated_product_quantities()` | Adds `hs_code` to aggregated data |

---

### `sale.order` (models/sale_order.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `set_delivery_line(carrier, amount)` | Also updates carrier on pending pickings |
| `_create_delivery_line(carrier, price_unit)` | If `invoice_policy == 'real'`, shows 0 with estimated cost in name |

---

### `stock.package.type` (models/stock_package_type.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `shipper_package_code` | Char | Carrier-specific package code |
| `package_carrier_type` | Selection | Carrier type ('none' default) |

#### Methods

| Method | Behavior |
|--------|----------|
| `_onchange_carrier_type()` | Auto-sets shipper_package_code from carrier |
| `_compute_length_uom_name()` | Clears UOM name for integrated carriers |

---

### `stock.quant.package` (models/stock_quant_package.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `weight` | Float | Computed from contained products, digits='Stock Weight' |
| `weight_uom_name` | Char | UOM label |
| `weight_is_kg` | Boolean | Whether weight UOM is kg |
| `weight_uom_rounding` | Float | Decimal places for weight |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_weight()` | Calls `_get_weight()` with context picking_id |
| `_get_default_weight_uom()` | Gets from product template |
| `_compute_weight_uom_name()` | Sets UOM name |
| `_compute_weight_is_kg()` | Checks against kg reference, sets rounding |

---

## Security File

No security file (`security/` directory does not exist in this module).

---

## Data Files

No data file (`data/` directory does not exist in this module).

---

## Critical Behaviors

1. **Real Cost Invoicing**: `invoice_policy = 'real'` keeps the delivery line price at zero on SO confirmation. After `send_to_shipper()` is called (picking validated), `_add_delivery_cost_to_so()` updates the SOL with the actual carrier price.

2. **Package Building**: `_get_packages_from_order()` automatically distributes products into carrier-sized packages. It divides total weight by `max_weight` of the package type, splits commodities uniformly across packages.

3. **Carrier Propagation**: `_get_new_picking_values()` on `stock.move` sets the carrier from the sale order's carrier. Routes marked `shipping_selectable = True` can be selected on the carrier form.

4. **Tracking Number Concatenation**: `send_to_shipper()` handles multiple pickings sharing the same tracking number — appends new tracking numbers to existing ones with comma separation.

5. **Return Labels**: `print_return_label()` calls `carrier_id.get_return_label()` if the carrier has `can_generate_return = True`. Labels are stored as IR attachments with name prefix `LabelReturn-{delivery_type}`.

6. **Weight Auto-Init**: `stock.move.weight` is created via SQL in `_auto_init()` to avoid RAM exhaustion on large databases. The column is backfilled with `product_qty * product.weight`.

---

## v17→v18 Changes

- `delivery_type` related field added to `stock.picking`
- `_check_carrier_details_compliance()` hook added for carrier-specific compliance checks
- `destination_country_code` related field added
- `is_return_picking` compute logic improved
- `weight` field on `stock.move` now has `compute_sudo=True`

---

## Notes

- `stock_delivery` is the base for carrier-specific modules (e.g., `delivery_ship效力`, `delivery_gls`, etc.)
- The `DeliveryPackage` and `DeliveryCommodity` data classes are the canonical interface for carrier API methods
- Commodity monetary values are split uniformly across packages when using `_get_packages_from_order()`
- The `shipping_selectable` field on `stock.route` enables routes to appear in carrier configuration
