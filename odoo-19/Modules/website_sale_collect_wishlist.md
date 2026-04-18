---
uuid: 4d5e6f7a-8b9c-0d1e-2f3a-b4c5d6e7f8a9
title: "Collect & Wishlist"
status: published
category: Website/Website
tags:
  - odoo
  - odoo19
  - website
  - wishlist
  - click_collect
  - ecommerce
created: 2024-01-15
modified: 2024-11-20
---

# Collect & Wishlist

## Overview

**Module:** `website_sale_collect_wishlist`
**Category:** Website/Website
**Version:** 1.0
**Depends:** `website_sale_wishlist`, `website_sale_collect`
**Summary:** Allows customers to add out-of-stock products to their wishlist when the selected pickup location does not carry the product
**Auto-install:** `True`
**License:** LGPL-3
**Author:** Odoo S.A.

`website_sale_collect_wishlist` is a thin bridge module that connects two eCommerce features — [Modules/website_sale_wishlist](Modules/website_sale_wishlist.md) (wishlist/saved products) and [Modules/website_sale_collect](Modules/website_sale_collect.md) (Click & Collect with in-store stock checking). It ensures that when a product is unavailable at the customer's selected pickup location, the wishlist functionality remains accessible on the pickup selection page. This prevents the loss of a potential sale when the customer's preferred store does not stock the product.

## Architecture

### Dependency Chain

```
website_sale_collect_wishlist
    ├── website_sale_wishlist     (wishlist feature, o_add_wishlist interaction)
    │       └── product.product._is_in_wishlist()
    └── website_sale_collect       (Click & Collect, in-store stock checking)
            └── website_sale_collect.unavailable_products_warning
                    (shows when a product is unavailable at the selected store)
```

### Component Map

```
website_sale_collect
    └── unavailable_products_warning (template)
            └── [INHERITED by website_sale_collect_wishlist]
                    └── Adds wishlist "Add to Wishlist" link when unavailable

No new Python models
No new controller methods
No new access rights
```

### Key Design Decisions

- **Thin bridge, no models:** The module defines no Python models or controllers. It exists solely to modify the presentation layer (QWeb templates) of `website_sale_collect` to expose wishlist functionality when a product is unavailable.
- **Widget-based interaction:** The wishlist add action uses the `o_add_wishlist_dyn` widget from `website_sale_wishlist`, which handles the AJAX call to add the product to the wishlist and provides user feedback (heart icon animation, toast notification).
- **Template inheritance pattern:** The module uses standard QWeb template inheritance (`inherit_id`) to add content to an existing template without replacing it. This keeps the modification minimal and compatible with other modules that may also extend the same parent template.
- **Per-product check:** The `_is_in_wishlist()` method is called per product line to determine whether to show "Add to Wishlist" or "In wishlist" status. This ensures the UI always reflects the current wishlist state even if the user has added the product from another page or session.

## Template Extension

### `unavailable_products_warning` — Injecting Wishlist Access

**File:** `views/delivery_form_templates.xml`

```xml
<template
    id="unavailable_products_warning"
    inherit_id="website_sale_collect.unavailable_products_warning"
>
    <div name="o_wsale_unavailable_line_button_container" position="inside">
        <t t-if="not available_qty">
            <t t-set="in_wishlist" t-value="order_line.product_id._is_in_wishlist()"/>
            <a
                t-if="not in_wishlist"
                title="Add to Wishlist"
                href="#"
                class="o_add_wishlist_dyn alert-link border-start ps-2 small"
                t-att-data-product-template-id="order_line.product_id.product_tmpl_id.id"
                t-att-data-product-product-id="order_line.product_id.id"
                data-action="o_wishlist"
            >
                <span
                    class="js_wsc_update_product_qty"
                    t-att-data-line-id="order_line.id"
                    t-att-data-product-id="order_line.product_id.id"
                >
                    <i class="fa fa-fw fa-heart-o" role="presentation" aria-label="Add to Wishlist"/>
                    Wishlist
                </span>
            </a>
            <span t-else="" class="alert-link border-start ps-2 small">
                <i class="fa fa-fw fa-heart"/> In wishlist
            </span>
        </t>
    </div>
</template>
```

#### Inherited Template: `website_sale_collect.unavailable_products_warning`

This template is rendered in the Click & Collect pickup selection page when a product in the cart is not available at the selected store. It displays each unavailable product with a message and a quantity update field.

#### Injection Point

| Element | Attribute | Description |
|---|---|---|
| `<div name="o_wsale_unavailable_line_button_container">` | `position="inside"` | The button container inside each unavailable product line |

The extension inserts content inside the button container when `available_qty` is 0 (product not in stock at this store).

#### Conditions and UI States

| Condition | UI Rendered |
|---|---|
| `available_qty == 0` AND product not in wishlist | "Add to Wishlist" link with heart outline icon |
| `available_qty == 0` AND product already in wishlist | "In wishlist" label with filled heart icon |
| `available_qty > 0` | No change (original button container preserved) |

#### Wishlist Widget Configuration

The "Add to Wishlist" link uses the `o_add_wishlist_dyn` CSS class and `data-action="o_wishlist"` attribute, which are recognized by `website_sale_wishlist`'s JavaScript widget to trigger the wishlist AJAX call. The `data-product-template-id` and `data-product-product-id` attributes pass the product identifiers to the wishlist service.

| Attribute | Value | Purpose |
|---|---|---|
| `data-action` | `o_wishlist` | Tells the wishlist widget to add to wishlist |
| `data-product-template-id` | `order_line.product_id.product_tmpl_id.id` | Product template ID for wishlist |
| `data-product-product-id` | `order_line.product_id.id` | Product variant ID |
| `data-line-id` | `order_line.id` | Order line ID for quantity updates |
| `data-product-id` | `order_line.product_id.id` | Product ID for quantity updates |

#### UX Flow

```
[Customer selects pickup location on Click & Collect page]
    |
    v
[website_sale_collect checks stock at that location]
    |
    v
[Products out of stock at this location]
    --> Renders unavailable_products_warning template
    --> website_sale_collect_wishlist extension adds wishlist links
    |
    v
[Customer clicks "Add to Wishlist"]
    --> o_add_wishlist_dyn widget sends AJAX request
    --> Product added to wishlist (website_sale_wishlist)
    --> Link changes to "In wishlist" with filled heart
    |
    v
[Customer receives notification toast]
```

## Relationship to Parent Modules

### `website_sale_collect`

**File:** `views/delivery_form_templates.xml` (inherited template)

`website_sale_collect` renders the pickup selection form and checks product availability at the selected location. When stock is insufficient, it calls the `unavailable_products_warning` template. The `available_qty` variable is passed by the parent template's controller to indicate stock level at the chosen store.

The parent template structure (simplified):

```xml
<div t-foreach="unavailable_lines" t-as="order_line">
    <span class="text-danger">
        <t t-esc="order_line.product_id.display_name"/> -
        Not available at this store
    </span>
    <div name="o_wsale_unavailable_line_button_container">
        <!-- original: nothing / quantity update -->
    </div>
</div>
```

`website_sale_collect_wishlist` injects the wishlist link inside `o_wsale_unavailable_line_button_container`.

### `website_sale_wishlist`

**File:** `models/product_product.py` (or `product.template.py`)

The `website_sale_wishlist` module defines:

- `_is_in_wishlist()` method — checks whether the product is in the current visitor's wishlist
- `o_add_wishlist_dyn` JavaScript widget — handles the AJAX add-to-wishlist request
- Wishlist storage (using `wishlist` key on the visitor's session or partner)

`website_sale_collect_wishlist` does not override any of these; it simply calls them via the template.

## Data Flow

```
[Customer browses Click & Collect page]
    |
    v
[System checks product stock at selected store]
    |
    v
[Product stock == 0 at this store]
    |
    v
[website_sale_collect.unavailable_products_warning rendered]
    |
    v
[website_sale_collect_wishlist extension executes]
    |
    +-- t-if="not available_qty" --> TRUE (out of stock)
    |
    v
    t-set="in_wishlist" = order_line.product_id._is_wishlist()
    |
    v
    +-- in_wishlist == False
    |       --> Renders "Add to Wishlist" link
    |           data-action="o_wishlist"
    |           data-product-template-id="..."
    |           data-product-product-id="..."
    |
    +-- in_wishlist == True
            --> Renders "In wishlist" label
                (filled heart icon)
```

## No Python Models

This module has no Python model files. The `__init__.py` is empty. All functionality is implemented via QWeb template inheritance and leverages existing methods from `website_sale_wishlist`:

- `product.product._is_in_wishlist()` — checks wishlist membership
- `website_sale_wishlist` JavaScript `o_add_wishlist` widget — handles the AJAX add

## Related Modules

| Module | Role |
|---|---|
| [Modules/website_sale_wishlist](Modules/website_sale_wishlist.md) | Provides wishlist storage, `_is_in_wishlist()`, and the AJAX add widget |
| [Modules/website_sale_collect](Modules/website_sale_collect.md) | Provides Click & Collect stock checking, pickup location selection, and the `unavailable_products_warning` template |
| [Modules/website_sale](Modules/website_sale.md) | Base eCommerce; checkout flow and cart management |
| `stock` | Inventory management; provides `stock.quant` for stock level queries |

## Security Considerations

- No new access rights are introduced.
- The template only renders UI elements; all data access is controlled by the parent modules (`website_sale_wishlist`, `website_sale_collect`).
- The `_is_in_wishlist()` method respects the visitor's wishlist (session or partner-based), ensuring no cross-user data leakage.

## Performance Notes

- The template calls `_is_in_wishlist()` per unavailable order line. This is a single database read per product per render. For carts with many unavailable products, this could be optimized by batch-fetching wishlist status, but for typical use cases (a few unavailable items), the overhead is negligible.
- No new database tables or records are created by this module.
- The module's only operation is a QWeb template extension, which is resolved at render time with no database cost.

## Extension Points

Because this module relies entirely on template inheritance, it can be further extended by other modules:

- A module that adds "Notify me when available" could extend the same container with an email notification signup.
- A module that adds "Find another store" functionality could add a button to switch pickup location.
- Both extensions would coexist cleanly since they add different content inside the same container.

## Migration Notes

- No Python code changes are needed when migrating; simply ensure the template inheritance is preserved.
- The `o_add_wishlist_dyn` widget class and `data-action="o_wishlist"` attribute must remain unchanged for the wishlist AJAX to work.
- If the parent template `website_sale_collect.unavailable_products_warning` is restructured in a future version, the inheritance `position="inside"` target (`name="o_wsale_unavailable_line_button_container"`) may need to be updated.

## See Also

- [Modules/website_sale_wishlist](Modules/website_sale_wishlist.md)
- [Modules/website_sale_collect](Modules/website_sale_collect.md)
- [Modules/website_sale](Modules/website_sale.md)
