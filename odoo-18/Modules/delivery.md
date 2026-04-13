---
Module: delivery
Version: Odoo 18
Type: Integration
Tags: [#odoo, #odoo18, #delivery, #shipping, #carrier, #pricing, #sale, #stock]
---

# Delivery Costs Module

**Module:** `delivery`
**Path:** `~/odoo/odoo18/odoo/addons/delivery/`
**Category:** Sales/Delivery
**Depends:** `sale`
**License:** LGPL-3

Core delivery carrier framework. Provides carrier configuration, pricing rules, pickup location management, and shipping cost integration with `sale.order`. This is the base module — third-party carrier integrations (DHL, FedEx, etc.) extend it via the provider pattern.

> **L4 Architecture:** `delivery` is a framework module. It defines `delivery.carrier` with a plug-in architecture for external shipping providers. Pricing can be rule-based (`base_on_rule`) or fixed. The `sale.order` is extended to carry delivery method selection and shipping weight. Separate modules (`stock_picking_delivery`) add actual shipment tracking and label generation to `stock.picking`.

---

## Models

### `delivery.carrier` (Core Model)

Shipping provider configuration. The central model of the delivery system.

**Inheritance:** `models.Model`
**External ID:** `delivery.model_delivery_carrier`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Delivery method display name — shown in SO wizard and confirmation emails |
| `active` | Boolean | Hide inactive carriers. Default `True` |
| `sequence` | Integer | Display order when listing carriers. Default `10` |
| `delivery_type` | Selection | Provider type. Core options: `'base_on_rule'` (rule-based pricing), `'fixed'` (fixed price). Extensible by carrier modules |
| `integration_level` | Selection | `'rate'` (get rate only) or `'rate_and_ship'` (get rate and create shipment). Default `'rate_and_ship'` |
| `prod_environment` | Boolean | Toggle production vs. test/sandbox mode. Default `False` |
| `debug_logging` | Boolean | Log XML requests for debugging. Default `False` |
| `company_id` | Many2one `res.company` | Derived from `product_id.company_id`. Stored, readonly |
| `product_id` | Many2one `product.product` | **Required.** Delivery product used as the SO line product. Ondelete: `restrict` |
| `tracking_url` | Char | Tracking link template. Use `<shipmenttrackingnumber>` placeholder. Example: `https://track.example.com/?ref=<shipmenttrackingnumber>` |
| `currency_id` | Many2one `res.currency` (related) | From `product_id.currency_id` |
| `invoice_policy` | Selection | Currently only `'estimated'` — customer invoiced at estimated cost |
| `country_ids` | Many2many `res.country` | Restrict carrier to specific destination countries. Empty = worldwide |
| `state_ids` | Many2many `res.country.state` | Restrict carrier to specific destination states |
| `zip_prefix_ids` | Many2many `delivery.zip.prefix` | Restrict carrier to specific zip code prefixes. Supports regex (append `$` to match exact prefix) |
| `max_weight` | Float | Maximum order weight (in `weight_uom_name`). Exceeds = carrier unavailable |
| `weight_uom_name` | Char (computed) | Unit label from config parameter |
| `max_volume` | Float | Maximum order volume. Exceeds = carrier unavailable |
| `volume_uom_name` | Char (computed) | Volume unit label |
| `must_have_tag_ids` | Many2many `product.tag` | Order must contain at least one product with one of these tags |
| `excluded_tag_ids` | Many2many `product.tag` | Order is rejected if any product has one of these tags |
| `carrier_description` | Text | Customer-facing description shown on SO and confirmation email |
| `margin` | Float | Percentage added to computed shipping price. Can be negative (discount). Constraint: `>= -1` |
| `fixed_margin` | Float | Fixed amount added to computed shipping price after margin percentage |
| `free_over` | Boolean | Enable free shipping above `amount` threshold. Default `False` |
| `amount` | Float | Order amount threshold for free shipping. Default `1000` (company currency) |
| `can_generate_return` | Boolean (computed) | Whether this carrier supports return label generation. Override in carrier modules |
| `return_label_on_delivery` | Boolean | Auto-generate return label when delivery is validated |
| `get_return_label_from_portal` | Boolean | Allow customer to download return label from portal |
| `supports_shipping_insurance` | Boolean (computed) | Whether this carrier supports insurance |
| `shipping_insurance` | Integer | Insurance percentage (0–100). Default `0` |
| `price_rule_ids` | One2many `delivery.price.rule` | Pricing rules (only used when `delivery_type = 'base_on_rule'`) |

#### SQL Constraints

```python
('margin_not_under_100_percent', 'CHECK (margin >= -1)', 'Margin cannot be lower than -100%')
('shipping_insurance_is_percentage', 'CHECK(shipping_insurance >= 0 AND shipping_insurance <= 100)', ...)
```

#### Key Methods

**`rate_shipment(order)`** — Main pricing method. Dispatches to `{delivery_type}_rate_shipment()`. Returns:
```python
{'success': bool, 'price': float, 'error_message': str|False,
 'warning_message': str|False, 'carrier_price': float}
```

Flow:
1. Calls `{delivery_type}_rate_shipment()` (e.g., `fixed_rate_shipment` or `base_on_rule_rate_shipment`)
2. Applies fiscal position tax to the price
3. Applies carrier margins (`_apply_margins`)
4. Saves as `carrier_price` (original before free-over override)
5. If `free_over` and order total >= `amount` and not `base_on_rule`: sets `price = 0.0`, adds warning

**`log_xml(xml_string, func)`** — Writes XML debug log to `ir.logging` if `debug_logging = True`. Uses a separate DB cursor to avoid rollback.

**`fixed_rate_shipment(order)`** — Pricing for `delivery_type = 'fixed'`.
- Uses `_match_address()` to validate destination
- Returns price from `order.pricelist_id._get_product_price(self.product_id, 1.0)`

**`base_on_rule_rate_shipment(order)`** — Pricing for `delivery_type = 'base_on_rule'`.
- Uses `_match_address()` to validate destination
- Calls `_get_price_available(order)` to compute price from rules
- Converts currency to pricelist currency

**`_get_price_available(order)`** — Computes rule-based price.
- Runs as sudo
- Aggregates order line data: `total`, `weight`, `volume`, `quantity`, `wv` (weight*volume)
- Excludes `cancel` lines, `is_delivery` lines, `service` type products
- Applies `shipping_weight` from context/order if set
- Calls `_get_price_from_picking()`

**`_get_price_from_picking(total, weight, volume, quantity, wv)`** — Applies price rules.
- Iterates `price_rule_ids` in sequence order
- Evaluates `safe_eval(line.variable + line.operator + str(line.max_value), price_dict)`
- First matching rule: `price = line.list_base_price + list_price * price_dict[line.variable_factor]`
- Raises `UserError` if no rule matches ("Not available for current order")

**`_get_price_dict(total, weight, volume, quantity, wv)`** — Hook method. Override to add custom fields to price rule evaluation context.

**`_compute_currency(order, price, conversion)`** — Converts price between company and pricelist currencies. `'company_to_pricelist'` or `'pricelist_to_company'`.

**`_apply_margins(price)`** — Applies `margin` and `fixed_margin`. Uses `order` context for currency conversion. Fixed price type uses raw price.

**`_match(partner, order)`** — Combines all matching checks: address, must-have tags, excluded tags, weight, volume. All must pass.

**`_match_address(partner)`** — Checks `country_ids`, `state_ids`, `zip_prefix_ids` (regex against `partner.zip.upper()`).

**`_match_must_have_tags(order)`** — Returns `True` if at least one order line product has at least one must-have tag.

**`_match_excluded_tags(order)`** — Returns `False` if any order line product has any excluded tag.

**`_match_weight(order)`** — `sum(product.weight * qty) <= max_weight` or no limit.

**`_match_volume(order)`** — `sum(product.volume * qty) <= max_volume` or no limit.

**`toggle_prod_environment()`** — Toggle button action for `prod_environment`.

**`toggle_debug()`** — Toggle button action for `debug_logging`.

**`install_more_provider()`** — Opens the module manager with `delivery_%` filter (shows available carrier modules as installable apps).

**`_get_delivery_type()`** — Returns `delivery_type`. Can be overridden by carrier modules that compute the type dynamically.

---

### `delivery.price.rule`

Pricing rule for `base_on_rule` delivery type. Each carrier can have multiple rules evaluated in sequence.

**Inheritance:** `models.Model`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char (computed) | Auto-generated human-readable rule description |
| `sequence` | Integer | Evaluation order. Default `10` |
| `carrier_id` | Many2one `delivery.carrier` | Parent carrier. Required, ondelete cascade |
| `currency_id` | Many2one (related) | From `carrier_id.currency_id` |
| `variable` | Selection | Value to compare: `'weight'`, `'volume'`, `'wv'`, `'price'`, `'quantity'` |
| `operator` | Selection | Comparison: `'=='`, `'<='`, `'<'`, `'>='`, `'>'` |
| `max_value` | Float | Threshold value for comparison |
| `list_base_price` | Float | Fixed price component (base fee) |
| `list_price` | Float | Variable rate (multiplied by `variable_factor` value) |
| `variable_factor` | Selection | Which order metric to multiply the variable rate by |

**Computed `name` example:** `"if weight <= 5.00 then fixed price 10.00 plus 2.00 times weight"`

#### Pricing Formula

```
price = list_base_price + list_price * order[variable_factor]
```

Example: `list_base_price=10, list_price=2, variable='weight', variable_factor='weight', max_value=5, operator='<='`
-> Order weight 3kg: `price = 10 + 2 * 3 = 16`

---

### `delivery.zip.prefix`

Zip code prefix that a carrier delivers to. Used for address-based filtering.

**Inheritance:** `models.Model`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Prefix value. Stored uppercase. Supports regex via `$` suffix |

**Behavior:**
- `create()` and `write()` automatically convert `name` to uppercase
- `name` is unique (SQL constraint)
- `_match_address()` uses regex: `'^' + prefix` for each prefix, joined with `|`

**Example:** `'100$'` only matches zip code `'100'` exactly. `'100'` matches `'1000'`, `'1001'`, `'100XX'`.

---

### `sale.order` (Extended)

Added delivery method and shipping weight tracking.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `pickup_location_data` | Json | JSON data for selected pickup point (populated for carriers with `*_use_locations` attribute) |
| `carrier_id` | Many2one `delivery.carrier` | Selected delivery method on the SO |
| `delivery_message` | Char | Message from carrier (e.g., warning, free shipping notice). Readonly |
| `delivery_set` | Boolean (computed) | `True` if any order line has `is_delivery = True` |
| `recompute_delivery_price` | Boolean | Set to `True` when order lines change — triggers price recomputation |
| `is_all_service` | Boolean (computed) | `True` if all order lines are service type (no physical shipping) |
| `shipping_weight` | Float (computed) | Total estimated weight of physical products. Depends on `order_line.product_uom_qty` and `product_uom` |

#### Key Methods

**`_get_estimated_weight()`** — Sums `product_qty * product.weight` for all `consu` type order lines (excluding delivery lines, cancelled lines, display_type lines). This is the weight used in `rate_shipment()`.

**`_remove_delivery_line()`** — Deletes delivery order lines with `qty_invoiced == 0`. Raises `UserError` if any delivery line is partially/fully invoiced.

**`set_delivery_line(carrier, amount)`** — Removes existing delivery line, sets `carrier_id`, creates new SO line with `is_delivery = True`.

**`_prepare_delivery_line_vals(carrier, price_unit)`** — Builds the SO line create values. Applies fiscal position tax mapping, uses `carrier.product_id` as the product, sets `is_delivery = True`. Description uses `carrier.name` + `product.description_sale` with "Free Shipping" suffix if applicable.

**`_create_delivery_line(carrier, price_unit)`** — Creates the SO line via sudo.

**`_set_pickup_location(pickup_location_data)`** — Stores pickup location JSON. Calls `{delivery_type}_use_locations` attribute on carrier; if `True` and data provided, parses and stores.

**`_get_pickup_locations(zip_code, country, **kwargs)`** — Delegates to `_{delivery_type}_get_close_locations()` on the carrier. Returns `{'pickup_locations': [...]}` or `{'error': '...'}`.

**`_action_confirm()`** (override) — If `pickup_location_data` is set, creates a `res.partner` of type `'delivery'` at the pickup address and updates `partner_shipping_id`. Prevents address mismatch on shipment.

**`action_open_delivery_wizard()`** — Opens the `choose.delivery.carrier` wizard. Prefills carrier from `partner_shipping_id.property_delivery_carrier_id` or commercial partner's default carrier.

**`_compute_amount_total_without_delivery()`** — Returns `amount_total` minus all delivery line totals. Used for `free_over` threshold check.

**`_update_order_line_info()`** (override) — Calls `onchange_order_line()` after price update, which sets `recompute_delivery_price = True`.

**`onchange_order_line()`** — Onchange on `order_line`, `partner_id`, `partner_shipping_id`. Sets `recompute_delivery_price = True` if a delivery line exists.

**`_get_update_prices_lines()`** — Override. Excludes delivery lines from price list recomputation.

---

### `sale.order.line` (Extended)

Delivery line tracking and special behavior.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `is_delivery` | Boolean | `True` for delivery cost lines. Default `False` |
| `product_qty` | Float (computed) | UoM-converted quantity for delivery lines |
| `recompute_delivery_price` | Boolean (related) | From `order_id.recompute_delivery_price` |

#### Special Behavior

- `unlink()`: If `is_delivery`, clears `order_id.carrier_id` after unlink
- `_can_be_invoiced_alone()`: Delivery lines cannot be invoiced standalone
- `_is_not_sellable_line()`: Delivery lines are excluded from sellable line count
- `_check_line_unlink()` (override): Delivery lines CAN be deleted from confirmed orders (bypasses normal SO line deletion restrictions)
- `_compute_pricelist_item_id()`: Delivery lines always have no `pricelist_item_id`
- `_get_invalid_delivery_weight_lines()`: Returns lines with physical products (`type not in ('service', 'combo')`) and `product_qty > 0` but `weight == 0`

---

### `res.partner` (Extended)

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `property_delivery_carrier_id` | Many2one `delivery.carrier` | Company-dependent default delivery method for this partner's orders |

---

### `choose.delivery.carrier` (Wizard)

Transient model for the "Add a shipping method" / "Update shipping cost" wizard.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `order_id` | Many2one `sale.order` | Required. Ondelete cascade |
| `partner_id` | Many2one `res.partner` | Related to `order_id.partner_id` |
| `carrier_id` | Many2one `delivery.carrier` | Selected carrier |
| `delivery_type` | Selection (related) | From `carrier_id.delivery_type` |
| `delivery_price` | Float | Computed price (after tax, margins, free-over) |
| `display_price` | Float | Carrier's original price before free-over |
| `currency_id` | Many2one (related) | From `order_id.currency_id` |
| `company_id` | Many2one (related) | From `order_id.company_id` |
| `available_carrier_ids` | Many2many (computed) | All carriers matching the order's delivery address |
| `invoicing_message` | Text (computed) | Invoicing policy message |
| `delivery_message` | Text | Carrier feedback/warning message |
| `total_weight` | Float | Order weight, related to `order_id.shipping_weight` |
| `weight_uom_name` | Char | Unit of measure label |

#### Key Methods

**`_compute_available_carrier()`** — Searches all carriers for the company and filters via `available_carriers(partner_shipping_id, order)`.

**`_get_delivery_rate()`** — Calls `carrier_id.rate_shipment(order_id)` with `order_weight` context. Sets `display_price = carrier_price` (pre-free-over) and `delivery_price = price` (potentially $0 if free).

**`update_price()`** — Re-computes rate and reopens wizard.

**`button_confirm()`** — Calls `order_id.set_delivery_line(carrier_id, delivery_price)` and writes `recompute_delivery_price = False`, `delivery_message`.

---

### `product.category` (Extended)

#### Methods

**`_unlink_except_delivery_category()`** — `@api.ondelete(at_uninstall=False)`. Prevents deletion of the `product_category_deliveries` category (used by delivery carrier products). Raises `UserError`.

---

## Pricing Flow Diagram

```
SO Action: Add/Update Shipping Method
         |
         v
action_open_delivery_wizard()
         |
         v
choose.delivery.carrier (wizard opens)
         |
         v
_compute_available_carrier()
  → delivery.carrier.search(company)
  → .available_carriers(partner_shipping_id, order)
       → ._match(partner, order)
         /  |  |  |  \       (address, tags, weight, volume)
         v  v  v  v  v
    All checks must pass
         |
    user selects carrier
         |
         v
_onchange_carrier_id()
  → _get_delivery_rate()
      → carrier.rate_shipment(order)
            │
       +----+----+
       |         |
   fixed      base_on_rule
       |         |
       v         v
fixed_rate_    base_on_rule_rate_shipment()
shipment()            |
       |               v
       |      _get_price_available(order)
       |               | (sum weight, volume, qty, price)
       |               v
       |      _get_price_from_picking()
       |               | (evaluate price_rule_ids via safe_eval)
       |               v
       |         Rule Match?
       |           /     \
       |         Yes       No
       |          |         |
       |          v         v
       |    Apply formula  UserError
       |          |
       +----------+
                |
                v
         _apply_margins(price)
                |
                v
         free_over check?
         (if enabled & threshold met → price = 0)
                |
                v
    Returns {success, price, carrier_price,
             error_message, warning_message}
                |
                v
   display_price = carrier_price  (pre-free-over)
   delivery_price = price         (potentially $0)
                |
                v
button_confirm()
  → order.set_delivery_line(carrier, delivery_price)
       → _remove_delivery_line()
       → _create_delivery_line()
```

---

## L4: Adding a New Carrier

Carrier integration modules (e.g., `delivery_dhl`, `delivery_fedex`) follow this pattern:

```python
class DeliveryCarrierDHL(models.Model):
    _name = 'delivery.carrier'
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(selection_add=[('dhl', 'DHL')])

    def dhl_rate_shipment(self, order):
        # Call DHL API
        return {
            'success': True,
            'price': 25.50,
            'error_message': False,
            'warning_message': False,
        }

    def dhl_send_shipping(self, pickings):
        # Create shipment in DHL
        return [{'tracking_number': 'XYZ', 'exact_price': 25.50}]

    def dhl_get_tracking_link(self, picking):
        return 'https://www.dhl.com/track?tracking=' + picking.tracking_number

    def dhl_cancel_shipment(self, picking):
        pass

    @api.depends('delivery_type')
    def _compute_can_generate_return(self):
        for carrier in self:
            carrier.can_generate_return = carrier.delivery_type == 'dhl'
```

**Method naming convention:** `{delivery_type}_{method}` where method is one of:
- `rate_shipment` — get shipping rate (quoting)
- `send_shipping` — create actual shipment (booking)
- `get_tracking_link` — return tracking URL
- `cancel_shipment` — void shipment

---

## L4: `rate_shipment` vs `send_shipping`

| Method | When Called | Purpose | Called By |
|--------|-------------|---------|-----------|
| `rate_shipment()` | User selects carrier in wizard | Compute price to display and store on SO line | `choose.delivery.carrier` wizard |
| `send_shipping()` | Delivery order validated in stock | Create actual shipment with carrier, get tracking number | `stock_picking_delivery` module |

`rate_shipment` is for **quoting**. `send_shipping` is for **booking**.

---

## L4: Weight Context Precedence

Shipping weight is determined in this priority order:

1. **User-specified** weight in `choose.delivery.carrier` wizard — via `context['order_weight']`
2. **Saved** `order.shipping_weight` (previously computed from lines)
3. **Computed** sum of all order line weights as fallback

This allows the wizard to override weight when the customer provides an exact weight.

---

## L4: Pickup Location Flow

When a carrier supports `*_use_locations` (e.g., `bpost_use_locations`):

1. SO confirmed with carrier and pickup location data → `_action_confirm()` called
2. Creates a `res.partner` of type `'delivery'` at the pickup address
3. Updates `partner_shipping_id` to this new delivery contact
4. `pickup_location_data` JSON stored on SO for carrier reference
5. Carrier integration reads `pickup_location_data` when generating shipping labels

---

## L4: Delivery Line Lifecycle

1. **Creation:** When carrier is confirmed in wizard → `sale.order._create_delivery_line()` creates SO line with `is_delivery = True`, using `carrier.product_id` as the product
2. **Recomputation:** On order line changes → `recompute_delivery_price = True` → user opens wizard to update
3. **Deletion:** Via `_remove_delivery_line()` — only if `qty_invoiced == 0`. Raises `UserError` if already invoiced
4. **Special rules:** Delivery lines can be deleted from **confirmed** orders (normally SO lines cannot), and they have no `pricelist_item_id` (not affected by pricelist updates)

---

## Related Documentation

- [Modules/Sale](Modules/Sale.md) — Sale order being extended
- [Modules/Stock](Modules/Stock.md) — Stock picking (extended by `stock_picking_delivery`)
- [New Features/New Modules](New-Features/New-Modules.md) — `delivery_dhl`, `delivery_fedex` carrier modules