---
title: website_sale_delivery
tags:
  - odoo
  - odoo19
  - modules
  - website
  - delivery
  - ecommerce
  - checkout
  - shipping
description: "eCommerce delivery method selection, rate computation, and carrier integration — merged into website_sale in Odoo 19"
---

# website_sale_delivery

> **Module status note**: In Odoo 19, `website_sale_delivery` was merged into `website_sale`. The delivery functionality lives in `website_sale` (which hard-depends on `delivery`). This document covers the merged implementation as it exists in Odoo 19.

## Module Information

| Property | Value |
|----------|-------|
| **Technical Name** | `website_sale` (delivery sub-system) |
| **Category** | Website/Website |
| **Summary** | Delivery method selection, shipping rate computation, carrier publishing for eCommerce |
| **Depends** | `website_sale`, `delivery` (and transitively: `sale`, `website`, `stock`) |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

---

## L1: Business Concept — How Delivery Methods Work on the Website

The website delivery sub-system handles:

1. **Carrier publishing**: Website operators publish `delivery.carrier` records to the website with pricing, description, and geographic restrictions
2. **Rate computation**: When a customer reaches checkout, available carriers compute shipping rates based on order weight, volume, price, and destination address
3. **Carrier selection**: The customer selects a carrier; the selection is stored as `carrier_id` on `sale.order` and a delivery `sale.order.line` is added with the shipping price
4. **Address-change recompute**: Changing the shipping address triggers re-evaluation of available carriers and prices
5. **Express checkout**: Google Pay / Apple Pay express flows auto-select the cheapest available carrier when shipping address changes

The `pickup_location_data` JSON field (from `delivery` module) stores selected pickup point data (e.g., Mondial Relay Point Relais). On SO confirmation, a child `res.partner` of type `'delivery'` with `is_pickup_location=True` is created or reused to represent the pickup point address on the stock picking.

---

## L2: Field Types, Defaults, Constraints

### `delivery.carrier` (base model, from `delivery` module)

Defined in: `delivery/models/delivery_carrier.py`

**Key fields:**

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char | — | Required, translatable — display name in checkout |
| `active` | Boolean | `True` | — |
| `sequence` | Integer | `10` | Display order in lists |
| `delivery_type` | Selection | — | `'base_on_rule'` (rule-based) or `'fixed'` (fixed price) |
| `integration_level` | Selection | — | `'rate'` or `'rate_and_ship'` |
| `prod_environment` | Boolean | — | Toggle test/production for external providers |
| `product_id` | Many2one `product.product` | — | The delivery product used as the SO line product |
| `company_id` | Many2one `res.company` | — | Stored; related to `product_id.company_id` |
| `country_ids` | Many2many `res.country` | Empty | Empty = all countries; restricts carrier availability |
| `state_ids` | Many2many `res.country.state` | Empty | — |
| `zip_prefix_ids` | Many2many `delivery.zip.prefix` | Empty | Regex matching on partner zip |
| `max_weight` | Float | `0` | Carrier unavailable if order exceeds this |
| `max_volume` | Float | `0` | Carrier unavailable if order exceeds this |
| `must_have_tag_ids` | Many2many `product.tag` | Empty | Carrier available only if at least one order product has one of these tags |
| `excluded_tag_ids` | Many2many `product.tag` | Empty | Carrier unavailable if any order product has one of these tags |
| `margin` | Float | `0.0` | Percentage added to price. Constraint: `>= -1.0` |
| `fixed_margin` | Float | `0.0` | Fixed amount added |
| `free_over` | Boolean | `False` | Enable free shipping above threshold |
| `amount` | Float | `0.0` | Minimum order amount for free shipping |
| `shipping_insurance` | Integer | `0` | Percentage 0–100. Adds cost to shipment |

**Constraints:**

```python
_margin_not_under_100_percent = models.Constraint(
    'CHECK (margin >= -1)',
    'Margin cannot be lower than -100%',
)
_shipping_insurance_is_percentage = models.Constraint(
    'CHECK(shipping_insurance >= 0 AND shipping_insurance <= 100)',
    'The shipping insurance must be a percentage between 0 and 100.',
)
@api.constrains('must_have_tag_ids', 'excluded_tag_ids')
def _check_tags(self):
    for carrier in self:
        if carrier.must_have_tag_ids & carrier.excluded_tag_ids:
            raise UserError(_("Carrier cannot have the same tag in both lists."))
```

**`website_sale` extension** (in `website_sale/models/delivery_carrier.py`):

```python
class DeliveryCarrier(models.Model):
    _name = 'delivery.carrier'
    _inherit = ['delivery.carrier', 'website.published.multi.mixin']

    website_description = fields.Text(
        string="Description for Online Quotations",
        related='product_id.description_sale',
        readonly=False,
    )
```

`website.published.multi.mixin` adds: `website_id` (Many2one), `is_published` (Boolean), `website_publish_button` (in-form toggle), `website_published` (deprecated computed alias).

---

### `sale.order` (extended by `delivery`, further by `website_sale`)

Defined in: `delivery/models/sale_order.py` and `website_sale/models/sale_order.py`

**Fields added by `delivery` module:**

| Field | Type | Notes |
|-------|------|-------|
| `carrier_id` | Many2one `delivery.carrier` | The selected delivery method |
| `delivery_message` | Char | Readonly status message from carrier |
| `delivery_set` | Boolean (computed) | Any line with `is_delivery = True` |
| `recompute_delivery_price` | Boolean | Set True when order lines change to trigger recompute |
| `shipping_weight` | Float | Computed order weight; editable override for `base_on_rule` |
| `pickup_location_data` | Json | Selected pickup point JSON (e.g., Mondial Relay) |

**Fields added by `website_sale`:**

| Field | Type | Compute | Notes |
|-------|------|---------|-------|
| `website_id` | Many2one `website` | — | Set at cart creation; readonly after |
| `amount_delivery` | Monetary | `_compute_amount_delivery` | Sum of delivery line prices (tax-included or excluded per website setting) |
| `cart_quantity` | Integer | `_compute_cart_info` | Total cart qty from `website_order_line` |
| `only_services` | Boolean | `_compute_cart_info` | True if all cart products are services |
| `shop_warning` | Char | — | Temp warning for cart UI (e.g., stock issues) |

---

## L3: Cross-Model Integration, Override Patterns, Workflow Triggers

### Cross-Model Map

| From | To | Integration |
|------|----|-------------|
| `sale.order` | `delivery.carrier` (via `carrier_id`) | Selected carrier, delivery rate, pickup location |
| `delivery.carrier` | `product.product` (via `product_id`) | Delivery product = the `sale.order.line` product when carrier selected |
| `sale.order.line` | `delivery.carrier` (via `is_delivery` flag) | Delivery line carries the carrier's pricing |
| `res.partner` | `delivery.carrier` (via `property_delivery_carrier_id`) | Per-partner preferred carrier |
| `res.partner` | `res.partner` (pickup child) | On SO confirm, creates type='delivery' child with `is_pickup_location=True` |

### Override Patterns

| Model | In Module | Override Method |
|-------|-----------|-----------------|
| `delivery.carrier` | `delivery` | `rate_shipment()`, `_match()`, `_match_address()`, `_match_must_have_tags()`, `_match_excluded_tags()`, `_match_weight()`, `_match_volume()`, `_apply_margins()`, `fixed_rate_shipment()`, `base_on_rule_rate_shipment()` |
| `delivery.carrier` | `website_sale` | `website.published.multi.mixin` (publishing) |
| `sale.order` | `website_sale` | `_get_delivery_methods()`, `_set_delivery_method()`, `_compute_amount_delivery()`, `_has_deliverable_products()`, `_update_address()`, `_verify_cart_after_update()`, `_get_preferred_delivery_method()` |
| `sale.order` | `delivery` | `_set_pickup_location()`, `_action_confirm()` (pickup partner creation) |

### Workflow Trigger: Shipping Rate Computation at Checkout

```
User on checkout page
    ↓
/shop/delivery_methods (GET, rendered QWeb)
    ├─ order_sudo._get_delivery_methods()
    │     └─ sudo() search: website_published=True, company filter
    │           └─ .filtered(carrier._is_available_for_order())
    │                 └─ carrier._match() + carrier.rate_shipment()
    └─ Render: website_sale.delivery_form with delivery_methods list

User selects carrier → JS: /shop/set_delivery_method {dm_id}
    ├─ Validates carrier in available methods
    ├─ Transaction guard: no confirmed tx
    ├─ delivery_method.rate_shipment() → price
    └─ order._set_delivery_method(carrier, price)
          ├─ _remove_delivery_line()
          └─ set_delivery_line(carrier, price) → sale.order.line with is_delivery=True

Address change → POST /shop/update_address
    └─ order._update_address(partner_id, fnames)
          └─ if carrier_id and 'partner_shipping_id' in fnames:
                 order._set_delivery_method(preferred_carrier)
```

### Express Checkout Flow: `express_checkout_process_delivery_address`

```
Google Pay / Apple Pay form (shipping address callback)
    ↓
POST /shop/express/shipping_address_change
    ├─ _parse_form_data()          ← Normalize address fields
    ├─ _create_new_address()        ← Create delivery partner
    ├─ order.partner_id = new_partner  ← Triggers _update_address → delivery recompute
    ├─ _get_delivery_methods_express_checkout()
    │      └─ _get_rate() per carrier (pickup-location carriers EXCLUDED)
    ├─ Sort by minorAmount (price)
    └─ Auto-select cheapest carrier
    ↓
Return { delivery_methods: [{id, name, description, minorAmount}, ...] }
    ↓
Express payment form displays shipping options
    ↓
User selects (separate JS call to /shop/set_delivery_method)
    ↓
Payment submission
```

### Pickup Location Flow

```
User selects Point Relais on carrier widget
    ↓
POST /website_sale/set_pickup_location {pickup_location_data JSON}
    └─ order._set_pickup_location(pickup_location_data)
          └─ Stored on sale.order.pickup_location_data (Json)

sale.order._action_confirm()
    └─ Creates/resuses res.partner child (type='delivery', is_pickup_location=True)
          └─ stock.picking uses this pickup address instead of customer's home address
```

---

## L4: Odoo 18 → 19 Changes, Security

### Version Changes Odoo 18 → 19

**Module merge**: `website_sale_delivery` was merged into `website_sale` in Odoo 19. No standalone module exists.

**`delivery.carrier` changes**:
- `website_published` field removed (replaced by `is_published` from `website.published.multi.mixin`)
- `free_over` now explicitly excluded from `base_on_rule` carriers (same behavior, now documented in code)

**Express checkout**: Odoo 18 used a different code path. Odoo 19 standardizes on `Delivery._get_rate()` for both regular and express flows, reducing divergence.

**`pickup_location_data`**: Moved from `website_sale_mondialrelay` to the `delivery` module's `sale.order` extension. All carrier types sharing the pickup location pattern now store data in the same field.

**Pickup locations in express checkout**: `website_sale_mondialrelay` sets `mondialrelay_use_locations = True` on the carrier. In express checkout, `_get_delivery_methods_express_checkout()` hard-filters out carriers with `{delivery_type}_use_locations = True` — express checkout cannot show the location picker widget.

### Security

| Concern | Assessment | Notes |
|---------|------------|-------|
| ACL on `delivery.carrier` | Minimal risk | `sudo()` used in `_get_delivery_methods()` to bypass record rules. Carriers are typically public info |
| Transaction guard | Safe | `shop_set_delivery_method` refuses carrier changes if a non-draft/cancelled transaction exists |
| Pricelist protection | Safe | `env.protecting([order._fields['pricelist_id']], order)` prevents price recompute after customer accepted amount |
| Address partner creation | Safe | Anonymous users get a newly created `res.partner` of type `'delivery'` — no reuse of existing partners across sessions |
| `is_published` on carrier | Safe | Unpublished carriers invisible on website; allows soft deprecation |
| `pickup_location_data` Json | Low risk | Stores arbitrary JSON from carrier-specific selectors. No server-side schema validation |
| CSRF | Safe | JSON endpoints use Odoo's built-in CSRF |
| Mass assignment | Safe | Methods don't write user-controlled data to sensitive fields |

---

## Quick Reference: Key Methods

| Method | Model | File | Purpose |
|--------|-------|------|---------|
| `rate_shipment(order)` | `delivery.carrier` | `delivery/models/delivery_carrier.py` | Main rate entry point; calls `<type>_rate_shipment`, applies tax and margins |
| `_match(partner, source)` | `delivery.carrier` | `delivery/models/delivery_carrier.py` | Full matching: address + tags + weight + volume |
| `_get_price_available(order)` | `delivery.carrier` | `delivery/models/delivery_carrier.py` | Sums weight/volume/qty/total from non-delivery lines; runs as `sudo()` |
| `_get_delivery_methods(self)` | `sale.order` | `website_sale/models/sale_order.py` | Returns website-published carriers filtered by `_is_available_for_order()` |
| `_set_delivery_method(self, carrier, rate)` | `sale.order` | `website_sale/models/sale_order.py` | Removes old delivery line, calls `rate_shipment`, adds new line |
| `_verify_cart_after_update(self)` | `sale.order` | `website_sale/models/sale_order.py` | Recomputes delivery after cart line changes; removes if all-services |
| `_update_address(self, partner_id, fnames)` | `sale.order` | `website_sale/models/sale_order.py` | Triggers delivery recompute when shipping address changes |
| `_set_pickup_location(self, data)` | `sale.order` | `delivery/models/sale_order.py` | Stores pickup point JSON on order |
| `_get_rate(delivery_method, order, is_express=False)` | `Delivery` controller | `website_sale/controllers/delivery.py` | Tax-aware rate computation; static method used by both regular and express checkout |
| `shop_delivery_methods` | `Delivery` controller | `website_sale/controllers/delivery.py` | Renders delivery method selection list |
| `shop_set_delivery_method` | `Delivery` controller | `website_sale/controllers/delivery.py` | Carrier selection with transaction guard |

---

## Related

- [Modules/delivery](odoo-18/Modules/delivery.md) — Base carrier model, rate computation, pickup locations
- [Modules/website_sale](odoo-18/Modules/website_sale.md) — eCommerce base: cart, checkout, payment
- [Modules/website_sale_mondialrelay](odoo-18/Modules/website_sale_mondialrelay.md) — Point Relais integration via `delivery_mondialrelay`
- [Modules/stock](odoo-18/Modules/stock.md) — Inventory; shipping_weight used by `base_on_rule` rate computation
- [Modules/sale](odoo-18/Modules/sale.md) — `carrier_id`, `delivery_set`, `shipping_weight` fields
