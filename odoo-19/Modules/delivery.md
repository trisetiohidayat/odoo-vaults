---
type: module
module: delivery
tags: [odoo, odoo19, delivery, shipping, rate-shipment, pricing-rules, cash-on-delivery, pickup-location, external-providers, COD]
created: 2026-04-06
updated: 2026-04-11
updated_detail: Added hooks, tracking URL, delivery_type override, wizard missing methods, L4 edge cases
---

# Delivery Module (Odoo 19)

**Technical Name:** `delivery`
**Location:** `odoo/addons/delivery/`
**Category:** Sales/Delivery
**License:** LGPL-3
**Depends:** `sale`, `payment_custom`
**Odoo Version:** 19

## Overview

The delivery module provides shipping method management and delivery cost calculation for sales orders. It supports fixed pricing, rule-based pricing (weight, volume, quantity, price), Cash on Delivery (COD) payment integration, pickup location selection, and integration with external shipping providers (DHL, FedEx, UPS, etc. via separate `delivery_*` modules).

A delivery carrier is fundamentally a `delivery.carrier` record paired with a service-type `product.product` (the delivery product). The carrier stores pricing rules, geographic restrictions, product-tag filters, free-shipping thresholds, and margins. Rate computation is delegated to either the built-in pricing engine or to provider-specific methods for external carriers.

---

## Module Architecture

### Core Models

| Model | Technical Name | Purpose |
|-------|---------------|---------|
| Carrier | `delivery.carrier` | Shipping methods with pricing and restrictions |
| Price Rule | `delivery.price.rule` | Pricing rule lines per carrier |
| Zip Prefix | `delivery.zip.prefix` | Zip code prefix restrictions per carrier |
| Sale Order (ext) | `sale.order` | Carrier assignment, shipping weight, pickup data |
| Sale Order Line (ext) | `sale.order.line` | `is_delivery` flag for delivery product lines |
| Partner (ext) | `res.partner` | Default delivery carrier per partner |
| Payment Provider (ext) | `payment.provider` | Cash on Delivery payment mode |
| Payment Transaction (ext) | `payment.transaction` | Auto-confirm SO on COD payment |
| Product Category (ext) | `product.category` | Prevent deletion of delivery category |

### Supporting Models

| Model | Technical Name | Purpose |
|-------|---------------|---------|
| Carrier Wizard | `choose.delivery.carrier` | Modal for selecting delivery method |
| Module (ext) | `ir.module.module` | Action to view carriers from provider module |
| HTTP (ext) | `ir.http` | Frontend translation loading |
| Location Selector | (controller) | JSON endpoints for pickup location management |

### `ir.module.module` Action: `action_view_delivery_methods()`

When an external delivery provider module (e.g., `delivery_dhl`) is installed, its app page shows a smart button "Delivery Methods" that links to `delivery.carrier` filtered by that provider's type. Strips the `delivery_` prefix from the module name to get the `delivery_type` value. Special case: `delivery_mondialrelay` uses context key `search_default_is_mondialrelay` instead of `search_default_delivery_type` (the provider uses a different mechanism to register its type).

### File Structure

```
delivery/
  __manifest__.py
  __init__.py
  const.py                          # COD payment method codes
  models/
    __init__.py
    delivery_carrier.py              # Core carrier model (506 lines)
    delivery_price_rule.py           # Pricing rule model
    delivery_zip_prefix.py           # Zip prefix model
    sale_order.py                    # SO extension
    sale_order_line.py               # SO line extension
    res_partner.py                   # Partner extension
    payment_provider.py               # COD payment provider
    payment_transaction.py           # COD auto-confirm
    product_category.py              # Category protection
    ir_module_module.py              # Provider module action
    ir_http.py                       # Frontend translations
  wizard/
    choose_delivery_carrier.py       # Carrier selection wizard
  controllers/
    location_selector.py             # Pickup location JSON endpoints
  data/
    delivery_data.xml                # Default product, category, carrier
    payment_method_data.xml
    payment_provider_data.xml
    delivery_demo.xml
  security/
    ir_rules.xml                    # Multi-company rule for carriers
```

---

## Model: `delivery.carrier`

**Technical Name:** `delivery.carrier`
**Description:** "Shipping Methods"
**Inherits:** None (standalone model)
**Order:** `sequence, id`
**Table:** `delivery_carrier`

The central model. Every delivery method is a `delivery.carrier` record. The model stores the pricing configuration, geographic restrictions, product-tag-based availability filters, free-shipping thresholds, margins, and delegates actual rate computation to provider-specific methods.

### Fields

#### Identity Fields

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `name` | `Char` | - | Yes | Display name of the delivery method. Used in SO and emails. Translateable. |
| `active` | `Boolean` | `True` | No | Soft-delete toggle. Archived carriers are hidden from selection wizards. |
| `sequence` | `Integer` | `10` | No | Display ordering within carrier lists. Lower values appear first. |
| `company_id` | `Many2one(res.company)` | related to `product_id.company_id` | No | Restricts carrier visibility to a specific company in multi-company setups. Stored, related to product, `readonly=False`. |
| `product_id` | `Many2one(product.product)` | - | Yes | The service product used as the delivery line on SOs. `ondelete='restrict'` prevents deleting the product while the carrier exists. |
| `tracking_url` | `Char` | - | No | Tracking URL shown to customers in the portal. Use `<shipmenttrackingnumber>` as a placeholder that gets substituted with the actual tracking number. |

#### Provider Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `delivery_type` | `Selection` | `'fixed'` | Provider type. Built-in options: `'base_on_rule'` (rule-based pricing), `'fixed'` (fixed price). External providers extend this with values like `'dhl'`, `'fedex'`, `'ups'`. |
| `integration_level` | `Selection` | `'rate_and_ship'` | Controls behavior on SO confirmation. Options: `'rate'` (get rate only), `'rate_and_ship'` (get rate AND create shipment). When `'rate'`, `invoice_policy` is forced to `'estimated'`. |
| `prod_environment` | `Boolean` | `False` | Toggle between test/sandbox (False) and production (True) environments. Used by external providers to switch API endpoints. |
| `debug_logging` | `Boolean` | `False` | When True, XML requests/responses to external shipping APIs are logged to `ir.logging` for debugging. |
| `fixed_price` | `Float` | computed | For `delivery_type='fixed'`. Stored computed field that mirrors `product_id.list_price`. Inverse method `_set_product_fixed_price` writes back to the product's `list_price`. |
| `allow_cash_on_delivery` | `Boolean` | `False` | If True, the Cash on Delivery payment method is available for orders using this carrier. Controls visibility of COD in the payment provider selection. |

#### Geographic Restrictions

| Field | Type | Description |
|-------|------|-------------|
| `country_ids` | `Many2many(res.country)` | Whitelist of countries where this carrier is available. If empty, available everywhere. |
| `state_ids` | `Many2many(res.country.state)` | Whitelist of states within the selected countries. Cascade-cleared when `country_ids` is cleared via `_onchange_country_ids`. |
| `zip_prefix_ids` | `Many2many(delivery.zip.prefix)` | Zip code prefix restrictions. Supports regex via manual `$` anchoring. E.g., `'100$'` matches only exactly `100`, not `1000`. Prefixes are uppercased automatically on create/write. |

#### Product-Based Availability Filters

| Field | Type | Description |
|-------|------|-------------|
| `must_have_tag_ids` | `Many2many(product.tag)` | Carrier is ONLY available if at least one product in the order carries at least one of these tags. Related through `all_product_tag_ids` (inherited tags). |
| `excluded_tag_ids` | `Many2many(product.tag)` | Carrier is NOT available if ANY product in the order carries at least one of these tags. Related through `all_product_tag_ids`. |

**Constraint:** `_check_tags` (`@api.constrains`) prevents a carrier from having the same tag in both fields. Raises `UserError` if violated.

#### Weight and Volume Limits

| Field | Type | Description |
|-------|------|-------------|
| `max_weight` | `Float` | Maximum total order weight (in kg, the system's default weight UoM). Orders exceeding this cannot use this carrier. |
| `weight_uom_name` | `Char` (computed) | Human-readable label of the system's weight UoM. Read-only. Computed via `product.template._get_weight_uom_name_from_ir_config_parameter()`. |
| `max_volume` | `Float` | Maximum total order volume (in cubic meters). Orders exceeding this cannot use this carrier. |
| `volume_uom_name` | `Char` (computed) | Human-readable label of the system's volume UoM. Read-only. Computed via `product.template._get_volume_uom_name_from_ir_config_parameter()`. |

#### Pricing: Margins and Free Shipping

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `margin` | `Float` | `0.0` | Percentage margin added to computed shipping price. Can be negative (discount) but constrained to >= -1 (-100%). Applied as `(1.0 + margin) * price`. |
| `fixed_margin` | `Float` | `0.0` | Fixed amount added after percentage margin. In company currency. |
| `free_over` | `Boolean` | `False` | If True, shipping is free when `amount_total_without_delivery >= amount`. |
| `amount` | `Float` | `1000.0` | Order total threshold (excluding delivery) for free shipping. Only relevant when `free_over=True`. |
| `invoice_policy` | `Selection` | `'estimated'` | Only option is `'estimated'` (estimated cost invoiced). Forced to `'estimated'` when `integration_level='rate'`. |

**Constraints:**
- `_margin_not_under_100_percent`: `CHECK (margin >= -1)` -- prevents margin below -100%.
- `_shipping_insurance_is_percentage`: `CHECK(shipping_insurance >= 0 AND shipping_insurance <= 100)`.

#### Return Label and Insurance

| Field | Type | Description |
|-------|------|-------------|
| `can_generate_return` | `Boolean` (computed) | Default False. External providers override `_compute_can_generate_return` to return True if they support return labels. |
| `return_label_on_delivery` | `Boolean` | Auto-generate return label when delivery picking is validated. Only if `can_generate_return=True`. Onchange resets to False when `can_generate_return` becomes False. |
| `get_return_label_from_portal` | `Boolean` | Allow customer to download return label from portal. Onchange resets to False when `return_label_on_delivery` is unchecked. |
| `supports_shipping_insurance` | `Boolean` (computed) | Default False. External providers override. |
| `shipping_insurance` | `Integer` | Insurance percentage (0-100). Default 0. Added to shipping price as surcharge. |

#### Pricing Rules and Display

| Field | Type | Description |
|-------|------|-------------|
| `price_rule_ids` | `One2many(delivery.price.rule)` | Lines defining the pricing matrix. Only used when `delivery_type='base_on_rule'`. Copy=True. |
| `currency_id` | `Many2one(res.currency)` | Related to `product_id.currency_id`. Convenience field. |
| `carrier_description` | `Text` | Translatable description shown to customers in the SO and confirmation email. Used for delivery instructions. |

### Methods

#### Action Methods

**`toggle_prod_environment()`**
Toggles `prod_environment` between True/False. Iterates over `self` to support bulk toggle.

**`toggle_debug()`**
Toggles `debug_logging` between True/False.

**`install_more_provider()`**
Opens a kanban/list view of available delivery provider modules (modules starting with `delivery_`). Excludes internal modules: `delivery_barcode`, `delivery_stock_picking_batch`, `delivery_iot`. Returns `ir.actions.act_window` for `ir.module.module`.

#### Availability Matching

**`available_carriers(partner, source)`**
Returns carriers from `self` that match the given partner and source document (SO or stock.picking). Delegates to `_match`.

```python
def available_carriers(self, partner, source):
    return self.filtered(lambda c: c._match(partner, source))
```

**`def _is_available_for_order(order)`**
Checks if `self` (single carrier) is available for the given order. Returns False if `_match` fails. For `base_on_rule` delivery types, additionally calls `rate_shipment()` and checks its success status.

**`def _match(partner, source)`** (compound match)
Returns True only if ALL pass: `_match_address`, `_match_must_have_tags`, `_match_excluded_tags`, `_match_weight`, `_match_volume`.

**`def _match_address(partner)`**
- If `country_ids` set and `partner.country_id` not in it -> False
- If `state_ids` set and `partner.state_id` not in it -> False
- If `zip_prefix_ids` set: builds regex `'^prefix1|^prefix2|...'` and tests `partner.zip.upper()`. Returns False if no match.
- Returns True otherwise (including when all restrictions are empty).

**`def _match_must_have_tags(source)`**
- For `sale.order`: uses `source.order_line.product_id`
- For `stock.picking`: uses `source.move_ids.with_prefetch().mapped('product_id')`
- Returns True if `must_have_tag_ids` is empty OR any product has any tag in `must_have_tag_ids` (through `all_product_tag_ids`)
- Raises `UserError` for unsupported source types

**`def _match_excluded_tags(source)`**
- Same product source as above
- Returns True if no product has any tag in `excluded_tag_ids` (through `all_product_tag_ids`)
- Raises `UserError` for unsupported source types

**`def _match_weight(source)`**
- For `sale.order`: `sum(line.product_id.weight * line.product_qty)` over non-cancelled, non-delivery order lines
- For `stock.picking`: `sum(move.product_id.weight * move.product_uom_qty)` over moves
- Returns True if `max_weight == 0` (unlimited) OR `total_weight <= max_weight`

**`def _match_volume(source)`**
- Same pattern as weight, using `product_id.volume` and `max_volume`
- Products with no weight/volume (None or 0.0) do not trigger exclusion

#### Rate Computation

**`def rate_shipment(order)`** (primary API)
Main entry point for getting a shipping rate. Called by the delivery wizard and e-commerce.

**Flow:**
1. Dispatches to `self.{delivery_type}_rate_shipment(order)` if the method exists. Falls back to error dict.
2. Applies fiscal position via `product_id._get_tax_included_unit_price()` with `fiscal_position=order.fiscal_position_id`.
3. Applies margins via `_apply_margins(price, order)`.
4. Stores `carrier_price` (the real price before free_over override).
5. Checks `free_over` threshold: if `order._compute_amount_total_without_delivery() >= self.amount` and `delivery_type != 'base_on_rule'`, sets price to 0.0 with a warning message.
6. Returns dict: `{'success': bool, 'price': float, 'error_message': str|False, 'warning_message': str|False, 'carrier_price': float}`.

**`def fixed_rate_shipment(order)`**
For `delivery_type='fixed'`. Matches address via `_match_address`. Price from `order.pricelist_id._get_product_price(self.product_id, 1.0)` -- supports pricelist-based pricing overrides. Returns standard rate dict.

**`def base_on_rule_rate_shipment(order)`**
For `delivery_type='base_on_rule'`. Matches address. Calls `_get_price_available(order)` which loops order lines to compute `total`, `weight`, `volume`, `quantity`, `wv` (weight*volume). Converts total to company currency, then calls `_get_price_from_picking`. Returns rate dict.

**`def _apply_margins(price, order)`**
Applies margin and fixed_margin to the price. For `fixed` delivery type, returns float price directly -- margins are ignored for fixed pricing. For other types, converts `fixed_margin` from company to sale currency.

**`def _compute_currency(order, price, conversion)`**
Converts `price` using `_get_conversion_currencies`. If currencies are the same, returns price unchanged. Uses `from_currency._convert(price, to_currency, order.company_id, order.date_order)`.

**`def _get_conversion_currencies(order, conversion)`**
Helper returning `(from_currency, to_currency)` tuple. For `'company_to_pricelist'`: `(company_currency, pricelist_currency)`. For `'pricelist_to_company'`: `(pricelist_currency, company_currency)`. Falls back to main company if `self.company_id` is not set. Used by both `_apply_margins()` and `_get_price_available()` for consistent currency handling.

**`def _get_price_available(order)`**
Core pricing engine for rule-based carriers. Runs in `sudo()` to bypass record rules during price computation.

**Computation steps:**
1. Iterate all non-cancelled, non-delivery, non-service order lines
2. Convert qty to product's default UoM via `product_uom_id._compute_quantity()`
3. Accumulate: `weight += weight * qty`, `volume += volume * qty`, `wv += weight * volume * qty`, `quantity += qty`
4. `total = order.amount_total - total_delivery` (excludes existing delivery lines)
5. Convert total to company currency
6. Determine weight: use `context['order_weight']` (from wizard), else `order.shipping_weight` (saved), else computed total weight
7. Call `_get_price_from_picking(total, weight, volume, quantity, wv=wv)`
8. Raises `UserError` if no rule matches

**`def _get_price_dict(total, weight, volume, quantity, wv=0.)`**
Hook method. Returns `{'price': total, 'volume': volume, 'weight': weight, 'wv': wv or volume*weight, 'quantity': quantity}`. External providers override this to add extra fields (e.g., `distance`, `zip_code`) for use in price rule variable factors.

**`def _get_price_from_picking(total, weight, volume, quantity, wv=0.)`**
Evaluates price rules in sequence order. For each rule:
```python
test = safe_eval(line.variable + line.operator + str(line.max_value), price_dict)
price = line.list_base_price + line.list_price * price_dict[line.variable_factor]
```
First matching rule wins. Raises `UserError` if no rule matches.

#### Logging

**`def log_xml(xml_string, func)`**
If `debug_logging=True`, flushes the ORM cache and creates an `ir.logging` record with level DEBUG. Uses a separate cursor/registry to avoid rollback conflicts. Catches `psycopg2.Error` silently -- logging failures should not break shipping.

#### Delivery Type Override

**`def _get_delivery_type(self)`**
Override hook for external providers whose delivery type is not stored on `delivery_type` field but computed dynamically. Default implementation simply returns `self.delivery_type`. Used by `rate_shipment()` to dispatch to the correct `{type}_rate_shipment` method.

#### Onchange Methods

| Method | Trigger | Behavior |
|--------|---------|----------|
| `_onchange_integration_level` | `integration_level` | Forces `invoice_policy='estimated'` if integration_level is `'rate'` |
| `_onchange_can_generate_return` | `can_generate_return` | Resets `return_label_on_delivery=False` if can_generate_return becomes False |
| `_onchange_return_label_on_delivery` | `return_label_on_delivery` | Resets `get_return_label_from_portal=False` if unchecked |
| `_onchange_country_ids` | `country_ids` | Removes states not in selected countries. Clears `zip_prefix_ids` if all countries removed. |

#### Copy

**`def copy_data(default=None)`**
Overrides default copy to append " (copy)" to the carrier name.

---

## Model: `delivery.price.rule`

**Technical Name:** `delivery.price.rule`
**Description:** "Delivery Price Rules"
**Order:** `sequence, list_price, id`
**Table:** `delivery_price_rule`

Pricing matrix lines associated with a `delivery.carrier`. Each rule defines a condition and a price formula.

**Module-level constant `VARIABLE_SELECTION`:**
```python
VARIABLE_SELECTION = [
    ('weight', "Weight"),
    ('volume', "Volume"),
    ('wv', "Weight * Volume"),
    ('price', "Price"),
    ('quantity', "Quantity"),
]
```
This constant is used for both the `variable` (condition metric) and `variable_factor` (multiplier metric) fields. External providers can reuse this constant in their extended rule models.

### Fields

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `name` | `Char` (computed) | - | No | Human-readable description of the rule. Not stored. |
| `sequence` | `Integer` | `10` | Yes | Order of evaluation. First matching rule wins. |
| `carrier_id` | `Many2one(delivery.carrier)` | - | Yes | Parent carrier. `ondelete='cascade'`. Indexed. |
| `currency_id` | `Many2one(res.currency)` | related to `carrier_id.currency_id` | No | Convenience field. |
| `variable` | `Selection` | `'quantity'` | Yes | Order metric for the condition. Options: `'weight'`, `'volume'`, `'wv'` (weight*volume), `'price'` (order total), `'quantity'`. |
| `operator` | `Selection` | `'<='` | Yes | Comparison operator. Options: `'=='`, `'<='`, `'<'`, `'>='`, `'>'`. |
| `max_value` | `Float` | - | Yes | Threshold value for the condition. |
| `list_base_price` | `Float` | `0.0` | Yes | Fixed base price component. Can be 0 for purely variable pricing. |
| `list_price` | `Float` | `0.0` | Yes | Variable rate. Multiplied by `variable_factor`. Can be 0 for purely fixed pricing. |
| `variable_factor` | `Selection` | `'weight'` | Yes | Metric used to multiply `list_price`. Same options as `variable`. |

### Computed Name Generation

Generates strings like:
- `"if weight <= 10.00 then fixed price 5.00 plus 2.00 times weight"`
- `"if price > 500.00 then fixed price 0.00 plus 0.00 times price"` (free shipping example)

### Evaluation

Evaluated in `delivery.carrier._get_price_from_picking()` using `safe_eval()`. **Example rule set for weight-based pricing:**

| Seq | variable | operator | max_value | list_base_price | list_price | variable_factor | Price formula |
|-----|----------|----------|-----------|-----------------|------------|-----------------|---------------|
| 10 | weight | <= | 5 | 10.0 | 0.0 | weight | 10.0 (flat up to 5kg) |
| 20 | weight | <= | 20 | 10.0 | 2.0 | weight | 10.0 + 2.0*weight (up to 20kg) |
| 30 | weight | > | 20 | 50.0 | 1.0 | weight | 50.0 + 1.0*weight (above 20kg) |

---

## Model: `delivery.zip.prefix`

**Technical Name:** `delivery.zip.prefix`
**Description:** "Delivery Zip Prefix"
**Order:** `name, id`
**Table:** `delivery_zip_prefix`

Defines zip code prefix restrictions for carriers. Supports regex patterns.

### Fields

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `name` | `Char` | - | Yes | Zip prefix or regex pattern. Automatically uppercased on create/write. |

### Behavior

- **Auto-uppercase:** Both `create()` and `write()` convert `name` to uppercase.
- **Unique constraint:** `_name_uniq` prevents duplicate prefixes.
- **Regex support:** The `_match_address` method builds a combined regex: `'^prefix1|^prefix2|^prefix3...'`. Supports end-of-string anchoring with `$`: `'100$'` matches `'100'` but not `'1000'`.
- **Association:** Linked to carriers via `delivery.carrier.zip_prefix_ids` Many2many.

---

## Model: `sale.order` (Extension)

**Technical Name:** `sale.order`
**Inheritance:** `_inherit = 'sale.order'`

### Additional Fields

| Field | Type | Description |
|-------|------|-------------|
| `carrier_id` | `Many2one(delivery.carrier)` | The selected delivery method. `check_company=True`. |
| `delivery_message` | `Char` | Read-only message displayed after delivery selection (e.g., "Free shipping applied"). Copied=False. |
| `delivery_set` | `Boolean` (computed) | True if any order line has `is_delivery=True`. |
| `recompute_delivery_price` | `Boolean` | Flag to trigger delivery price recomputation. Set True when order lines change. |
| `is_all_service` | `Boolean` (computed) | True if all non-display-type order lines are service products. Used to determine whether delivery is relevant. |
| `shipping_weight` | `Float` (computed, stored, readonly=False) | Total estimated shipping weight. Computed from `order_line.product_qty * product.weight` for consumable products only. Stored so it can be overridden manually. |
| `pickup_location_data` | `Json` | Selected pickup point location data as JSON. Format varies by carrier. |

### Method: `action_open_delivery_wizard()`

Opens the `choose.delivery.carrier` wizard in a modal form.

**Logic:**
- If `context.get('carrier_recompute')` is set, opens for price update with existing `carrier_id` pre-selected.
- Otherwise, determines default carrier by checking `partner_shipping_id.property_delivery_carrier_id` (falling back to `commercial_partner_id.property_delivery_carrier_id`), then filters to available carriers via `available_carriers(partner_shipping_id, self)`.
- Sets `default_total_weight` from `_get_estimated_weight()`.

### Method: `set_delivery_line(carrier, amount)`

Removes existing delivery lines via `_remove_delivery_line()`, then creates a new delivery line via `_create_delivery_line(carrier, amount)`.

### Method: `_remove_delivery_line()`

Removes delivery lines from the order. If any delivery line has been partially or fully invoiced (`qty_invoiced > 0`), raises `UserError` preventing modification.

### Method: `_create_delivery_line(carrier, price_unit)`

Calls `_prepare_delivery_line_vals()` then creates the line with `sudo()`.

### Method: `_prepare_delivery_line_vals(carrier, price_unit)`

Builds the `sale.order.line` creation dict:
- Sets `lang` context to partner's language
- Fetches taxes from `carrier.product_id.taxes_id`, filtered by company, then mapped through fiscal position
- Builds the line name: `carrier.name: carrier.product_id.description_sale` (or just `carrier.name`)
- If `carrier.free_over` and `price_unit == 0.0`, appends "\nFree Shipping"
- Returns: `{'order_id', 'name', 'price_unit', 'product_uom_qty': 1, 'product_id', 'tax_ids', 'is_delivery': True, 'sequence'}`

### Method: `_set_pickup_location(pickup_location_data)`

Stores pickup location JSON. Checks if carrier supports locations via `{delivery_type}_use_locations` attribute. Sets `pickup_location_data` to parsed JSON or `None`.

### Method: `_get_pickup_locations(zip_code, country, **kwargs)`

Proxies to the carrier's `_{delivery_type}_get_close_locations()` method. Returns dict with `'pickup_locations'` list or `'error'` message.

### Method: `_action_confirm()` (override)

After standard SO confirmation, checks for `pickup_location_data`. If present, creates or finds a partner of type `'delivery'` with `is_pickup_location=True` at the pickup address, then sets it as the shipping partner.

### Method: `_get_estimated_weight()`

Sums `product_qty * weight` for order lines where:
- `product_id.type == 'consu'`
- `not is_delivery`
- `not display_type`
- `product_uom_qty > 0`

Service products and negative quantities are excluded.

### Method: `_compute_amount_total_without_delivery()`

Returns `amount_total - sum(delivery line price_totals)`. Used by `rate_shipment()` for free shipping threshold without double-counting.

### Method: `_compute_partner_shipping_id()` (override)

If the computed shipping partner has `is_pickup_location=True`, resets to the base partner. Prevents pickup location being used as the primary shipping address.

### Method: `_get_update_prices_lines()` (override)

Filters out delivery lines from price list recomputation.

### Method: `_update_order_line_info()` (override)

After updating a line's quantity, calls `onchange_order_line()` to set the `recompute_delivery_price` flag.

---

## Model: `sale.order.line` (Extension)

**Technical Name:** `sale.order.line`
**Inheritance:** `_inherit = 'sale.order.line'`

### Additional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `is_delivery` | `Boolean` | `False` | Marks this line as a delivery product line. |
| `product_qty` | `Float` | computed | Recomputes quantity in the product's default UoM. Handles UoM conversion via `product_uom_id._compute_quantity()`. This compute is used in `_get_estimated_weight()` on the parent order. The delivery line's `product_qty` is always 1.0 (set in `_prepare_delivery_line_vals`). |
| `recompute_delivery_price` | `Boolean` | related | Convenience related field for the order's recompute flag. |

### Key Behaviors

**Cannot be invoiced alone:** `_can_be_invoiced_alone()` returns False for delivery lines.

**Deletable from confirmed orders:** `_check_line_unlink()` excludes delivery lines from the undeletable set.

**Unlink cascade:** When a delivery line is deleted, if the parent order still has a `carrier_id`, that carrier reference is cleared (`order.carrier_id = False`). This resets the delivery method on the order.

**On unlink:** If the line is a delivery line and the order has a `carrier_id`, clears `order.carrier_id`.

**Pricelist exclusion:** `_compute_pricelist_item_id()` explicitly sets `pricelist_item_id = False` for delivery lines, preventing pricelist rules from affecting delivery pricing.

**`_get_invalid_delivery_weight_lines()`:** Returns lines with `product_qty > 0`, `product_id.type` not in `('service', 'combo')`, and `product_id.weight == 0`. Handles combo products correctly via `combo_item_id`.

**`_is_delivery()`:** Convenience method wrapping the `is_delivery` boolean. Used by the base `sale` module to determine line type. `self.ensure_one()` is called before returning.

---

## Model: `res.partner` (Extension)

**Technical Name:** `res.partner`
**Inheritance:** `_inherit = 'res.partner'`

### Additional Fields

| Field | Type | Description |
|-------|------|-------------|
| `property_delivery_carrier_id` | `Many2one(delivery.carrier)` | Company-dependent default delivery method for this partner. Used to pre-select a carrier when creating SOs. |
| `is_pickup_location` | `Boolean` | Marks this partner/address as a pickup point location. Used to exclude from delivery address selection. |

### Method: `_get_delivery_address_domain()` (override)

Extends base domain with `Domain('is_pickup_location', '=', False)`, preventing pickup location partners from appearing in delivery address dropdown on SOs.

---

## Model: `payment.provider` (Extension)

**Technical Name:** `payment.provider`
**Inheritance:** `_inherit = 'payment.provider'`

### Additional Fields

| Field | Type | Description |
|-------|------|-------------|
| `custom_mode` | `Selection` (extends) | Adds `'cash_on_delivery'` option to the provider's custom mode selection. |

### Method: `_get_compatible_providers()` (override)

Filters out COD payment providers when the sale order's selected carrier has `allow_cash_on_delivery=False`. Uses `payment_utils.add_to_report()` to add a reason to the availability report.

---

## Model: `payment.transaction` (Extension)

**Technical Name:** `payment.transaction`
**Inheritance:** `_inherit = 'payment.transaction'`

### Method: `_post_process()` (override)

After standard payment post-processing, checks for COD transactions in `'pending'` state. For each matching transaction, confirms draft SOs with `send_email=True` context. This auto-confirms the SO when customer selects COD at checkout.

---

## Model: `product.category` (Extension)

**Technical Name:** `product.category`
**Inheritance:** `_inherit = 'product.category'`

### Method: `_unlink_except_delivery_category()`

`@api.ondelete(at_uninstall=False)` hook. Raises `UserError` if attempting to delete the `delivery.product_category_deliveries` record.

---

## Wizard: `choose.delivery.carrier`

**Technical Name:** `choose.delivery.carrier`
**Type:** `TransientModel`
**Description:** "Delivery Carrier Selection Wizard"

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `order_id` | `Many2one(sale.order)` | Required. `ondelete='cascade'`. |
| `partner_id` | `Many2one(res.partner)` | Related to `order_id.partner_id`. |
| `carrier_id` | `Many2one(delivery.carrier)` | Selected carrier. Domain restricted to `available_carrier_ids`. |
| `delivery_type` | `Selection` | Related to `carrier_id.delivery_type`. |
| `delivery_price` | `Float` | Final computed delivery price (after all adjustments). |
| `display_price` | `Float` | Carrier's base price before free_over override. |
| `currency_id` | `Many2one(res.currency)` | Related to `order_id.currency_id`. |
| `company_id` | `Many2one(res.company)` | Related to `order_id.company_id`. |
| `available_carrier_ids` | `Many2many(delivery.carrier)` (computed) | Carriers matching the order's shipping address, product tags, weight, and volume. |
| `delivery_message` | `Text` | Warning/info message from carrier rate computation. |
| `total_weight` | `Float` | Total shipping weight. Related to `order_id.shipping_weight` with `readonly=False`. |
| `weight_uom_name` | `Char` | Display label for weight UoM. |

### Method: `_compute_available_carrier()`

Searches all carriers in the order's company, then filters via `available_carriers(partner_shipping_id, order)`.

### Method: `_compute_invoicing_message()`

Returns an empty string (reserved for future use). Currently returns a blank message regardless of carrier or partner state.

### Method: `_onchange_order_id()`

Triggered when the wizard's order changes. Only re-computes delivery rate if the carrier is set, the order already has a delivery line, and the delivery type is NOT `'fixed'` or `'base_on_rule'`. Returns a warning notification if rate computation fails.

### Method: `_get_delivery_rate()`

Calls `carrier_id.with_context(order_weight=self.total_weight).rate_shipment(order_id)`. Stores `delivery_message`, `delivery_price` (final), and `display_price` (original).

### Method: `update_price()`

Re-runs rate calculation and reopens the wizard with updated prices. Used for weight changes.

### Method: `button_confirm()`

Calls `order_id.set_delivery_line(self.carrier_id, self.delivery_price)` and writes `recompute_delivery_price=False` and `delivery_message` on the SO.

---

## Controller: `location_selector`

**Routes:**
- `/delivery/set_pickup_location` (JSON-RPC, auth: user)
- `/delivery/get_pickup_locations` (JSON-RPC, auth: user)

### `delivery_set_pickup_location(order_id, pickup_location_data)`

Stores the JSON pickup location data on the order via `order._set_pickup_location()`.

### `delivery_get_pickup_locations(order_id, zip_code=None)`

Returns pickup locations for a given zip code. Determines country from GeoIP or falls back to the order's shipping address country. Proxies to `order._get_pickup_locations()`.

---

## Module Lifecycle Hooks

### `post_init_hook(env)`

Called automatically after the module is installed. Executes `setup_provider(env, 'custom', custom_mode='cash_on_delivery')` to activate the COD payment provider configuration when the module is first installed. This ensures COD is ready to use without manual configuration.

### `uninstall_hook(env)`

Called automatically when the module is uninstalled. Executes `reset_payment_provider(env, 'custom', custom_mode='cash_on_delivery')` to remove COD payment provider configuration. Prevents orphaned payment provider records after module removal.

### `ir_http._get_translation_frontend_modules_name()` (Extension)

Adds `'delivery'` to the list of modules whose terms are loaded for frontend translations. This ensures carrier names and descriptions are translatable in the e-commerce/shop context.

---

## Default Data Records

### Product Category
**External ID:** `delivery.product_category_deliveries`
**Name:** "Deliveries"

The category for all delivery product records. Cannot be deleted.

### Default Product
**External ID:** `delivery.product_product_delivery`
**Name:** "Standard delivery" | **Type:** `service` | **Sale OK:** `False` | **List Price:** `0.0`

### Default Carrier
**External ID:** `delivery.free_delivery_carrier`
**Name:** "Standard delivery" | **Delivery Type:** `fixed` | **Fixed Price:** `0.0`

### Payment Provider: Cash on Delivery
**External ID:** `delivery.payment_provider_cod`
**Provider Code:** `custom` | **Custom Mode:** `cash_on_delivery`
**Linked Module:** `base.module_delivery` -- links the payment provider to this delivery module, enabling automatic uninstall hook triggering when delivery is removed.
**Payment Method:** `delivery.payment_method_cash_on_delivery` (`code='cash_on_delivery'`)

---

## L4: Pickup Location Data Flow and JSON Contract

The `pickup_location_data` Json field on `sale.order` stores carrier-specific pickup point information. The format is not enforced by Odoo -- it is entirely carrier-dependent (external providers like `delivery_mondialrelay` define their own JSON structure).

**Common expected fields (carrier-specific):**
- `name`: Pickup point name
- `street`, `city`, `zip_code`, `country_code`: Address components
- `state`: State code (optional)

**Data lifecycle:**
1. E-commerce JS fetches available locations via `/delivery/get_pickup_locations`
2. Customer selects a location; JS stores data via `/delivery/set_pickup_location`
3. On SO confirmation (`_action_confirm()`), a `res.partner` of type `'delivery'` is created at the pickup address with `is_pickup_location=True`
4. `_compute_partner_shipping_id()` resets the shipping partner back to the customer (not the pickup point) when `is_pickup_location=True` is detected -- ensuring the SO's shipping address stays as the customer address while the picking is addressed to the pickup point

**Security note:** `pickup_location_data` is JSON stored server-side. The JS controller validates the structure is not enforced at write time -- it relies entirely on the carrier's `_set_pickup_location()` to parse or reject invalid data.

---

## L4: Wizard Computed Domain and Carrier Filtering

The wizard's `carrier_id` field uses a domain bound to the computed `available_carrier_ids` field:

```python
domain = "[('id', 'in', available_carrier_ids)]"
```

This means the carrier dropdown only shows carriers that pass all `_match()` checks for the current SO. The domain is evaluated client-side against the pre-computed recordset, not re-filtered server-side.

**Performance note:** `available_carrier_ids` is computed via `_compute_available_carrier()` which calls `available_carriers()` on every carrier in the system filtered by company. For databases with hundreds of carriers, this triggers N `_match()` calls (one per carrier's `_match_*` chain). Consider indexing `delivery.carrier.company_id`, `country_ids`, `state_ids`, and `active`.

---

## L4: Weight Override Context Chain

The `shipping_weight` field on `sale.order` serves as a manual override for the computed weight used in rate calculation. It is threaded through the system via context:

```
choose.delivery.carrier.total_weight  -->  context['order_weight']  -->  _get_price_available()  -->  _get_price_from_picking()
```

Priority order in `_get_price_available()`:
1. `context['order_weight']` (from wizard, user-entered weight)
2. `order.shipping_weight` (manually saved on the SO)
3. Computed `sum(line.product_id.weight * line.product_qty)` (automatic fallback)

This allows dispatch/shipping teams to correct weight mismatches without editing the product master data.

---

## L4: `fixed_price` Inverse Cycle and Pricing Priority

For `delivery_type='fixed'`, there are two price sources that interact:

1. **Carrier `fixed_price` field** -- mirrors `product_id.list_price` (stored computed, inverse writes back to product)
2. **Pricelist price** -- returned by `pricelist_id._get_product_price(product, 1.0)` in `fixed_rate_shipment()`

The `fixed_price` inverse cycle means editing the carrier's fixed price in the delivery carrier form writes directly to the product's `list_price`. The product's pricelist rules (if any) then determine what the customer pays. This gives two ways to control fixed price: directly on the carrier form, or via the product's pricelist rules.

---

## Security

### Record Rules
**`delivery_carrier_comp_rule`:** Multi-company rule for `delivery.carrier`.
- Domain: `[('company_id', 'in', company_ids + [False])]`
- Allows access to carriers with the user's current company, plus carriers with no company set (global).

### Constants
**`const.DEFAULT_PAYMENT_METHOD_CODES = {'cash_on_delivery'}`**
Set of payment method codes activated when COD is enabled.

---

## L3: Edge Cases and Workflow Triggers

### rate_shipment Flow

```
rate_shipment(order)
  |
  +-- delivery_type == 'fixed' --> fixed_rate_shipment()
  |     +-- _match_address() fails --> {success: False}
  |     +-- _match_address() passes --> get price from pricelist
  |
  +-- delivery_type == 'base_on_rule' --> base_on_rule_rate_shipment()
  |     +-- _match_address() fails --> {success: False}
  |     +-- _get_price_available() raises UserError --> {success: False}
  |     +-- no rule matches --> UserError("Not available for current order")
  |
  +-- External provider (e.g., 'dhl') --> dhl_rate_shipment()
        (provider-specific implementation)
```

After type-specific rate computation:
1. Apply fiscal position (tax-inclusive pricing)
2. Apply margin + fixed_margin
3. Store `carrier_price` (original)
4. Check `free_over` threshold (only for non-rule-based)
5. Return dict with `success`, `price`, `error_message`, `warning_message`, `carrier_price`

### free_over Edge Case

```python
if (res['success']
    and self.free_over
    and self.delivery_type != 'base_on_rule'  # <-- rule-based excluded
    and self._compute_currency(order, amount_without_delivery, 'pricelist_to_company') >= self.amount):
```

**Key point:** `free_over` does NOT apply to `base_on_rule` delivery types. Rule-based carriers express free shipping through pricing rules (e.g., `list_base_price=0`, `list_price=0`).

**Fiscal position application:** The fiscal position is applied via `_get_tax_included_unit_price()` AFTER the type-specific rate method returns. This means both `base_on_rule` and `fixed` rates get tax adjustments. The fiscal position is read from `order.fiscal_position_id`. For `base_on_rule`, the currency conversion (`_compute_currency`) happens before the fiscal position application.

### Cash on Delivery Workflow

1. **SO Creation:** User selects a carrier with `allow_cash_on_delivery=True`
2. **Payment Selection:** E-commerce shows COD via `_get_compatible_providers()` override
3. **Payment:** Customer selects COD (transaction created with `state='pending'`)
4. **Post-Processing:** `payment.transaction._post_process()` detects COD pending transaction and calls `sale_order.action_confirm()`
5. **Picking:** Standard SO confirmation creates the delivery picking

### Weight/Volume Calculation Edge Cases

- **Service products:** excluded from weight/volume calculations in `_get_price_available()`, `_match_weight()`, and `_match_volume()`.
- **Cancelled lines:** excluded from `_get_price_available()`.
- **Already-delivery lines:** excluded from `_get_price_available()` -- prevents double-counting.
- **UoM conversion:** `_get_price_available()` converts line quantities to the product's default UoM before multiplying by weight/volume. This ensures "5 dozens" of items weigh 5 dozen-times-the-item-weight.
- **Negative quantities:** excluded from `_get_estimated_weight()`.
- **Combo products:** `_get_invalid_delivery_weight_lines()` correctly traverses `combo_item_id` to find the actual product within a combo.

### Zip Prefix Regex Patterns

```python
regex = re.compile('|'.join(['^' + zip_prefix for zip_prefix in self.zip_prefix_ids.mapped('name')]))
if not partner.zip or not re.match(regex, partner.zip.upper()):
    return False
```
- Each prefix gets `^` prepended automatically
- User can add `$` manually: `'100$'` becomes `'^100$'` -- matches exactly "100"
- Without `$`, `'10'` matches `'100'`, `'1000'`, `'1024'`, etc.
- Multiple prefixes are OR'd together with `|`
- Empty `zip_prefix_ids` means no zip restriction (returns True)

### Pickup Location Handling

On SO confirmation (`_action_confirm()`), if `pickup_location_data` is set, Odoo creates a new `res.partner` record of type `'delivery'` with `is_pickup_location=True`. This allows the picking to be created for the actual warehouse/retail location while keeping the customer's address on the SO.

---

## L4: Performance, Historical Changes, and Security

### Performance Considerations

#### High-Risk Area: `_get_price_available()`

The method loops through order lines and accesses `product_id.weight`, `product_id.volume`, `line.product_uom_id._compute_quantity()`. Within a loop on `order.order_line`, each `line.product_id` benefits from Odoo's prefetching -- all related product fields are loaded in a single batch query.

The UoM conversion `product_uom_id._compute_quantity()` may involve UoM factor queries. For typical order sizes this is acceptable. For very large orders (hundreds of lines), this is the primary performance consideration.

#### Medium-Risk Area: `_match_*` Methods

Called for every carrier in `available_carriers()`. Each `_match()` triggers `mapped('product_id')` on order lines or moves (batched). The company filter on `available_carriers()` reduces the carrier set before these checks run.

#### Stored vs Unstored Fields

- `fixed_price` is stored (`store=True`) -- only recomputes when product's `list_price` changes.
- `carrier.can_generate_return` and `supports_shipping_insurance` are unstored computed fields returning False in the base module.

#### `_get_price_from_picking()` Rule Evaluation

Iterates through `self.price_rule_ids` in sequence order. Each rule involves a `safe_eval()` call. First matching rule wins, so ordering rules by likelihood reduces average evaluation cost.

### Odoo 18 to Odoo 19 Changes

#### New Features in Odoo 19

1. **Product Tags Filtering:** `must_have_tag_ids` and `excluded_tag_ids` are new. Allows carrier availability based on product tags through `all_product_tag_ids` (inherited tags).

2. **Shipping Weight Override:** `shipping_weight` field on `sale.order` is new. Allows manual override of computed shipping weight, passed via context to `_get_price_available()`.

3. **Volume Limits:** `max_volume` and `volume_uom_name` fields are new. Volume-based pricing is a new dimension.

4. **COD via Payment Module:** Cash on Delivery as a proper payment method via `payment.provider` with `custom_mode='cash_on_delivery'`. The `payment.transaction._post_process()` override for COD auto-confirmation is part of this integration.

5. **Pickup Location:** `is_pickup_location` on `res.partner` and associated pickup location data handling are new in Odoo 19.

6. **WV (Weight*Volume) Variable:** `wv` variable factor in price rules. Allows pricing based on dimensional weight, common in freight pricing.

7. **`_get_price_dict()` Hook:** More formally exposed as a hook allowing external providers to add custom variables for rule evaluation.

#### Breaking Changes

1. **Fiscal Position on Delivery:** In prior versions, delivery lines used `product_id.taxes_id` directly. In Odoo 19, `rate_shipment()` applies the SO's fiscal position via `_get_tax_included_unit_price()`.

2. **free_over Exclusion for Rule-Based:** The explicit check `self.delivery_type != 'base_on_rule'` is deliberate. Previously, behavior may have been inconsistent.

3. **Delivery Line Pricelist Override:** In Odoo 19, delivery lines explicitly set `pricelist_item_id = False` in `_compute_pricelist_item_id()`, preventing pricelist rules from modifying delivery line prices.

### External Provider Integration Pattern

The `delivery.carrier` model is designed for extension by external provider modules:

```python
class DeliveryCarrierDHL(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(
        selection_add=[('dhl', 'DHL')],
        ondelete='restrict',
    )

    def dhl_rate_shipment(self, order):
        # Build request, call DHL API, parse response
        return {'success': bool, 'price': float, ...}

    def dhl_send_shipping(self, picking):
        # Create shipment, generate label
        ...

    def dhl_get_tracking_link(self, picking):
        # Return tracking URL
        ...
```

OCA modules (e.g., `delivery-carrier-cost-estimation`, `delivery-iata`) follow this pattern. The `log_xml()` method provides a standardized way to log external API communications.

### Security Considerations

1. **safe_eval in `_get_price_from_picking`:** Evaluates expressions like `"weight <= 10.0"` against a controlled dictionary containing only float values from order data. No user-controlled strings enter the eval. Considered safe as long as `price_dict` values remain numeric.

2. **No SQL Injection:** All database access uses the ORM. `_get_price_available()` uses `sudo()` but only reads order data and computes prices.

3. **Pickup Location Data:** Stored as JSON. No server-side validation of the JSON structure -- it is carrier-dependent.

4. **Debug Logging:** When enabled, XML request/response bodies from external providers are stored in `ir.logging`. These may contain sensitive data. Debug logging should only be enabled during development/troubleshooting.

5. **Multi-company:** `delivery_carrier_comp_rule` ensures carriers are scoped to their company. Carriers with `company_id=False` are accessible to all companies. `check_company=True` on `carrier_id` in `sale.order` ensures carrier belongs to the correct company.

6. **Delivery Line Deletion:** `_remove_delivery_line()` prevents modification of delivery costs once invoiced. The `unlink()` override allows deletion of delivery lines from confirmed orders. The invoicing check provides the safety net.

---

## Related Models

| Model | Module | Description |
|-------|--------|-------------|
| `sale.order` | `sale` | Sales order -- extended by delivery |
| `sale.order.line` | `sale` | Sales order line -- extended by delivery |
| `stock.picking` | `stock` | Delivery picking -- uses carrier for shipping |
| `stock.move` | `stock` | Stock moves -- matched by delivery for weight/volume |
| `product.product` | `product` | Products -- the delivery service product |
| `product.tag` | `product` | Product tags -- used for carrier filtering |
| `payment.provider` | `payment` | Payment providers -- COD mode |
| `payment.transaction` | `payment` | Payment transactions -- COD auto-confirm |

## Related Documentation

- [Modules/sale](Modules/sale.md)
- [Modules/stock](Modules/stock.md)
- [Modules/payment](Modules/payment.md)
- [Core/API](Core/API.md)
- [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md)

---

## Loyalty Integration (`sale_loyalty_delivery`)

**Module:** `sale_loyalty_delivery`
**Location:** `odoo/addons/sale_loyalty_delivery/`
**Depends:** `sale_loyalty`, `delivery`
**Auto-installs:** True (when both dependencies are present)

### Overview

This module bridges the loyalty and delivery modules. It adds a **Free Shipping** reward type to the loyalty system, allowing programs to grant free or discounted shipping as a reward. The `delivery` module itself contains **no loyalty code** - the integration is entirely in `sale_loyalty_delivery`.

### Program Type Impact

The module adds a `shipping` reward to the default `loyalty` program template with `required_points: 100`:

```python
# sale_loyalty_delivery/models/loyalty_program.py
res['loyalty']['reward_ids'].append((0, 0, {
    'reward_type': 'shipping',
    'required_points': 100,
}))
```

The `promotion` template description is also overridden to mention free shipping instead of a discount coupon.

### Reward Type Extension

`loyalty.reward` is extended via `_inherit` to add `'shipping'` to the `reward_type` selection:

```python
# sale_loyalty_delivery/models/loyalty_reward.py
reward_type = fields.Selection(
    selection_add=[('shipping', 'Free Shipping')],
    ondelete={'shipping': 'set default'})
```

The `ondelete='set default'` means if the `sale_loyalty_delivery` module is uninstalled, any `shipping` reward types revert to the default (empty/new value), which will likely trigger a validation error - a deliberate protection to prevent orphaned shipping rewards.

### Free Shipping Reward Computation

The core logic is in `sale.order._get_reward_values_free_shipping()`:

```python
# sale_loyalty_delivery/models/sale_order.py
def _get_reward_values_free_shipping(self, reward, coupon, **kwargs):
    delivery_line = self.order_line.filtered(lambda l: l.is_delivery)[:1]
    taxes = delivery_line.product_id.taxes_id._filter_taxes_by_company(self.company_id)
    taxes = self.fiscal_position_id.map_tax(taxes)
    max_discount = reward.discount_max_amount or float('inf')
    return [{
        'name': _('Free Shipping - %s', reward.description),
        'reward_id': reward.id,
        'coupon_id': coupon.id,
        'points_cost': reward.required_points if not reward.clear_wallet
                        else self._get_real_points_for_coupon(coupon),
        'product_id': reward.discount_line_product_id.id,
        'price_unit': -min(max_discount, delivery_line.price_unit or 0),
        'product_uom_qty': 1,
        'order_id': self.id,
        'is_reward_line': True,
        'sequence': max(self.order_line.filtered(lambda x: not x.is_reward_line)
                         .mapped('sequence'), default=0) + 1,
        'tax_ids': [Command.clear()] + [Command.link(tax.id) for tax in taxes],
    }]
```

Key behaviors:
- Finds the current delivery line (`is_delivery=True`) on the order
- Caps the discount at `reward.discount_max_amount` (allows partial free shipping, e.g., free shipping up to $50)
- `float('inf')` as default means full delivery cost is covered when no cap is set
- Tax IDs are inherited from the delivery product, then cleared and relinked after fiscal position mapping
- The reward line `price_unit` is negative, reducing the order total

### Threshold Line Exclusion

Delivery lines must not count toward the minimum purchase threshold for loyalty programs:

```python
def _get_no_effect_on_threshold_lines(self):
    res = super()._get_no_effect_on_threshold_lines()
    return res + self.order_line.filtered(
        lambda line: line.is_delivery or line.reward_id.reward_type == 'shipping')
```

This ensures the delivery cost is excluded from `amount_untaxed` when computing whether the minimum purchase threshold is met. Both physical delivery lines and the free shipping reward line are excluded.

### Point Generation Exclusion

Delivery lines do not generate loyalty points:

```python
def _get_not_rewarded_order_lines(self):
    order_line = super()._get_not_rewarded_order_lines()
    return order_line.filtered(lambda line: not line.is_delivery)
```

The `is_delivery` flag on `sale.order.line` is the sole criterion. No discount-type check is needed because delivery lines are never reward lines from the base delivery module perspective.

### Shipping Reward Mutex

Only one shipping reward can be claimed per order:

```python
def _get_claimable_rewards(self, forced_coupons=None):
    res = super()._get_claimable_rewards(forced_coupons)
    if any(reward.reward_type == 'shipping' for reward in self.order_line.reward_id):
        # Allow only one reward of type shipping at the same time
        filtered_res = {}
        for coupon, rewards in res.items():
            filtered_rewards = rewards.filtered(lambda r: r.reward_type != 'shipping')
            if filtered_rewards:
                filtered_res[coupon] = filtered_rewards
        res = filtered_res
    return res
```

If the order already has a shipping reward applied (any coupon), all shipping rewards are removed from the claimable set. This prevents double-applying free shipping discounts from two different programs simultaneously.

### Delivery Line Amount Exclusion

The base `_compute_amount_total_without_delivery()` in `sale_loyalty` is overridden to also exclude e-wallet and gift card lines from the threshold calculation:

```python
def _compute_amount_total_without_delivery(self):
    res = super()._compute_amount_total_without_delivery()
    return res - sum(
        self.order_line.filtered(
            lambda l: l.coupon_id and l.coupon_id.program_type in ['ewallet', 'gift_card']
        ).mapped('price_unit')
    )
```

### L4: Cross-Module Data Flow

```
sale.order (confirms)
  └─→ _update_programs_and_rewards()
        └─→ _get_claimable_rewards()    [sale_loyalty]
              └─→ filters out 'shipping' if already claimed   [sale_loyalty_delivery]
  └─→ _add_reward_lines() [sale_loyalty]
        └─→ _get_reward_line_values()
              └─→ reward_type == 'shipping' → _get_reward_values_free_shipping() [sale_loyalty_delivery]
                    └─→ Creates sale.order.line (is_reward_line=True, price_unit=-N)

Order total computation
  └─→ _get_no_effect_on_threshold_lines()   [sale_loyalty]
        └─→ includes: is_delivery=True, reward_type='shipping'  [sale_loyalty_delivery]
  └─→ _compute_amount_total_without_delivery()   [sale_loyalty_delivery]
        └─→ excludes ewallet/gift_card lines
```

### L4: Performance Considerations

The `sale_loyalty_delivery` hooks are all lightweight:
- `filtered()` calls on `order_line` — O(n) where n = number of order lines (typically small, < 100)
- No database writes in the delivery overrides themselves
- `_get_reward_values_free_shipping()` creates one dict (not a write) — the actual ORM write happens in `sale_loyalty._add_reward_lines()`
- `_get_claimable_rewards()` filters an existing recordset — O(m) where m = number of available rewards

The module adds no N+1 risk because all data is already loaded by the calling `sale_loyalty` methods.

### L4: Failure Modes

| Failure | Cause | Result |
|---------|-------|--------|
| No delivery line on order | Order has no shipping method selected | `_get_reward_values_free_shipping()` returns line with `price_unit=0` (free shipping on $0 = $0) |
| `delivery_line.product_id.taxes_id` empty | Delivery product has no taxes configured | Empty `tax_ids` on reward line — no tax adjustment |
| Multiple shipping rewards claimed | Race condition or manual coupon code entry | `_get_claimable_rewards()` mutex prevents new claims; existing claims remain unless manually removed |
| `discount_max_amount < delivery_line.price_unit` | Reward cap is lower than actual shipping cost | Partial free shipping: customer pays `delivery_cost - max_discount` |
| `clear_wallet=True` on shipping reward | Wallet exhaustion mode | All card points are consumed on redemption regardless of points cost |

### L4: Security Notes

- The free shipping reward reduces the order total by the delivery cost. This could theoretically be abused by setting up a program where the "delivery product" has an inflated price, and the shipping reward grants a large discount.
- Mitigations: only internal users with `loyalty.program` write access can create shipping rewards. The `discount_max_amount` cap should be set to a reasonable maximum.
- No additional ACLs beyond the base `loyalty.program` and `loyalty.reward` permissions.

---

### Updated: Related Models

| Model | Module | Description |
|-------|--------|-------------|
| `sale.order` | `sale` | Sales order -- extended by delivery and sale_loyalty_delivery |
| `sale.order.line` | `sale` | Sales order line -- extended by delivery (`is_delivery`), sale_loyalty (`is_reward_line`) |
| `stock.picking` | `stock` | Delivery picking -- uses carrier for shipping |
| `stock.move` | `stock` | Stock moves -- matched by delivery for weight/volume |
| `product.product` | `product` | Products -- the delivery service product |
| `product.tag` | `product` | Product tags -- used for carrier filtering |
| `payment.provider` | `payment` | Payment providers -- COD mode |
| `payment.transaction` | `payment` | Payment transactions -- COD auto-confirm |
| `loyalty.program` | `loyalty` | Loyalty programs -- extended by sale_loyalty_delivery |
| `loyalty.reward` | `loyalty` | Rewards -- extended with `shipping` reward_type |
| `loyalty.card` | `loyalty` | Loyalty cards -- shipping rewards redeemed against cards |
| `sale.order.coupon.points` | `sale_loyalty` | Pending point allocation for shipping rewards |

---

### Updated: Related Documentation

- [Modules/sale](Modules/sale.md)
- [Modules/sale_loyalty](Modules/sale_loyalty.md) or [Modules/loyalty](Modules/loyalty.md)
- [Modules/stock](Modules/stock.md)
- [Modules/payment](Modules/payment.md)
- [Core/API](Core/API.md)
- [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md)
