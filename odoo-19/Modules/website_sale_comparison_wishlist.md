---
title: Website Sale Comparison Wishlist
description: Bridge module combining website sale comparison and wishlist functionality. Adds a product comparison action to wishlist items for seamless product research workflows.
tags: [odoo19, website, e-commerce, comparison, wishlist, module]
model_count: 0
models: []
dependencies:
  - website_sale_comparison
  - website_sale_wishlist
category: Website/Website
source: odoo/addons/website_sale_comparison_wishlist/
created: 2026-04-14
uuid: c3d4e5f6-a7b8-9012-cdef-123456789012
---

# Website Sale Comparison Wishlist

## Overview

**Module:** `website_sale_comparison_wishlist`
**Category:** Website/Website
**Depends:** `website_sale_comparison`, `website_sale_wishlist`
**Auto-install:** True
**License:** LGPL-3
**Author:** Odoo S.A.
**Module directory:** `odoo/addons/website_sale_comparison_wishlist/`

`website_sale_comparison_wishlist` is a frontend bridge module that seamlessly integrates two website sale features -- product comparison and wishlists -- into a unified user experience. It adds an "Add to Compare" button directly onto wishlist items, so customers can research and compare products without leaving their wishlist page.

This is one of the thinnest possible bridge modules: it contains zero Python models, zero server-side controllers, and zero business logic. Its entire function is to modify the QWeb template rendered by the wishlist page and to patch a JavaScript interaction component. The module is purely a UX enhancement that makes the existing comparison infrastructure accessible from the wishlist.

## Module Structure

```
website_sale_comparison_wishlist/
├── __init__.py
├── __manifest__.py
├── views/
│   └── templates.xml         # QWeb template: injects compare button into wishlist
└── static/
    └── src/
        └── interactions/
            └── product_comparison.js   # JS patch: handles add-to-compare from wishlist
```

The module has no `data/` files beyond `views/templates.xml`, no wizard models, no ORM overrides, and no Python business logic. It is 100% frontend.

## Dependency Chain

```
website_sale_comparison_wishlist
├── website_sale_comparison    # Product comparison: comparison table, attribute columns
│   ├── website_sale           # E-commerce: product pages, cart, checkout
│   │   └── sale              # Sales: orders, pricing, product configuration
│   └── product                # Product master: variants, attributes, variants
└── website_sale_wishlist     # Wishlist: save products for later
    ├── website_sale           # (shared dependency)
    └── product                # (shared dependency)
```

Both `website_sale_comparison` and `website_sale_wishlist` depend on `website_sale`, so installing this bridge module brings in the entire e-commerce stack. The `auto_install=True` declaration ensures that if a user installs either parent module without this bridge, Odoo will auto-install the bridge.

## Design Philosophy

This module exemplifies the "bridge pattern" in Odoo website development: instead of duplicating code from the comparison and wishlist modules, it composes their outputs using XML template inheritance and JavaScript interaction patching.

**What it does NOT do:**
- It does not define any new models.
- It does not create new database tables.
- It does not add server-side business logic.
- It does not modify product data or wishlist storage.

**What it does:**
- It modifies the wishlist QWeb template to include an "Add to Compare" button.
- It patches the JavaScript product comparison component to handle clicks from the wishlist context.
- It ensures visual alignment in the wishlist grid even when a product cannot be compared (placeholder shown).

## Template Injection

**File:** `views/templates.xml`

```xml
<template id="product_wishlist" inherit_id="website_sale_wishlist.product_wishlist">
    <xpath expr="//div[hasclass('o_wsale_product_action_row')]" position="inside">
        <t t-if="is_view_active('website_sale_comparison.add_to_compare')">
            <t t-set="categories"
               t-value="wish.product_id.product_tmpl_id.valid_product_template_attribute_line_ids._prepare_categories_for_display()"/>
            <t t-set="product_variant_id"
               t-value="wish.product_id.product_tmpl_id._get_first_possible_variant_id()"/>

            <button
                t-if="product_variant_id and categories"
                type="button"
                class="btn btn-light o_add_to_compare d-inline-flex"
                t-att-data-product-id="wish.product_id.id"
                aria-label="Add to compare"
            >
                <i class="fa fa-fw fa-exchange" role="presentation"/>
            </button>

            <!-- Render placeholder when product is not comparable to ensure alignment -->
            <div t-else="" class="o_add_to_compare_placeholder btn btn-light pe-none opacity-0">
                <i class="fa fa-exchange fa-fw" aria-hidden="true"/>
            </div>
        </t>
    </xpath>
</template>
```

### Template Injection Analysis

| Element | Detail |
|---------|--------|
| Target template | `website_sale_wishlist.product_wishlist` -- the wishlist page |
| Injection point | Inside `<div class="o_wsale_product_action_row">` -- the action button row |
| Condition | `is_view_active('website_sale_comparison.add_to_compare')` -- comparison feature must be enabled |
| Product resolution | `wish.product_id.product_tmpl_id._get_first_possible_variant_id()` -- gets first sellable variant |
| Attribute check | `valid_product_template_attribute_line_ids` -- ensures product has comparison attributes |
| Accessibility | `aria-label="Add to compare"` for screen readers |

### Why Two Buttons?

The template injects one of two elements:
1. **Compare button** (`<button class="o_add_to_compare">`): When the product has variants and attributes, the real compare button is shown. Clicking it adds the product to the comparison list.
2. **Placeholder** (`<div class="o_add_to_compare_placeholder">`): When the product has no comparable attributes, a disabled, invisible placeholder is rendered to maintain grid alignment. Without this, wishlist items with and without comparison would have different button rows, causing layout misalignment.

### The `is_view_active()` Check

```xml
<t t-if="is_view_active('website_sale_comparison.add_to_compare')">
```

This t-if checks whether the comparison feature is active on the website. The comparison feature is a website-specific toggle (in website settings, the "Product Comparison" feature can be enabled or disabled per website). This check ensures the compare button only appears when the comparison feature is turned on.

### Product Variant Resolution

```python
wish.product_id.product_tmpl_id._get_first_possible_variant_id()
```

This is important for configurable products. A product template might have many variants (size/color combinations), but the wishlist stores a specific `product.product` record. The comparison module works at the template level (product_tmpl_id), so the wishlist needs to resolve the first possible variant ID for the comparison to work.

## JavaScript Interaction Patching

**File:** `static/src/interactions/product_comparison.js`

```javascript
import { patch } from '@web/core/utils/patch';
import { patchDynamicContent } from '@web/public/utils';
import { ProductComparison } from '@website_sale_comparison/interactions/product_comparison';
import comparisonUtils from '@website_sale_comparison/js/website_sale_comparison_utils';

patch(ProductComparison.prototype, {
    setup() {
        super.setup();
        patchDynamicContent(this.dynamicContent, {
            '.wishlist-section .o_add_to_compare': {
                't-on-click': this.addProductFromWishlist.bind(this),
            },
        });
    },

    addProductFromWishlist(ev) {
        if (this._checkMaxComparisonProducts()) return;

        const el = ev.currentTarget;
        const productId = parseInt(el.dataset.productId);
        if (!productId || this._checkProductAlreadyInComparison(productId)) {
            comparisonUtils.updateDisabled(el, true);
            return;
        }

        comparisonUtils.addComparisonProduct(productId, this.bus);
        comparisonUtils.updateDisabled(el, true);
    },
});
```

### JavaScript Architecture

The module patches the `ProductComparison` class from `website_sale_comparison` rather than creating a new class. This is a clean extension pattern:

1. **Imports:** The module imports `ProductComparison` from the parent comparison module.
2. **Patches the prototype:** `patch(ProductComparison.prototype, {...})` adds new methods to the existing class.
3. **Patches dynamic content:** `patchDynamicContent()` adds a click handler to wishlist elements matching `.wishlist-section .o_add_to_compare`.
4. **Binds context:** `this.addProductFromWishlist` is bound to the prototype so `this` refers to the `ProductComparison` instance.

### The `addProductFromWishlist()` Method

```
addProductFromWishlist(event)
  │
  ├─ Check: _checkMaxComparisonProducts()
  │     └─ If max reached: return (no action)
  │
  ├─ Get: productId from el.dataset.productId
  │
  ├─ Check: _checkProductAlreadyInComparison(productId)
  │     └─ If already in comparison:
  │           └─ updateDisabled(el, true) → disable button
  │           └─ return
  │
  ├─ Add: comparisonUtils.addComparisonProduct(productId, this.bus)
  │     └─ Adds product to comparison list, notifies other components
  │
  └─ Disable: comparisonUtils.updateDisabled(el, true)
        └─ Visually marks button as added
```

### Comparison Utilities

The `comparisonUtils` module (from `website_sale_comparison/js/website_sale_comparison_utils`) provides:
- `addComparisonProduct(productId, bus)`: Adds a product to the comparison session and broadcasts via the event bus.
- `updateDisabled(el, disabled)`: Updates the button's disabled state and visual appearance.
- `removeComparisonProduct(productId)`: Removes a product from comparison.
- `_checkMaxComparisonProducts()`: Enforces the maximum comparison list size (usually 4 or 5 products).
- `_checkProductAlreadyInComparison(productId)`: Checks if a product is already in the list.

## How the User Journey Works

```
1. Customer browses the e-commerce website
      ↓
2. Finds product A, adds to wishlist (via website_sale_wishlist)
      ↓
3. Finds product B, adds to wishlist
      ↓
4. Finds product C, adds to wishlist
      ↓
5. Customer opens "My Wishlist" page
      (page renders via website_sale_wishlist's product_wishlist template)
      ↓
6. website_sale_comparison_wishlist template injection:
      → Each wishlist item gets an "Add to Compare" button
      → Buttons are hidden if comparison feature is disabled
      → Placeholders fill empty slots for alignment
      ↓
7. Customer clicks "Add to Compare" on products A and B
      ↓
8. JavaScript patch intercepts click:
      → Validates not at max capacity
      → Checks not already in comparison
      → Adds to comparison via comparisonUtils
      → Disables button (prevents duplicate)
      ↓
9. Customer navigates to Comparison page
      (via website_sale_comparison's comparison table)
      → Comparison table shows products A and B side by side
      → Attribute rows show specifications for each product
      ↓
10. Customer reviews and decides → buys product B
```

## The Comparison Table (from website_sale_comparison)

To fully understand the bridge, it helps to know how `website_sale_comparison` works:

**Product Comparison Table structure:**
- **Rows:** Product attributes (screen size, RAM, color, weight, etc.) from `product.template.attribute.line`.
- **Columns:** Products added to the comparison list (up to the configured maximum, usually 4).
- **Cells:** Attribute values for each product.

The comparison list is stored in the website visitor's session (`website.visitor` model) as ` comparison_product_ids` (Many2many to `product.product`). When a product is added via the JS component, it is written to this session record.

**How the bridge feeds into this:**
1. The wishlist stores `product.product` records in the visitor's session.
2. The bridge adds a button to each wishlist item.
3. Clicking the button calls `comparisonUtils.addComparisonProduct(productId)`.
4. `comparisonUtils` writes to `visitor.comparison_product_ids`.
5. The comparison page reads this field and renders the table.

## Asset Loading

**File:** `__manifest__.py`

```python
'assets': {
    'web.assets_frontend': [
        'website_sale_comparison_wishlist/static/src/**/*',
    ],
},
```

The module's JavaScript is loaded as part of `web.assets_frontend`, which is the frontend web assets bundle. This means:
- The JS is loaded on all frontend pages (not just the wishlist page).
- It only has an effect when the `.wishlist-section .o_add_to_compare` element exists in the DOM.
- The `patch()` call on `ProductComparison.prototype` only takes effect when the comparison interaction is initialized.

## Visibility Conditions

| Condition | Result |
|-----------|--------|
| Comparison feature disabled (`is_view_active` returns False) | No button or placeholder rendered |
| Product has no attributes (`categories` is empty) | Placeholder rendered (invisible, for alignment) |
| Product has no sellable variant (`product_variant_id` is falsy) | Placeholder rendered |
| Product has attributes and variant | Compare button rendered |
| Product already in comparison | Button disabled (via `updateDisabled`) |
| Max comparison reached | Button does nothing (returns early) |

## Extension Points

| Extension | How |
|-----------|-----|
| Change button style | Edit the `class` attribute on the `<button>` element in templates.xml |
| Add different icon | Change `<i class="fa fa-fw fa-exchange">` to any FontAwesome icon |
| Require minimum wishlist items before comparing | Add JS check in `addProductFromWishlist()` |
| Add "Remove from comparison" toggle | Add JS handler for a toggle state |
| Custom comparison max size | Change the check in `_checkMaxComparisonProducts()` |
| Show comparison preview on hover | Add CSS/JS hover behavior to the button |

## Why Both a Template and a JS Patch?

This is a common pattern in Odoo's website development:

- **Template (XML):** Adds the visual button element to the DOM. Without this, there would be no button to click.
- **JavaScript (JS):** Handles the interaction when the button is clicked. The comparison infrastructure is written in JavaScript (not server-side), so the click must be handled client-side.

The template creates the element; the JS makes it interactive. Neither works without the other.

## Related

- [Modules/website_sale_comparison](website_sale_comparison.md) -- Product comparison: comparison table, attribute rows, max products
- [Modules/website_sale_wishlist](website_sale_wishlist.md) -- Wishlist: save products for later, share wishlist
- [Modules/website_sale](website_sale.md) -- E-commerce core: product pages, cart, checkout
- [Modules/sale](sale.md) -- Sales order management
- [Modules/product](product.md) -- Product master: templates, variants, attributes
