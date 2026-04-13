# Events Booths Sales

## Overview
- **Name**: Events Booths Sales
- **Category**: Marketing/Events
- **Depends**: `event_booth`, `event_sale`
- **Summary**: Sell event booths and track payments via sale orders
- **Version**: 1.2
- **Auto-install**: True

## Models

### `event.booth.category` (extended)
- `product_id` (Many2one `product.product`, required) - Service product for this booth category (service_tracking = event_booth)
- `price`, `price_incl` (Float) - Booth rental price (excl/incl tax)
- `price_reduce`, `price_reduce_taxinc` (Float, computed) - Discounted prices
- `currency_id` (Many2one `res.currency`) - Currency for the price
- `image_1920` (Image) - Category image (falls back to product image)
- `_compute_price()` - Derives price from the linked product
- `_compute_price_incl()` - Computes tax-included price
- `_compute_price_reduce()` / `_compute_price_reduce_taxinc()` - With pricelist discounts
- `_check_service_tracking()` - Validates product has `service_tracking = event_booth`
- `_init_column()` - Initializes `product_id` for existing records on module install

### `event.type.booth` (extended)
- `product_id` (Many2one, related to `booth_category_id.product_id`)
- `price` (Float, related from category)
- `_get_event_booth_fields_whitelist()` - Adds `product_id`, `price`

### `event.booth` (extended)
- `event_booth_registration_ids` (One2many `event.booth.registration`) - Pending registrations
- `sale_order_line_registration_ids` (Many2many `sale.order.line`) - SO lines with booth reservations
- `sale_order_line_id` (Many2one `sale.order.line`) - Final confirmed SO line
- `sale_order_id` (Many2one `sale.order`) - Confirmed sale order
- `is_paid` (Boolean) - Payment status
- `action_set_paid()` - Marks booth as paid
- `action_view_sale_order()` - Opens the related SO
- `_get_booth_multiline_description()` - Multi-line name: event + booth names

### `event.booth.registration`
Temporary records linking SO lines to booths during the cart/quote process.

- `sale_order_line_id` (Many2one `sale.order.line`, required) - Parent SO line
- `event_booth_id` (Many2one `event.booth`, required) - Reserved booth
- `partner_id` (Many2one `res.partner`, related) - Order partner
- `contact_name`, `contact_email`, `contact_phone` (Char) - Contact info from partner
- `_unique_registration` - Constraint: one registration per SO line + booth combination
- `action_confirm()` - Confirms the booth and cancels conflicting registrations
- `_cancel_pending_registrations()` - Cancels SO for booths reserved by other registrations

### `sale.order.line` (extended)
- `event_booth_category_id` (Many2one `event.booth.category`) - Selected booth category
- `event_booth_pending_ids` (Many2many `event.booth`) - Booths pending confirmation
- `event_booth_registration_ids` (One2many) - Confirmed registrations
- `event_booth_ids` (One2many) - Confirmed booths
- `_compute_event_booth_pending_ids()` - Derives pending booths from registrations
- `_inverse_event_booth_pending_ids()` - Creates/deletes booth registrations on write
- `_check_event_booth_registration_ids()` - All booths must belong to the same event
- `_update_event_booths()` - Confirms booths and marks as paid
- `_get_sale_order_line_multiline_description_sale()` - Returns event + booth description

### `sale.order` (extended)
- `event_booth_ids` (One2many `event.booth`) - All confirmed booths
- `event_booth_count` (Integer) - Total booth count
- `action_confirm()` - Validates booth lines have booths selected; calls `_update_event_booths()`
- `action_view_booth_list()` - Opens booth list for this order

### `account.move` (extended)
- `_invoice_paid_hook()` - When invoice is paid, marks booths as paid via `_update_event_booths(set_paid=True)`

## Wizards

### `event.booth.configurator`
Allows selecting booth category and specific booths during SO line creation.

- `event_id` (Many2one `event.event`, required) - Target event
- `event_booth_category_available_ids` (Many2many) - Available categories
- `event_booth_category_id` (Many2one) - Selected category
- `event_booth_ids` (Many2many `event.booth`) - Selected booths
- `_check_if_no_booth_ids()` - Validates at least one booth is selected

## Related
- [Modules/event_booth](modules/event_booth.md) - Booth management base
- [Modules/event_sale](modules/event_sale.md) - Event ticket sales
- [Modules/Sale](modules/sale.md) - Sale orders
