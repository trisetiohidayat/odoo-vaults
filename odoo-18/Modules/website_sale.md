# Website Sale Module (website_sale)

## Overview

The `website_sale` module provides eCommerce functionality for the Odoo website. It integrates the cart system, product display, checkout flow, and payment processing with the website framework.

## Key Models

### sale.order (website_sale Extension)

Extends the standard `sale.order` with website-specific functionality.

**Additional Fields:**
- `website_id`: Many2one - Website this order was placed through
- `cart_recovery_email_sent`: Boolean - Whether cart recovery email has been sent
- `shop_warning`: Char - Warning message for cart display
- `website_order_line`: One2many - Lines filtered for website display (computed)
- `amount_delivery`: Monetary - Delivery cost (tax-aware computed field)
- `cart_quantity`: Integer - Total quantity in cart (computed)
- `only_services`: Boolean - Whether order contains only services (computed)
- `is_abandoned_cart`: Boolean - Whether this draft order is an abandoned cart (computed)

**Key Computed Methods:**
- `_compute_abandoned_cart()`: Marks orders as abandoned based on website delay setting and inactivity
- `_compute_cart_info()`: Computes `cart_quantity` and `only_services`
- `_compute_amount_delivery()`: Computes delivery amount respecting tax display setting

**Key Methods:**

- `_cart_update(product_id, line_id, add_qty, set_qty, **kwargs)`:
  - Core cart update logic
  - Handles quantity verification via `_verify_updated_quantity()`
  - Creates/updates/deletes order lines
  - Manages delivery method recalculation
  - Returns dict with `line_id`, `quantity`, `option_ids`, `warning`
  - Raises `UserError` if order is not in draft state
  - Prevents adding products with zero price when `prevent_zero_price_sale` is enabled

- `_cart_find_product_line(product_id, line_id, **kwargs)`:
  - Finds matching cart line considering attributes, no_variant values, combo items
  - Used by cart update to avoid duplicates

- `_prepare_order_line_values(product_id, quantity, **kwargs)`:
  - Prepares values for creating new order line
  - Handles variant creation for dynamic attributes
  - Includes custom attribute values and combo item tracking

- `_cart_recovery_email_send()`:
  - Sends cart recovery emails to abandoned cart holders
  - Uses website-specific or default template
  - Marks `cart_recovery_email_sent = True`

- `_filter_can_send_abandoned_cart_mail()`:
  - Filters abandoned carts eligible for recovery email
  - Checks: partner has email, no payment errors, has paid products, no subsequent orders

- `_has_deliverable_products()`: Returns True if order has products needing delivery

- `_get_delivery_methods()`: Returns available delivery carriers for the order

- `_set_delivery_method(carrier, rate)`: Sets delivery method and creates delivery line

- `_update_address(partner_id, fnames)`: Updates address and recomputes fiscal position/pricelist

**Cart Recovery Workflow:**
1. Scheduled action `_send_abandoned_cart_email()` runs periodically
2. Finds all abandoned carts (draft orders older than `cart_abandoned_delay`)
3. Filters using `_filter_can_send_abandoned_cart_mail()`
4. Sends email using template from `website.cart_recovery_mail_template_id`
5. Marks `cart_recovery_email_sent = True`

**State Machine:**
- Cart (draft order) is created on first product add via `sale_get_order(force_create=True)`
- Cart persists in session via `sale_order_id` session key
- Payment flow: Cart -> Checkout -> Payment -> Sale Order confirmation

### website.sale.extra.field

Extra fields displayed in the checkout process.

**Fields:**
- `website_id`: Many2one - Website
- `name`: Char - Field name
- `field_name`: Char - Technical field name
- `position`: Selection - Where to display (before or after checkout fields)

### website (website_sale Extension)

Extends `website` model with eCommerce fields and methods.

**Additional Fields:**
- `enabled_portal_reorder_button`: Boolean - Enable reordering from portal
- `salesperson_id`: Many2one - Default salesperson
- `salesteam_id`: Many2one - Default sales team
- `show_line_subtotals_tax_selection`: Selection - Tax display (tax_excluded/tax_included)
- `add_to_cart_action`: Selection - Behavior after adding to cart
- `account_on_checkout`: Selection - Customer account requirements (optional/disabled/mandatory)
- `cart_recovery_mail_template_id`: Many2one - Template for abandoned cart emails
- `cart_abandoned_delay`: Float - Hours before cart is considered abandoned
- `send_abandoned_cart_email`: Boolean - Enable cart recovery emails
- `shop_ppg`, `shop_ppr`: Integer - Products per grid/page, columns per row
- `shop_default_sort`: Selection - Default product sort order
- `product_page_image_layout`, `product_page_image_width`, `product_page_image_spacing`: Product page layout options
- `prevent_zero_price_sale`: Boolean - Hide Add to Cart for zero-price products
- `prevent_zero_price_sale_text`: Char - Text to display instead of price

**Key Methods:**
- `get_pricelist_available(show_visible)`: Returns available pricelists considering GeoIP
- `_get_pl_partner_order()`: Cached method for pricelist computation
- `_get_current_pricelist()`: Determines current pricelist with GeoIP and session support
- `sale_product_domain()`: Domain for website-available products
- `sale_get_order(force_create)`: Gets or creates current cart
- `_prepare_sale_order_values(partner)`: Prepares SO creation values
- `_get_current_fiscal_position()`: Computes fiscal position with GeoIP support
- `_send_abandoned_cart_email()`: Scheduled action for cart recovery
- `_get_checkout_step_list()`: Returns checkout flow steps

## Product Display Models

### product.template (website_sale Extension)

**Additional Fields:**
- `website_description`: Html - eCommerce-specific description
- `alternative_product_ids`: Many2many - Alternative products shown on product page
- `accessory_product_ids`: Many2many - Accessory products shown in cart
- `website_size_x`, `website_size_y`: Integer - Grid size in shop
- `website_ribbon_id`: Many2one - Ribbon display
- `website_sequence`: Integer - Sort order on website
- `public_categ_ids`: Many2many - Product categories for shop filtering
- `product_template_image_ids`: One2many - Extra images
- `compare_list_price`: Monetary - Strikethrough price for comparison
- `base_unit_count`, `base_unit_id`, `base_unit_price`, `base_unit_name`: Unit of measure display

**Key Methods:**
- `_get_combination_info(product_id, add_qty, parent_combination)`:
  - Returns complete product combination information
  - Includes: `product_id`, `price`, `list_price`, `price_extra`, `has_discounted_price`
  - Handles variant creation, price computation, tax application
  - Returns `is_combination_possible` and `parent_exclusions`

- `_get_additionnal_combination_info(product_or_template, quantity, date, website)`:
  - Computes additional info: base_unit_price, prevent_zero_price_sale flags
  - Applies fiscal position taxes
  - Returns price with/without taxes based on `show_line_subtotals_tax_selection`

- `_apply_taxes_to_price(price, currency, product_taxes, taxes, product_or_template, website)`:
  - Applies taxes respecting website tax display setting
  - Returns price in display currency

- `_search_get_detail(website, order, options)`: Website search integration
- `_get_google_analytics_data(product, combination_info)`: GA4 product data

**Edge Cases:**
- Dynamic variant creation on product page
- No_variant attribute handling (attributes not creating variants)
- Combo product pricing with tax disclaimers
- Zero-price product restrictions with `prevent_zero_price_sale`

### product.template.attribute.value (website_sale Extension)

**Key Methods:**
- `_get_extra_price(combination_info)`: Returns price extra for attribute value, with currency conversion and tax application

### product.combo

Represents a combo product (bundled products sold together).

**Fields:**
- `name`: Char - Combo name
- `product_tmpl_id`: Many2one - Parent product template
- `combo_item_ids`: One2many - Items in the combo
- `base_price`: Monetary - Base price (may be lower than sum of items)
- `max_quantity`: Integer - Maximum selectable quantity of combo

**Key Methods:**
- `_get_max_quantity(website)`: Returns max quantity based on item availability

### product.product (website_sale Extension)

**Key Methods:**
- `_website_show_quick_add()`: Checks if product can be added to cart (considers stock, pricing)

## Payment Integration

### payment.transaction (website_sale Extension)

**Additional Fields:**
- `sale_order_ids`: One2many - Sale orders related to this transaction
- `billing_address`: Many2one - Res.partner billing address for country restrictions

The module handles:
- Payment flow integration with checkout
- Billing address capture for payment providers
- Multi-SO payments (split across orders)

## Cart Session Management

**Session Keys Used:**
- `sale_order_id`: Current cart SO ID
- `website_sale_current_pl`: Current pricelist ID
- `website_sale_cart_quantity`: Cart quantity for quick access
- `website_sale_selected_pl_id`: User-selected pricelist ID

**Cart State Flow:**
1. `sale_get_order()` checks session for existing cart
2. Validates cart still usable (pricelist available, fiscal position unchanged)
3. Creates new cart if needed with website defaults
4. Session stores `sale_order_id` for persistence

## Checkout Flow

The checkout flow consists of steps defined by `_get_checkout_step_list()`:

1. **Review Order** (`/shop/cart`) - Review and modify cart
2. **Delivery** (`/shop/checkout`) - Enter shipping address and delivery method
3. **Extra Info** (optional, `/shop/extra_info`) - Additional checkout fields
4. **Payment** (`/shop/payment`) - Payment selection

Each step is defined with main/back button URLs for navigation.

## Cross-Module Relationships

- **website**: Base website framework
- **sale**: Sale order management
- **delivery**: Shipping method integration
- **payment**: Payment provider integration
- **website_sale_wishlist**: Wishlist functionality
- **website_sale_stock**: Inventory display on website
- **website_sale_comparison**: Product comparison feature

## Edge Cases

1. **Pricelist Country Restriction**: GeoIP-based pricelist filtering
2. **Fiscal Position Change**: Recomputes prices when fiscal position changes on address update
3. **Abandoned Cart Detection**: Based on time since last modification, not just creation
4. **Zero-Price Products**: Special handling via `prevent_zero_price_sale` and `_get_product_types_allow_zero_price()`
5. **Combo Products**: Tax disclaimer when combo contains mixed-include/exclude products
6. **Anonymous Carts**: Carts created by public user with partner set to website public user
7. **Multi-Currency**: Pricelist currency vs company currency conversion in `_get_pl_partner_order()`
