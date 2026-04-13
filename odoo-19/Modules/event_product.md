# Events Product

## Overview
- **Name**: Events Product
- **Category**: Marketing/Events
- **Depends**: `event`, `product`, `account`
- **Summary**: Links products to event tickets and manages pricing/invoicing
- **Auto-install**: True

## Key Features
- Provides the **product linking layer** between `event` and `product` modules
- Adds `event` as a `service_tracking` option on product templates
- Creates a generic "Registration Product" template on install

## Extended Models

### `product.template`
- `service_tracking` - Added `event` option: "Event Registration"
- `_prepare_service_tracking_tooltip()` - Describes behavior for event tracking
- `_onchange_type_event()` - Sets `invoice_policy = 'order'` for event products
- `_service_tracking_blacklist()` - Excludes event products from certain service tracking contexts

### `product.product`
- `event_ticket_ids` (One2many `event.event.ticket`) - Tickets using this product
- `_check_event_ticket_service_tracking()` - Validates that products with tickets have `service_tracking = event`

## Related
- [Modules/event](modules/event.md) - Event management
- [Modules/event_sale](modules/event_sale.md) - Event ticket sales
- [Modules/Product](modules/product.md) - Product management
