---
Module: website_sale_delivery
Version: Odoo 18
Type: Integration
Tags: #odoo18, #e-commerce, #delivery, #website, #checkout
Related Modules: [delivery](Modules/delivery.md), [website_sale](Modules/website-sale.md), [sale](Modules/sale.md), [website_sale_stock](Modules/website-sale-stock.md), [website_sale_collect](Modules/website-sale-picking.md)
---

# website_sale_delivery — E-Commerce Delivery Methods

> **IMPORTANT:** In Odoo 18, `website_sale_delivery` is **not a standalone module**. Delivery for e-commerce is built into `website_sale` (which depends on `delivery`) and `website_sale_stock`. Delivery method display, selection, and cost recalculation are handled by `website_sale/controllers/delivery.py`, `website_sale/models/sale_order.py` (extends `sale.order`), and `website_sale/models/delivery_carrier.py` (extends `delivery.carrier`).
>
> The `website_sale` module also has a `website_sale_delivery.scss` stylesheet and `delivery_form_templates.xml` QWeb templates. This page documents all the delivery integration code across `website_sale` and `delivery`.

---

## Architecture Overview

```
website_sale
  ├── controllers/delivery.py   ← Delivery method selection, pickup location routes
  ├── models/delivery_carrier.py ← delivery.carrier extends website.publishable.mixin
  ├── models/sale_order.py      ← sale.order EXTENDS with website-specific delivery fields
  └── views/delivery_form_templates.xml  ← QWeb delivery form templates

delivery (base addon)
  ├── models/delivery_carrier.py  ← Core carrier model (free_over, price rules, etc.)
  └── models/sale_order.py        ← sale.order EXTENDS with carrier_id, pickup_location_data

website_sale_stock
  └── models/sale_order.py        ← sale.order EXTENDS with stock availability checks
```

---

## Models

### `delivery.carrier` (Extended by `website_sale`)

**Module:** `website_sale / delivery` | **Inherits:** `delivery.carrier`, `website.published.multi.mixin`

#### Fields Added by `website_sale`

| Field | Type | Description |
|-------|------|-------------|
| `website_description` | `Text` | Short description for online quotations. Related to `product_id.description_sale`, `readonly=False` |

#### Core `delivery.carrier` Fields (from `delivery` module)

| Field | Type | Description |
|-------|------|-------------|
| `name` | `Char` | Delivery method display name |
| `active` | `Boolean` | Whether the carrier is active |
| `sequence` | `Integer` | Display order |
| `delivery_type` | `Selection` | Provider type: `'base_on_rule'`, `'fixed'`, or extended by other modules (e.g., `'in_store'` by `website_sale_collect`) |
| `integration_level` | `Selection` | `'rate'` (get rate) or `'rate_and_ship'` (get rate + create shipment) |
| `company_id` | `Many2one(res.company)` | Related to `product_id.company_id` |
| `product_id` | `Many2one(product.product)` | Delivery product (used for invoicing) |
| `tracking_url` | `Char` | Tracking URL template with `<shipmenttrackingnumber>` placeholder |
| `free_over` | `Boolean` | If `True`, shipping is free when order amount >= `amount` |
| `amount` | `Float` | Minimum order amount to qualify for free shipping |
| `margin` | `Float` | Percentage added to shipping price |
| `fixed_margin` | `Float` | Fixed amount added to shipping price |
| `price_rule_ids` | `One2many` | Pricing rules for `base_on_rule` type |
| `country_ids` | `Many2many(res.country)` | Countries this carrier applies to |
| `state_ids` | `Many2many(res.country.state)` | States this carrier applies to |
| `zip_prefix_ids` | `Many2many(delivery.zip.prefix)` | Zip code prefixes (regex supported) |
| `max_weight` | `Float` | Max weight before carrier becomes unavailable |
| `max_volume` | `Float` | Max volume before carrier becomes unavailable |
| `must_have_tag_ids` | `Many2many(product.tag)` | Carrier available only if order has one of these tags |
| `excluded_tag_ids` | `Many2many(product.tag)` | Carrier NOT available if order has any of these tags |

#### Constraints

```python
('margin_not_under_100_percent', 'CHECK (margin >= -1)')
('shipping_insurance_is_percentage', 'CHECK(shipping_insurance >= 0 AND shipping_insurance <= 100)')
# Tags cannot be in both must_have and excluded
```

#### Key Methods

**`rate_shipment(order)`** — Compute the price of shipment
- Calls `<delivery_type>_rate_shipment()` method on the carrier (e.g., `fixed_rate_shipment`, `base_on_rule_rate_shipment`)
- Applies fiscal position to the price
- Applies margin (`_apply_margins()`)
- If `free_over=True` and order amount >= `amount`: sets price to `0.0`
- Returns: `{'success': bool, 'price': float, 'error_message': str, 'warning_message': str, 'carrier_price': float}`

**`_is_available_for_order(order)`** — Check if carrier is available for an order
- Returns `False` if `_match()` fails
- For `base_on_rule`: also checks `rate_shipment().get('success')`

**`_match(order)`** — Full matching logic
- `_match_address()` — country, state, zip prefix
- `_match_must_have_tags()` — at least one product has a required tag
- `_match_excluded_tags()` — no product has an excluded tag
- `_match_weight()` — total weight <= `max_weight`
- `_match_volume()` — total volume <= `max_volume`

**`fixed_rate_shipment(order)`** — Fixed price provider
- Returns fixed price from `product_id.list_price`
- Validates against `country_ids` match

**`base_on_rule_rate_shipment(order)`** — Rule-based pricing
- Uses `delivery.price.rule` records to determine price based on `total`, `weight`, `volume`, `quantity`
- Uses `safe_eval()` on rule conditions

**`_get_price_available(order)`** — Calculate price from rules
- Sums order line weights, volumes, quantities, totals
- Skips cancelled lines, delivery lines, and service lines
- Falls back to `shipping_weight` from context or order

---

### `sale.order` (Extended by `website_sale`)

**Module:** `website_sale` | **Inherits:** `sale.order`

#### Website-Specific Fields

| Field | Type | Description |
|-------|------|-------------|
| `website_id` | `Many2one(website)` | Website through which the order was placed |
| `cart_recovery_email_sent` | `Boolean` | Whether cart recovery email has been sent |
| `shop_warning` | `Char` | Warning message displayed on shop/cart |
| `website_order_line` | `One2many` | Lines filtered to show in cart (`_show_in_cart()`) |
| `amount_delivery` | `Monetary` | Tax-included/excluded delivery amount |
| `cart_quantity` | `Integer` | Total quantity in cart |
| `only_services` | `Boolean` | `True` if all products in cart are services |
| `is_abandoned_cart` | `Boolean` | `True` if draft order is past the abandoned delay |

#### Delivery-Specific Fields (from `delivery` module, on `sale.order`)

| Field | Type | Description |
|-------|------|-------------|
| `pickup_location_data` | `Json` | JSON containing selected pickup location address (name, street, city, zip, country_code, state, latitude, longitude, additional_data) |
| `carrier_id` | `Many2one(delivery.carrier)` | Selected delivery method |
| `delivery_message` | `Char` | Delivery status message (readonly) |
| `delivery_set` | `Boolean` | Computed — whether any delivery line exists |
| `recompute_delivery_price` | `Boolean` | Flag to recompute delivery price when order line changes |
| `is_all_service` | `Boolean` | `True` if all order lines are services |
| `shipping_weight` | `Float` | Estimated total shipping weight |

#### Key Methods

**`_compute_amount_delivery()`**
- Sums `price_subtotal` (tax excluded) or `price_total` (tax included) of delivery lines
- Respects `website_id.show_line_subtotals_tax_selection`

**`_has_deliverable_products()`**
- Returns `True` if order has product lines and not `only_services`
- Used to determine whether delivery step can be skipped

**`_get_delivery_methods()`** — Get available carriers for the order
```python
return self.env['delivery.carrier'].sudo().search([
    ('website_published', '=', True),
    *self.env['delivery.carrier']._check_company_domain(self.company_id),
]).filtered(lambda carrier: carrier._is_available_for_order(self))
```
- Uses `website_published` field (from `website.published.multi.mixin`) — searches published carriers on current website

**`_get_preferred_delivery_method(available_delivery_methods)`** — Priority selection
1. Already-set carrier if still compatible
2. `partner_shipping_id.property_delivery_carrier_id` if in available list
3. First available method

**`_set_delivery_method(delivery_method, rate=None)`**
- Calls `_remove_delivery_line()` first
- Calls `delivery_method.rate_shipment(self)` to get rate
- If success: calls `set_delivery_line(carrier, price)` to create delivery order line

**`_update_address(partner_id, fnames=None)`**
- Called when shipping address changes
- Recomputes fiscal position if changed → `_recompute_taxes()`
- Recomputes pricelist if changed → `_recompute_prices()`
- **Automatically updates delivery method** if `partner_shipping_id` changes and order has deliverable products:
  ```python
  if 'partner_shipping_id' in fnames and self._has_deliverable_products():
      delivery_methods = self._get_delivery_methods()
      delivery_method = self._get_preferred_delivery_method(delivery_methods)
      self._set_delivery_method(delivery_method)
  ```

**`set_delivery_line(carrier, amount)`**
- Removes existing delivery line
- Creates `sale.order.line` with `is_delivery=True`, `product_id=carrier.product_id`

**`_remove_delivery_line()`**
- Removes delivery lines where `qty_invoiced == 0`
- Raises `UserError` if delivery was already invoiced
- Also resets `pickup_location_data = {}` (from `website_sale` override)

**`_set_pickup_location(pickup_location_data)`**
- For carriers with `<delivery_type>_use_locations = True`: stores JSON location data
- Calls `_set_pickup_location` on `sale.order` (in `delivery` module)

**`_get_pickup_locations(zip_code=None, country=None, **kwargs)`**
- Dispatches to `_<delivery_type>_get_close_locations()` method on carrier
- Used for in-store / pickup point selection

---

### `website` (Extended by `website_sale`)

**Module:** `website_sale` | **Inherits:** `website`

#### Fields Related to Delivery

| Field | Type | Description |
|-------|------|-------------|
| `fiscal_position_id` | `Many2one(account.fiscal.position)` | Computed: geoip-based or partner-based fiscal position |
| `pricelist_id` | `Many2one(product.pricelist)` | Computed: current applicable pricelist |
| `currency_id` | `Many2one(res.currency)` | Computed: currency of current pricelist |
| `pricelist_ids` | `One2many(product.pricelist)` | All pricelists available on this website |

---

## Delivery Cost Recalculation — L4 Analysis

### When Address Changes

Trigger: `shop_update_address` controller → `order._update_address(partner_id, {'partner_shipping_id'})`

```
_update_address()
  ├── Write partner_shipping_id
  ├── If fiscal_position changed → _recompute_taxes()
  ├── If pricelist changed → _recompute_prices()
  └── If carrier_id set AND has deliverable products:
        ├── _get_delivery_methods()  → all published, company-matched, available
        ├── _get_preferred_delivery_method()  → priority: current > partner pref > first
        └── _set_delivery_method(preferred_dm)
              ├── rate_shipment(order)  → get new price
              ├── set_delivery_line(dm, price)  → update order line
              └── (if rate fails: _remove_delivery_line())
```

### When Cart Contents Change

Trigger: `_cart_update(product_id, ...)` → after adding/updating a line

```
If only_services: → _remove_delivery_line()  (no shipping needed)
Elif carrier_id:
  └── rate_shipment(order)  → recalculate price
      ├── If success: update delivery line price_unit
      └── If fails: _remove_delivery_line()
```

### Address Change Recalculation Priority

The recalculation is indirect: `_update_address` does NOT directly call `rate_shipment`. Instead:

1. `_update_address` calls `_set_delivery_method(preferred_dm)` **without** a rate
2. `_set_delivery_method` calls `delivery_method.rate_shipment(self)` **with** the new address
3. The new rate is stored on the delivery line

### Fiscal Position on Delivery

- `rate_shipment()` calls `product_id._get_tax_included_unit_price()` with `fiscal_position=order.fiscal_position_id`
- The fiscal position from the **delivery address** (or warehouse for in-store) is used
- `website_sale_collect` overrides `_set_pickup_location()` to apply the warehouse's country fiscal position

---

## Express Checkout Integration

### Route: `/shop/express/shipping_address_change`

Express checkout (Google Pay / Apple Pay) calls this route when the shipping address changes:

```
express_checkout_process_delivery_address(partial_delivery_address)
  ├── Update/create partner_shipping_id
  ├── _get_delivery_methods_express_checkout(order)
  │     ├── Iterate all _get_delivery_methods()
  │     ├── Call _get_rate(dm, order, is_express_checkout_flow=True)
  │     └── Skip carriers with <type>_use_locations = True
  ├── Select cheapest available method
  └── _set_delivery_method(cheapest_dm)
```

**Key constraint:** Carriers that require location selection (e.g., `in_store` pickup) are **excluded from express checkout** because the customer cannot interact with a location picker in the express payment flow.

---

## Free Shipping Thresholds — L4 Analysis

### Mechanism

In `delivery.carrier.rate_shipment()`:

```python
# free when order is large enough
amount_without_delivery = order._compute_amount_total_without_delivery()
if (
    res['success']
    and self.free_over
    and self.delivery_type != 'base_on_rule'  # Note: NOT for rule-based
    and self._compute_currency(order, amount_without_delivery, 'pricelist_to_company') >= self.amount
):
    res['warning_message'] = _('The shipping is free since the order amount exceeds %.2f.', self.amount)
    res['price'] = 0.0
```

- `amount_without_delivery` = `amount_total - sum(delivery_line.price_total)`
- Currency is converted to company currency before comparing to `amount`
- `free_over` only applies to `fixed` and external provider types, **NOT** `base_on_rule`
- The `carrier_price` is preserved before overriding to `0.0` so the real cost is still available

### Delivery Line Label

When `free_over` triggers free shipping, the delivery line name is set to include "Free Shipping":

```python
# In _prepare_delivery_line_vals():
if carrier.free_over and self.currency_id.is_zero(price_unit):
    values['name'] = _('%s\nFree Shipping', values['name'])
```

---

## `website.published.multi.mixin` — L4

Applied to `delivery.carrier` via `website_sale`:

```python
class DeliveryCarrier(models.Model):
    _inherit = ['delivery.carrier', 'website.published.multi.mixin']
```

This mixin provides:

| Feature | Field | Description |
|---------|-------|-------------|
| Multi-website publish | `website_published` (Boolean) | Per-website publish state. Computed: `is_published AND (not website_id OR website_id == current_website)` |
| Per-website scoping | `website_id` (Many2one) | Restricts the carrier to a specific website |
| Inverse publish | `_inverse_website_published` | Sets `is_published = website_published` |
| Search scope | `_search_website_published` | Filters by website context |
| Frontend availability | `_compute_can_publish` | Checks user groups |

The key search method `_get_delivery_methods()` filters on `website_published=True`, so carriers unpublished on the current website are hidden from the checkout.

---

## Controllers

### `website_sale/controllers/delivery.py`

| Route | Method | Description |
|-------|--------|-------------|
| `GET /shop/delivery_methods` | `shop_delivery_methods()` | Render available delivery methods form |
| `POST /shop/set_delivery_method` | `shop_set_delivery_method(dm_id)` | Set delivery method on cart |
| `POST /shop/get_delivery_rate` | `shop_get_delivery_rate(dm_id)` | Get rate for a specific carrier |
| `POST /website_sale/set_pickup_location` | `website_sale_set_pickup_location()` | Set pickup location (for carriers with locations) |
| `GET /website_sale/get_pickup_locations` | `website_sale_get_pickup_locations()` | Get pickup locations near zip code |
| `POST /shop/express/shipping_address_change` | `express_checkout_process_delivery_address()` | Express checkout address + delivery selection |

---

## Dependencies Graph

```
website_sale
  depends: website, sale, website_payment, website_mail, portal_rating, digest, delivery
    └── delivery
          └── sale (for sale.order extensions)

website_sale_stock
  depends: website_sale, sale_stock, stock_delivery

website_sale_collect
  depends: base_geolocalize, payment_custom, website_sale_stock
```

---

## Key Takeaways

1. **`website_sale_delivery` is not a separate module** — delivery UI and logic live in `website_sale` + `delivery`
2. **`delivery.carrier`** is the central model; `website_sale` adds `website.published.multi.mixin` for WYSIWYG publishing
3. **Cost recalculation** is triggered indirectly via `_update_address()` → `_set_delivery_method()` → `rate_shipment()`
4. **`free_over`** works at the `rate_shipment()` level; excluded for `base_on_rule` type
5. **Express checkout excludes in-store pickup** because no location picker UI is available in the payment form
6. **`website_id`** on `sale.order` links every e-commerce order back to its originating website
