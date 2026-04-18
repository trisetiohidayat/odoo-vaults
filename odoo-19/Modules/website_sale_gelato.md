---
uuid: 3c4d5e6f-7a8b-9c0d-1e2f-a3b4c5d6e7f8
title: "eCommerce/Gelato Bridge"
status: published
category: Website/Website
tags:
  - odoo
  - odoo19
  - website
  - sale
  - gelato
  - print
  - product
created: 2024-01-15
modified: 2024-11-20
---

# eCommerce/Gelato Bridge

## Overview

**Module:** `website_sale_gelato`
**Category:** Website/Website
**Version:** 1.0
**Depends:** `sale_gelato`, `website_sale`
**Summary:** Ensures Gelato print-on-demand products are correctly displayed and purchasable through the Odoo website
**Auto-install:** `True`
**License:** LGPL-3
**Author:** Odoo S.A.

`website_sale_gelato` bridges [Modules/sale_gelato](sale_gelato.md) (print-on-demand product management) and [Modules/website_sale](website_sale.md) (eCommerce). It adds website-specific constraints and actions to prevent publishing Gelato products without print images and to unpublish products when new print images are created from Gelato. It also prevents mixing Gelato and non-Gelato products in the same cart, which is critical because Gelato products require separate shipping.

## Architecture

### Dependency Chain

```
website_sale_gelato
    ├── sale_gelato         (Gelato print-on-demand core integration)
    │       └── sale.order (Gelato cart validation constraint)
    │       └── product.template (Gelato template sync, attribute creation)
    │       └── product.document (Gelato print image marking)
    └── website_sale        (eCommerce website display)
            └── sale.order (website cart quantity verification)
            └── product.template (publish state on website)
```

### Component Map

```
sale_gelato
    ├── product.document
    │       └── is_gelato (Boolean field)
    │       └── _check_product_is_unpublished_before_removing_print_images()
    │               [CONSTRAINT EXTENDED]
    │
    └── product.template
            └── gelato_template_ref (Boolean)
            └── gelato_missing_images (computed)
            └── _check_print_images_are_set_before_publishing()
            │       [CONSTRAINT ADDED]
            └── action_create_product_variants_from_gelato_template()
            │       [ACTION ADDED]
            └── _create_attributes_from_gelato_info()
                    [METHOD ADDED]

website_sale
    └── sale.order
            └── _verify_updated_quantity()
                    [OVERRIDE - prevents Gelato/non-Gelato cart mixing]
```

### Key Design Decisions

- **Print image requirement before publish:** A Gelato product cannot be published on the website unless it has at least one print image. This is enforced both as a constraint on `product.template` (from `sale_gelato`) and in the website context via `_check_print_images_are_set_before_publishing`.
- **Auto-unpublish on new print images:** When `action_create_product_variants_from_gelato_template()` detects that Gelato sync created new print images, it automatically sets `is_published = False`. This forces the store manager to review the new images before making the product live.
- **Separate shipping enforcement:** Gelato products require physical shipment of printed items, while regular products may use the same carrier. Mixing them in one cart would result in incorrect shipping rates. The `_verify_updated_quantity` override blocks this by returning quantity 0 with a user-friendly error message.
- **eCommerce description sync:** The module extracts the `description` field from Gelato's product template info and writes it to `product.template.description_ecommerce`, ensuring the website product page displays the description synced from Gelato.

## Extended Models

### `product.document` — Gelato Print Image Guard

**File:** `models/product_document.py`

```python
class ProductDocument(models.Model):
    _inherit = 'product.document'

    @api.constrains('datas')
    def _check_product_is_unpublished_before_removing_print_images(self):
        for print_image in self.filtered(lambda i: i.is_gelato):
            template = self.env['product.template'].browse(print_image.res_id)
            if template.is_published and not print_image.datas:
                raise ValidationError(
                    _("Products must be unpublished before print images can be removed.")
                )
```

| Constraint | Behavior |
|---|---|
| `_check_product_is_unpublished_before_removing_print_images` | If a Gelato print image (`is_gelato = True`) has its `datas` cleared (file removed) and the product is published, raise `ValidationError` |

**Purpose:** This prevents store managers from accidentally removing print images from a live Gelato product. If the product needs to be unpublished first, it forces a deliberate two-step process, reducing the risk of a broken product page.

**Note:** The constraint only applies to documents where `is_gelato = True` — standard product documents (datasheets, manuals) are unaffected.

#### `is_gelato` Field

This field is defined in `sale_gelato` on the `product.document` model. When Gelato syncs print images to Odoo, it marks them with `is_gelato = True`. This allows `website_sale_gelato` to target only Gelato-related documents with its constraints.

---

### `product.template` — Publishing and Sync Guards

**File:** `models/product_template.py`

```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'
```

#### `_check_print_images_are_set_before_publishing()`

```python
@api.constrains('is_published')
def _check_print_images_are_set_before_publishing(self):
    for product in self.filtered('gelato_template_ref'):
        if product.is_published and product.gelato_missing_images:
            raise ValidationError(
                _("Print images must be set on products before they can be published.")
            )
```

| Trigger | Condition | Error |
|---|---|---|
| `is_published` write | `gelato_template_ref` is set AND `gelato_missing_images` is True | "Print images must be set on products before they can be published." |

The `gelato_template_ref` is set when a product is linked to a Gelato product template. The `gelato_missing_images` computed field (from `sale_gelato`) is True when the product has no associated print images from Gelato.

**Use case:** A store manager attempts to publish a Gelato product that was just created but has not yet synced print images from Gelato. The constraint blocks the publish and displays a clear message.

#### `action_create_product_variants_from_gelato_template()`

```python
def action_create_product_variants_from_gelato_template(self):
    image_count_before_sync = len(self.gelato_image_ids)
    res = super().action_create_product_variants_from_gelato_template()
    if image_count_before_sync < len(self.gelato_image_ids):
        self.is_published = False
    return res
```

| Step | Description |
|---|---|
| 1 | Count existing Gelato image attachments before sync |
| 2 | Call parent method from `sale_gelato` to sync and create variants |
| 3 | Compare image count — if new images were added |
| 4 | If new images: set `is_published = False` |
| 5 | Return parent result |

**Use case:** When Gelato syncs and delivers new print images for a product (e.g., a new colorway or size variant), the product is automatically unpublished. This forces the store manager to review the new images and manually republish, ensuring no broken or unexpected images go live without review.

#### `_create_attributes_from_gelato_info(template_info)`

```python
def _create_attributes_from_gelato_info(self, template_info):
    self.description_ecommerce = template_info['description']
    return super()._create_attributes_from_gelato_info(template_info)
```

| Parameter | Type | Description |
|---|---|---|
| `template_info` | dict | Gelato template metadata, including 'description' key |

**Enhancement over `sale_gelato`:** The parent method creates product attributes (size, color) from Gelato's template info. This override additionally extracts `template_info['description']` and writes it to `description_ecommerce` (the eCommerce description shown on the website product page).

**Effect:** The website product page automatically shows the description synchronized from Gelato, without manual re-entry.

---

### `sale.order` — Cart Mixing Prevention

**File:** `models/sale_order.py`

```python
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _verify_updated_quantity(self, order_line, product_id, new_qty, uom_id, **kwargs):
        """ Override of `website_sale` to prevent mixing Gelato and non-Gelato products in the cart. """
        product = self.env['product.product'].browse(product_id)
        mixing_products = product.type != 'service' and any(
            (product.gelato_product_uid and not line.product_id.gelato_product_uid)
            or (not product.gelato_product_uid and line.product_id.gelato_product_uid)
            for line in self.order_line.filtered(lambda l: l.product_id.type != 'service')
        )
        if mixing_products:
            return 0, _(
                "The product %(product_name)s cannot be added to the cart as it requires separate"
                " shipping. Please place your order for the current cart first.",
                product_name=product.name,
            )
        return super()._verify_updated_quantity(order_line, product_id, new_qty, uom_id, **kwargs)
```

| Condition | Result |
|---|---|
| Product is a storable (non-service) AND cart has mixed Gelato/non-Gelato storable products | Returns `(0, warning_message)` — blocks the add |
| Otherwise | Delegates to parent `_verify_updated_quantity()` |

**Logic breakdown:**

```python
mixing_products = product.type != 'service' and any(
    # Adding a Gelato product to a cart with non-Gelato storable products
    (product.gelato_product_uid and not line.product_id.gelato_product_uid)
    # OR: Adding a non-Gelato storable product to a cart with Gelato products
    or (not product.gelato_product_uid and line.product_id.gelato_product_uid)
    for line in self.order_line.filtered(lambda l: l.product_id.type != 'service')
)
```

- `gelato_product_uid` is set on products linked to a Gelato product (from `sale_gelato`). If it is falsy, the product is not a Gelato product.
- `type != 'service'` filters out service products (e.g., gift wrapping, engraving) which do not require physical shipping and can coexist with Gelato products.
- The condition checks both directions: adding Gelato to non-Gelato cart, or adding non-Gelato to Gelato cart.

**Error message:** The returned warning message is displayed as a toast notification in the website storefront, telling the customer to complete their current order first.

**Note on redundancy:** The code comments explicitly state that this check is not redundant with the `sale_gelato` constraint on `sale.order` because that constraint is only evaluated at the end of checkout. This override provides immediate, user-friendly feedback at the point of adding to cart.

## Views

The module has no additional view files. All views are inherited from `website_sale` and `sale_gelato`. The delivery carrier data (`data/delivery_carrier_data.xml`) registers the Gelato-specific shipping carrier configuration used for print-on-demand shipments.

## Data Files

### `delivery_carrier_data.xml`

Configures the Gelato-specific delivery carrier used for print-on-demand shipments. This carrier is available in the website shipping method selection and is automatically applied when the cart contains only Gelato products. The carrier configuration includes rate fetching from Gelato's API and tracking integration.

## Integration Flow

```
[Store Manager creates/selects product with Gelato template]
    |
    v
[sale_gelato] product.template.gelato_template_ref set
    |
    v
[Gelato sync downloads print images]
    |
    v
[website_sale_gelato] action_create_product_variants_from_gelato_template()
    - image_count_before_sync < image_count_after_sync?
    - YES: is_published = False
    - description_ecommerce = template_info['description']
    |
    v
[Store Manager reviews images, publishes product]
    - _check_print_images_are_set_before_publishing() passes
    - Product visible on website
    |
    v
[Customer adds product to cart on website]
    - sale.order._verify_updated_quantity()
    - Checks for cart mixing
    - Product added successfully
    |
    v
[Checkout] sale_gelato constraint on sale.order checks cart is Gelato-only
```

## Related Modules

| Module | Role |
|---|---|
| [Modules/sale_gelato](sale_gelato.md) | Core Gelato integration; defines `gelato_product_uid`, `gelato_template_ref`, `gelato_image_ids`, and the base constraint on `sale.order` |
| [Modules/website_sale](website_sale.md) | eCommerce cart and checkout; provides `_verify_updated_quantity()` that is overridden here |
| [Modules/sale_gelato_stock](sale_gelato_stock.md) | Gelato stock management; does not directly interact but is often installed alongside |
| `sale` | Sale order processing; base `sale.order` model |
| `product` | Product master data; `product.template` and `product.document` models |

## Security Considerations

- The `_verify_updated_quantity` override is a write-prevention mechanism, not a write operation. It does not modify any records, only returns a blocking quantity and message.
- The constraints on `product.template` and `product.document` prevent accidental state changes that could break the website storefront.
- All Gelato-related data (images, descriptions) is fetched from Gelato's external API; this module does not introduce new external data flows.

## Performance Notes

- `_verify_updated_quantity` iterates over `order_line` with a Python `any()` comprehension, which is O(n) where n is the number of order lines. This is negligible compared to the database write that follows a successful add-to-cart.
- The `filtered('gelato_template_ref')` in `_check_print_images_are_set_before_publishing` uses the pre-computed `gelato_template_ref` field (stored or indexed) to avoid expensive joins.
- The `action_create_product_variants_from_gelato_template` override adds only a length comparison and one write, negligible overhead on top of the already expensive variant creation process.

## Migration Notes

Key points for migration:

- The `gelato_product_uid` field on `product.product` (from `sale_gelato`) is the key discriminator for the cart mixing check. If migrating from a custom Gelato implementation, ensure this field is populated correctly.
- The `_check_print_images_are_set_before_publishing` constraint uses `gelato_missing_images` (computed in `sale_gelato`). Ensure that computed field is still working after migration.
- If custom product types are introduced (e.g., `consu` or other delivery-requiring types), the `type != 'service'` filter may need to be updated to exclude those types as well.
- The `is_gelato` field on `product.document` must be correctly set by the Gelato sync process; otherwise, the print image removal constraint will not apply to Gelato images.

## See Also

- [Modules/sale_gelato](sale_gelato.md)
- [Modules/sale_gelato_stock](sale_gelato_stock.md)
- [Modules/website_sale](website_sale.md)
