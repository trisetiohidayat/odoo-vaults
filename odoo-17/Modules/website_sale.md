---
tags: [odoo, odoo17, module, website_sale, e-commerce]
research_depth: deep
---

# Website Sale Module — Deep Reference

**Source:** `addons/website_sale/models/`
**Controllers:** `addons/website_sale/controllers/main.py`

## Overview

The `website_sale` module bridges the public website with the Odoo CRM/sale pipeline. It manages the complete e-commerce customer journey: product browsing, cart management, pricelist application, checkout, and payment. A `sale.order` is created in `draft` state when a customer first adds a product; it only confirms to `sale` after successful payment.

### Customer Journey

```
Customer visits website
    → /shop (product grid) via WebsiteSale.shop()
    → /shop/product/<slug> (product page) via WebsiteSale.product()
    → Add to cart → POST /shop/cart/update_json
        → website.sale_get_order(force_create=True)  [creates draft sale.order]
        → sale_order._cart_update(product_id, ...)   [creates/updates sale.order.line]
    → /shop/cart (review cart) via WebsiteSale.cart()
    → /shop/checkout (address + carrier) via WebsiteSale.checkout()
    → /shop/payment (payment providers)
    → Payment confirmed → _action_confirm() → sale.order state = 'sale'
    → Email confirmation sent
```

## Key Models

### `sale.order` (Extended by website_sale)

**File:** `sale_order.py`

#### Additional Fields Added by website_sale

| Field | Type | Description |
|-------|------|-------------|
| `website_order_line` | One2many (computed) | Order lines visible on website cart (`_show_in_cart()` filter) |
| `cart_quantity` | Integer (computed) | Sum of quantities from `website_order_line` |
| `only_services` | Boolean (computed) | True if all cart items are services |
| `is_abandoned_cart` | Boolean (computed, searchable) | True when cart is past `cart_abandoned_delay` with lines and non-public partner |
| `cart_recovery_email_sent` | Boolean | Prevents duplicate recovery emails |
| `website_id` | Many2one `website` | Which website generated this order (readonly) |
| `shop_warning` | Char | Warning message displayed on cart/checkout |
| `amount_delivery` | Monetary (computed) | Sum of delivery line totals (tax-included or excluded per website config) |
| `access_point_address` | Json | Pickup-point address for "delivery at store" carriers |

#### `_cart_update(product_id, line_id=None, add_qty=0, set_qty=0, **kwargs)`

The core cart management method. Called by both the `cart_update` and `cart_update_json` controller routes.

```python
def _cart_update(self, product_id, line_id=None, add_qty=0, set_qty=0, **kwargs):
    self.ensure_one()
    # Guard: only draft orders can be modified
    if self.state != 'draft':
        raise UserError(_('It is forbidden to modify a sales order which is not in draft status.'))

    product = self.env['product.product'].browse(product_id).exists()
    order_line = self._cart_find_product_line(product_id, line_id, **kwargs)[:1]

    # Compute final quantity: set_qty wins, else add_qty to existing line or use add_qty directly
    if set_qty:
        quantity = int(set_qty)
    elif order_line:
        quantity = order_line.product_uom_qty + (add_qty or 0)
    else:
        quantity = add_qty or 0

    if quantity > 0:
        quantity, warning = self._verify_updated_quantity(order_line, product_id, quantity, **kwargs)
    else:
        warning = ''

    self._remove_delivery_line()
    order_line = self._cart_update_order_line(product_id, quantity, order_line, **kwargs)

    return {
        'line_id': order_line.id,
        'quantity': quantity,
        'option_ids': list(...),
        'warning': warning,
    }
```

**Key behaviors:**
- If `set_qty=0` on an existing line, the line is unlinked (via `_cart_update_order_line`)
- If `quantity > 0`, `_verify_updated_quantity()` is called as a hook (overridden in `sale_product_matrix`)
- After every update, `_remove_delivery_line()` forces re-selection of carrier
- `_cart_find_product_line()` returns lines matching `product_id` and optionally `line_id`; for products with dynamic or no_variant attributes, it returns empty (product must be re-selected by combination)

#### `_cart_find_product_line(product_id, line_id=None, **kwargs)`

Finds an existing `sale.order.line` in the cart. If `line_id` is not given and the product has dynamic attributes or no_variant attributes, returns empty (prevents wrong line matching).

```python
def _cart_find_product_line(self, product_id, line_id=None, **kwargs):
    product = self.env['product.product'].browse(product_id)
    if not line_id and (
        product.product_tmpl_id.has_dynamic_attributes()
        or product.product_tmpl_id._has_no_variant_attributes()
    ):
        return SaleOrderLine  # empty — must use line_id for those products
    domain = [('order_id', '=', self.id), ('product_id', '=', product_id)]
    if line_id:
        domain += [('id', '=', line_id)]
    else:
        domain += [('product_custom_attribute_value_ids', '=', False)]
    return SaleOrderLine.search(domain)
```

#### `_prepare_order_line_values(product_id, quantity, ...)` → dict

Prepares dict values to `sale.order.line.create()`. Handles:
- Resolves the correct product variant via `_create_product_variant(combination)`
- Fills in `product_no_variant_attribute_value_ids` for `create_variant='no_variant'` attributes
- Fills in `product_custom_attribute_value_ids` for `is_custom=True` attribute values

#### Abandoned Cart Detection (`_compute_abandoned_cart`)

```python
def _compute_abandoned_cart(self):
    for order in self:
        if order.website_id and order.state == 'draft' and order.date_order:
            abandoned_delay = order.website_id.cart_abandoned_delay or 1.0
            abandoned_datetime = datetime.utcnow() - relativedelta(hours=abandoned_delay)
            order.is_abandoned_cart = bool(
                order.date_order <= abandoned_datetime
                and order.partner_id != order.website_id.user_id.partner_id
                and order.order_line
            )
```

The `_search_abandoned_cart` method generates a domain compatible with the searcher for reporting/filtering.

#### Cart Recovery (`_filter_can_send_abandoned_cart_mail`)

Before sending a recovery email, the system checks:
1. Partner has an email address
2. No transaction is in `error` state
3. At least one line has a non-zero price_unit (not all-free)
4. No confirmed `sale` order was created after the abandoned cart for the same partner

#### `_check_carrier_quotation(force_carrier_id=None, keep_carrier=False)`

Called before payment to validate/select a delivery carrier. Logic:
1. For service-only orders: skip (no shipping needed)
2. Prefer `partner_shipping_id.property_delivery_carrier_id`
3. Find all available carriers via `_get_delivery_methods()` and match by address
4. Write `carrier_id` and call `carrier.rate_shipment(self)` to set delivery line price

### `sale.order.line` (Extended by website_sale)

**File:** `sale_order_line.py`

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `linked_line_id` | Many2one `sale.order.line` | Parent line for optional products |
| `option_line_ids` | One2many `sale.order.line` | Lines linked as options to a parent |
| `name_short` | Char (computed) | Product display name without internal reference |
| `shop_warning` | Char | Per-line warning |

#### `_show_in_cart()`

Controls whether a line appears on the website cart. Excludes delivery lines and section/note lines:

```python
def _show_in_cart(self):
    return not self.is_delivery and not bool(self.display_type)
```

#### `_get_order_date()`

For website draft orders, uses `fields.Datetime.now()` instead of the order's `date_order`, so prices recompute correctly even if the cart was created earlier.

### `product.template` (Extended by website_sale)

**File:** `product_template.py`

Inherits from: `rating.mixin`, `product.template`, `website.seo.metadata`, `website.published.multi.mixin`, `website.searchable.mixin`

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `website_description` | Html | Full-description for website (overrides base `description`) |
| `description_ecommerce` | Html | Separate e-commerce description shown in shop |
| `alternative_product_ids` | Many2many `product.template` | Upsell: products shown on product page |
| `accessory_product_ids` | Many2many `product.product` | Cross-sell: suggested in cart review |
| `website_size_x`, `website_size_y` | Integer | Grid cell size for shop layout |
| `website_ribbon_id` | Many2one `product.ribbon` | Sale ribbon overlay |
| `website_sequence` | Integer | Sort order on shop page (default = max+5) |
| `public_categ_ids` | Many2many `product.public.category` | Shop categories |
| `product_template_image_ids` | One2many `product.image` | Extra gallery images |
| `compare_list_price` | Monetary | Strikethrough "was" price on shop page |
| `base_unit_count`, `base_unit_id`, `base_unit_price`, `base_unit_name` | Various | Price-per-unit display fields |

#### `_get_combination_info(combination=False, product_id=False, add_qty=1.0, ...)`

Returns a dict with all combination data needed by the product page JS:

```python
combination_info = {
    'product_id': product.id,
    'product_template_id': self.id,
    'display_name': display_name,
    'is_combination_possible': bool,
    'parent_exclusions': dict,
    'price': tax-applied pricelist price,
    'list_price': catalog price (tax-applied),
    'price_extra': attribute extra price,
    'has_discounted_price': bool,
    'compare_list_price': strike-through price or None,
    'prevent_zero_price_sale': bool,
    'base_unit_name', 'base_unit_price': per-unit pricing,
    'currency', 'date', 'product_taxes', 'taxes': context values,
}
```

This method gets the current website's pricelist, applies fiscal position taxes, and handles currency conversion.

#### `_get_sales_prices(pricelist, fiscal_position)`

Computes `price_reduce` and optional `base_price` for display in the shop grid. Handles `compare_list_price` as a strikethrough and the `without_discount` pricelist discount policy.

#### `_search_get_detail(website, order, options)`

Implements `website.searchable.mixin` for the global website search. Searches across `name`, `default_code`, `description_sale`, with optional price range, category, tag, and attribute filters.

### `product.pricelist` (Extended by website_sale)

**File:** `product_pricelist.py`

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `website_id` | Many2one `website` | Restricts this pricelist to a specific website |
| `code` | Char | Promotional code (e-commerce promo code), requires `base.group_user` |
| `selectable` | Boolean | Allow end-users to manually select this pricelist |

#### `_is_available_on_website(website)`

A pricelist is available if:
- It has no `website_id` and is `selectable`, OR
- It has no `website_id` and has a `code` (promotional), OR
- It has a `website_id` matching the current website
- AND `company_id` matches the website's company (or is empty)

#### `_is_available_in_country(country_code)`

Uses GeoIP country code to filter pricelists by country group membership.

#### `_get_website_pricelists_domain(website)`

Generates the domain used in `website.py` to search available pricelists:

```python
[
    ('active', '=', True),
    ('company_id', 'in', [False, website.company_id.id]),
    '|', ('website_id', '=', website.id),
    '&', ('website_id', '=', False),
    '|', ('selectable', '=', True), ('code', '!=', False),
]
```

### `website` (Extended by website_sale)

**File:** `website.py`

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `salesperson_id` | Many2one `res.users` | Default salesman for website orders |
| `salesteam_id` | Many2one `crm.team` | Default team, defaults to `salesteam_website_sales` |
| `pricelist_id` | Many2one `product.pricelist` (computed) | Current applicable pricelist |
| `currency_id` | Many2one `res.currency` (computed) | Pricelist currency or company currency |
| `pricelist_ids` | One2many `product.pricelist` (computed) | All available pricelists |
| `fiscal_position_id` | Many2one `account.fiscal.position` (computed) | GeoIP-based fiscal position |
| `show_line_subtotals_tax_selection` | Selection | `tax_excluded` or `tax_included` |
| `cart_recovery_mail_template_id` | Many2one `mail.template` | Template for abandoned cart emails |
| `cart_abandoned_delay` | Float | Hours before a cart is considered abandoned (default 10.0) |
| `send_abandoned_cart_email` | Boolean | Enable/disable automatic recovery emails |
| `shop_ppg`, `shop_ppr` | Integer | Products per page / columns per row |
| `shop_default_sort` | Selection | Default product sorting |
| `add_to_cart_action` | Selection | `stay` or `go_to_cart` after adding |
| `account_on_checkout` | Selection | `optional`, `disabled`, `mandatory` |
| `product_page_image_*` | Various | Product page image layout settings |
| `prevent_zero_price_sale` | Boolean | Hide add-to-cart when price is 0 |
| `prevent_zero_price_sale_text` | Char | Replacement text for zero-price add-to-cart |

#### `sale_get_order(force_create=False, update_pricelist=False)` → `sale.order`

Returns the current cart, creating one if needed:

1. First checks `request.session['sale_order_id']`
2. Falls back to `partner.last_website_so_id` for logged-in users
3. Validates the cart's pricelist is still available
4. If payment is already `pending/authorized/done`, returns empty (cannot modify)
5. On partner change: resets session pricelist, recomputes fiscal position
6. If `update_pricelist=True`: writes new pricelist and calls `_recompute_prices()`
7. If no cart and `force_create=True`: calls `_prepare_sale_order_values()` and creates the order

```python
def _prepare_sale_order_values(self, partner_sudo):
    return {
        'company_id': self.company_id.id,
        'fiscal_position_id': self.fiscal_position_id.id,
        'partner_id': partner_sudo.id,
        'partner_invoice_id': addr['invoice'],
        'partner_shipping_id': addr['delivery'],
        'pricelist_id': self.pricelist_id.id,
        'payment_term_id': self.sale_get_payment_term(partner_sudo),
        'team_id': self.salesteam_id.id or partner_sudo.parent_id.team_id.id or partner_sudo.team_id.id,
        'user_id': salesperson_user_sudo.id,
        'website_id': self.id,
    }
```

#### `_get_current_pricelist()` → `product.pricelist`

Pricelist resolution order:
1. Session `website_sale_current_pl` (explicitly chosen or promo code applied)
2. `partner.last_website_so_id.pricelist_id` (cart's existing pricelist)
3. `partner.property_product_pricelist` (partner's assigned pricelist)
4. First available pricelist from `get_pricelist_available()`

Session is invalidated if the stored pricelist is no longer available for the GeoIP country.

#### `get_pricelist_available(show_visible=False)` → `product.pricelist` recordset

Uses the `ormcache`-decorated `_get_pl_partner_order()` to return available pricelists:
- If GeoIP country code is available, finds pricelists linked to that country group
- Falls back to all website-compliant pricelists
- For logged-in users, adds their personal `property_product_pricelist`
- `show_visible=True` filters out non-selectable and non-code pricelists

#### `_send_abandoned_cart_email()`

Scheduled action (via `@api.autovacuum`) that:
1. Finds all `sale.order` with `is_abandoned_cart=True` and `cart_recovery_email_sent=False`
2. Filters via `_filter_can_send_abandoned_cart_mail()` (excludes orders with later confirmed orders, error transactions, or all-free items)
3. Sends `mail.template_sale_cart_recovery` to each partner

#### `_get_checkout_step_list()` → list

Returns the ordered checkout steps as `[xmlid, {metadata}]` pairs. Steps:
1. `website_sale.cart` — Review / Sign In
2. `website_sale.checkout` or `website_sale.address` — Shipping address
3. `website_sale.extra_info` — Optional extra info step (if active)
4. `website_sale.payment` — Payment

### `delivery.carrier` (Extended by website_sale)

**File:** `delivery_carrier.py`

```python
class DeliveryCarrier(models.Model):
    _inherit = ['delivery.carrier', 'website.published.multi.mixin']
    website_description = fields.Text(related='product_id.description_sale', ...)
```

Inherits `website.published.multi.mixin` so carriers can be published/unpublished per website.

### `res.partner` (Extended by website_sale)

**File:** `res_partner.py`

- `last_website_so_id` — Computed link to the partner's most recent open website cart
- Onchange warns if switching pricelist would orphan an open website cart
- `write()` triggers fiscal position recomputation on all open website orders when country, VAT, or zip changes

## Pricelist System

### GeoIP-based Pricelist Selection

The flow for an anonymous visitor:
1. `request.geoip.country_code` is read by `_get_geoip_country_code()` on `website`
2. `get_pricelist_available()` passes this to `_get_pl_partner_order()`
3. `_get_pl_partner_order()` queries `res.country.group` for pricelists linked to the country
4. If no match, falls back to the website's selectable generic pricelists

For logged-in users, the partner's `property_product_pricelist` is also added to the available set (if website-compliant).

### Promotional Code Flow

```
POST /shop/pricelist  (promo=CODE)
    → searches product.pricelist with code=CODE
    → validates website availability
    → sets request.session['website_sale_current_pl'] = pricelist.id
    → calls sale_order._cart_update_pricelist(pricelist_id=...)
    → redirects to /shop/cart
```

## Cart Recovery

### Abandoned Cart Detection

A cart is "abandoned" when:
- It has `website_id` set
- It is in `draft` state
- Its `date_order` is older than `website.cart_abandoned_delay` hours
- The partner is not the website's public user
- It has at least one order line

### Recovery Email Scheduling

The `_send_abandoned_cart_email` method is an `@api.autovacuum` model method — called automatically by the Odoo scheduler. The website config has `send_abandoned_cart_email` as a master switch.

## Product Page Layout

The `website` model stores layout preferences:
- `product_page_image_layout`: `carousel` (default) or `grid`
- `product_page_image_width`: `none`, `50_pc`, `66_pc`, `100_pc`
- `product_page_image_spacing`: `none`, `small`, `medium`, `big`
- `product_page_grid_columns`: 1, 2 (default), or 3

## See Also

- [[Modules/website]] — base website model
- [[Modules/sale]] — base `sale.order`
- [[Modules/sale_management]] — optional products, quotation templates
- [[Modules/payment]] — payment processing and transactions
- [[Modules/website_sale_loyalty]] — coupons, loyalty, and rewards
- [[Modules/website_sale_wishlist]] — wishlist/favorites
- [[Modules/website_sale_stock]] — inventory-aware website features
- [[Modules/delivery]] — delivery carrier and rate computation
- [[Modules/account]] — fiscal positions, invoicing
