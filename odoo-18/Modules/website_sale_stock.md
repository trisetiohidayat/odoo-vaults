# Website Sale Stock Module (website_sale_stock)

## Overview

The `website_sale_stock` module integrates stock and inventory visibility into the eCommerce storefront. It displays real-time stock levels, handles stock notifications, and controls product availability on the website based on actual inventory.

## Key Models

### product.template (website_sale_stock Extension)

Extends `product.template` from `website_sale_stock` with inventory-related fields and availability logic.

**Additional Fields:**
- `allow_out_of_stock_order`: Boolean - Allow ordering products even when out of stock (default: True)
- `available_threshold`: Float - Quantity threshold below which availability is shown (default: 5.0)
- `show_availability`: Boolean - Display the available quantity on the product page (default: False)
- `out_of_stock_message`: Html - Custom message shown when product is out of stock

**Key Methods:**

- `_is_sold_out()`: Returns True if the product is a storable product and its variant is sold out (via `product_variant_id._is_sold_out()`)

- `_website_show_quick_add()`: Controls whether the quick-add (Add to Cart) button appears.
  ```python
  def _website_show_quick_add(self):
      return (self.allow_out_of_stock_order or not self._is_sold_out()) and super()._website_show_quick_add()
  ```
  - Shows Add to Cart if `allow_out_of_stock_order=True` OR product is NOT sold out
  - Otherwise hides the button

- `_get_additionnal_combination_info(product_or_template, quantity, date, website)`: Overrides `website_sale` to append stock-specific data to combination info returned to the frontend.
  - When called on a product variant (`is_product_variant=True`):
    - `free_qty`: Real-time available quantity via `website._get_product_available_qty(product)`
    - `cart_qty`: Quantity already in cart via `product._get_cart_qty(website)`
    - `uom_name`: Unit of measure name
    - `uom_rounding`: UoM rounding precision
    - `show_availability`: Whether to display availability info
    - `out_of_stock_message`: Custom out-of-stock message
    - `has_stock_notification`: Whether user has stock notification enabled
    - `stock_notification_email`: Email for stock notifications
  - For combo products: computes `max_combo_quantity` as the minimum of all combo max quantities (via `combo._get_max_quantity(website)`)
  - For non-variant templates: returns `free_qty=0`, `cart_qty=0`

- `_get_additional_configurator_data(product_or_template, date, currency, pricelist, **kwargs)`: Override of `website_sale` to append stock data to the product configurator data.
  - Returns `free_qty` when `max_quantity` is available from `_get_max_quantity()`

### website (website_sale_stock Extension)

Extends `website` model with stock-specific methods.

**Key Methods:**

- `_get_product_available_qty(product)`: Returns the free quantity available for a product variant.
  - Delegates to `product.with_context(warehouse=self._get_warehouse_available()).product_variant_id._get_available_quantity()`
  - Uses the website's available warehouse context

- `_get_warehouse_available()`: Returns the warehouse to use for stock availability checks.
  - Delegates to the `stock` module's `website_warehouse` or falls back to the company's default warehouse

- `_get_product_cart_qty(product)`: Returns the quantity of a product already in the current website cart.

### product.product (website_sale_stock Extension)

Extends `product.product` with stock notification capabilities.

**Key Methods:**

- `_has_stock_notification(partner)`: Checks whether a specific partner has stock notifications enabled for this product.
  - Looks for `stock.notify.email` records linked to the partner and product

- `_get_stock_notification_destinations()`: Returns notification destinations (email addresses) for stock alerts.
  - Used when stock replenishes for a product

## Stock Notification Workflow

1. **Enabling Notifications**: When a product is out of stock, the website displays an "Notify Me" button.
2. **Email Capture**: The customer enters their email address (stored in session as `stock_notification_email`).
3. **Product Tracking**: The product ID is added to `product_with_stock_notification_enabled` set in the session.
4. **Replenishment Alert**: When stock arrives (via `stock.move` or manual adjustment), the system can trigger notifications.
5. **Legacy Support**: Also checks `stock.notify.email` model for partner-linked notifications.

## Cross-Module Relationships

- **website_sale**: Base eCommerce framework; `website_sale_stock` extends product combination info with stock data
- **stock**: Inventory and warehouse management; provides `_get_available_quantity()`, warehouse context
- **product**: Product variants and stockable product types; `is_storable` check for sold-out detection

## Edge Cases

1. **Combo Product Availability**: Max combo quantity is constrained by the combo item with the lowest `max_quantity`, considering each item's individual stock availability.
2. **Warehouse Selection**: Stock availability is website-warehouse-aware; different websites may show different stock levels based on their assigned warehouse.
3. **Out-of-Stock with `allow_out_of_stock_order=True`**: Product remains purchasable but a warning/inventory message may be displayed.
4. **Cart Quantity vs Free Quantity**: A product's total `free_qty` is reduced by the quantity already in the customer's cart (`cart_qty`).
5. **Non-Variant Template Calls**: When `_get_additionnal_combination_info` is called on a template record (not a variant), `free_qty` and `cart_qty` are returned as 0 since no specific inventory applies.
6. **UoM Rounding**: Stock quantities respect the product's unit of measure rounding precision for display.
7. **Session-Based Notifications**: Anonymous users' stock notifications are stored in session (`product_with_stock_notification_enabled` set), while logged-in users use `stock.notify.email` records.
