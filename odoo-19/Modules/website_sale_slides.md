---
title: website_sale_slides
tags:
  - odoo
  - odoo19
  - modules
  - website
  - slides
  - ecommerce
  - elearning
description: "Sell eLearning courses as e-commerce products — slide.channel enrollment via sale order confirmation"
---

# website_sale_slides

> **Sell Courses** — Bridges `website_slides` (eLearning) and `website_sale` (eCommerce). Courses (`slide.channel`) with `enroll='payment'` are linked to `product.product` variants with `service_tracking='course'`. When a customer confirms a sale order containing a course product, `slide.channel._action_add_members()` enrolls the buyer automatically.

## Module Information

| Property | Value |
|----------|-------|
| **Technical Name** | `website_sale_slides` |
| **Category** | Website/eLearning |
| **Version** | 1.0 |
| **Summary** | Sell your courses online |
| **Depends** | `website_slides`, `website_sale` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

---

## L1: Business Concept — How Course Purchases Work on e-Commerce

The module creates a purchase-to-enrollment pipeline:

```
slide.channel (enroll='payment', product_id → product.product)
       ↓
product added to website cart (/shop)
       ↓
sale.order confirmed (_action_confirm)
       ↓
channels.sudo()._action_add_members(partner_id)
       ↓
slide.channel.partner created (member_status='joined')
       ↓
"Start Learning" button on confirmation page (invitation_link)
```

**Core enrollment trigger**: `sale.order._action_confirm()` (after `super()`) searches for payment-enrolled channels linked to any product in the order, then calls `_action_add_members()` on each. A single product can theoretically be linked to multiple channels (though the default UX creates one product per channel).

**Key behaviors**:
- Published courses can be added to cart even by anonymous website visitors (`_is_add_to_cart_allowed` override uses `sudo().search_count`)
- Course products cannot be re-ordered — `sale.order.line._is_reorder_allowed` returns `False`
- Course products are capped at quantity 1 in cart — `_verify_updated_quantity` returns `(1, warning)` for `new_qty > 1`
- If the linked product is unpublished, the course page shows "Course Unavailable" (buy button hidden)
- Product publish state is synchronized with course publish state: `_synchronize_product_publish()` publishes the product when a payment channel goes live, and unpublishes the product when all linked payment channels are unpublished

---

## L2: Field Types, Defaults, Constraints

### `slide.channel` (extended from `website_slides`)

Defined in: `models/slide_channel.py`

**New fields:**

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `enroll` | `Selection` | — | Extends `website_slides` with `'payment'` / `"On payment"`. `ondelete={'payment': lambda recs: recs.write({'enroll': 'invite'})}` — on module uninstall, existing payment channels fall back to invite-only. Does NOT cascade-delete memberships |
| `product_id` | `Many2one product.product` | `False` | Domain: `service_tracking='course'`. `index='btree_not_null'` (partial index on non-null rows). `_get_default_product_id()` auto-links the unique such product if exactly one exists |
| `product_sale_revenues` | `Monetary` (computed) | `0.0` | `@api.depends('product_id')`. Reads from `sale.report` via `_read_group`. Group-restricted to `sales_team.group_sale_salesman` |
| `currency_id` | `Many2one res.currency` | `product_id.currency_id` | Related field; drives monetary display in kanban/list views |

**SQL constraint:**

```python
_product_id_check = models.Constraint(
    "CHECK( enroll!='payment' OR product_id IS NOT NULL )",
    'Product is required for on payment channels.',
)
```

This is a DB-level guard — even raw SQL cannot insert a payment channel without a product. The domain on the field provides the application-layer complement.

**Key method defaults**:

```python
def _get_default_product_id(self):
    product_courses = self.env['product.product'].search(
        [('service_tracking', '=', 'course')], limit=2)
    return product_courses.id if len(product_courses) == 1 else False
```

`limit=2` (not `limit=1`) — returns the product only if exactly one exists. Returns `False` if zero or multiple exist.

---

### `product.product` (extended)

Defined in: `models/product_product.py`

**New field:**

| Field | Type | Notes |
|-------|------|-------|
| `channel_ids` | `One2many slide.channel` | Inverse of `slide.channel.product_id` |

**Method overrides:**

`get_product_multiline_description_sale()`: Returns `"Access to: Channel A\nChannel B"` for payment-linked products. Falls back to `super()` for non-payment products.

---

### `product.template` (extended)

Defined in: `models/product_template.py`

**New selection option in `service_tracking`:**

| Value | Label | `ondelete` |
|-------|-------|------------|
| `'course'` | `"Course Access"` | `'set default'` — on uninstall, products revert to empty service tracking |

`_get_product_types_allow_zero_price()` includes `"course"` — free course access products are allowed at `list_price = 0`.

`_service_tracking_blacklist()` adds `'course'` to the exclusion list.

---

### `sale.order` (extended from `website_sale`)

Defined in: `models/sale_order.py`

Two method overrides only — no new fields:

`_action_confirm()`: Calls `channels.sudo()._action_add_members(sale_order.partner_id)` after `super()`. Idempotent but re-running re-adds members.

`_verify_updated_quantity(order_line, product_id, new_qty, uom_id, **kwargs)`: If `product.service_tracking == 'course'` and `new_qty > 1`, returns `(1, warning_message)`. Called before any cart mutation.

---

### `sale.order.line` (extended)

Defined in: `models/sale_order_line.py`

`_is_reorder_allowed()`: Returns `False` when `self.service_tracking == 'course'`. Blocks the "Reorder" button on `/my/orders`.

---

## L3: Cross-Model Integration, Override Patterns, Workflow Triggers

### Cross-Model Map

| From | To | Integration |
|------|----|-------------|
| `slide.channel` | `product.product` (via `product_id`) | Course linked to product; product drives cart/add-to-cart |
| `product.product` | `slide.channel` (via `channel_ids` O2M) | Access all channels for a product |
| `sale.order` | `slide.channel` (via `_action_confirm`) | Enrollment trigger |
| `sale.report` | `product.product` (via `product_id`) | Revenue aggregation source |

### Override Patterns

| Model | Pattern | Override Method |
|-------|---------|-----------------|
| `slide.channel` | `_inherit = 'slide.channel'` | `create()`, `write()`, `_get_default_product_id()`, `_compute_product_sale_revenues()`, `_synchronize_product_publish()`, `action_view_sales()` |
| `product.product` | `_inherit = 'product.product'` | `_is_add_to_cart_allowed()`, `get_product_multiline_description_sale()` |
| `product.template` | `_inherit = 'product.template'` | `_prepare_service_tracking_tooltip()`, `_get_product_types_allow_zero_price()`, `_service_tracking_blacklist()` |
| `sale.order` | `_inherit = 'sale.order'` | `_action_confirm()`, `_verify_updated_quantity()` |
| `sale.order.line` | `_inherit = 'sale.order.line'` | `_is_reorder_allowed()` |

### Workflow Trigger: SO Confirmation → Channel Enrollment

```
sale.order._action_confirm()
    → super() confirms SO
    → so_lines = sale.order.line search
    → products = mapped product_id
    → related_channels = slide.channel search (
          product_id in products.ids,
          enroll='payment'
      )
    → channels_per_so dict built (SO → set of channels)
    → for each SO, channels.sudo()._action_add_members(partner_id)
    → slide.channel.partner created with member_status='joined'
```

### Failure Modes

| Failure | Mechanism | Result |
|---------|-----------|--------|
| Course without product (`enroll='payment'`, `product_id=False`) | SQL `CHECK` constraint | DB-level rejection |
| Unpublished product on published course | `_prepare_additional_channel_values` returns `product_info=False` | "Course Unavailable" alert shown |
| Re-running `_action_confirm` on confirmed SO | `_action_add_members` not idempotent | Partner re-added; dedup depends on `website_slides` |
| Anonymous user adds course to cart | `_is_add_to_cart_allowed` uses `sudo().search_count` | Allowed; enrollment requires authenticated user |

### Controllers

**`WebsiteSaleSlides` (extends `WebsiteSale`)** — `controllers/sale.py`:
- `_prepare_shop_payment_confirmation_values(order)`: After payment confirmation, builds `{channel: channel_partner}` dict from `slide.channel.partner` (with `sudo()`), passes to QWeb template as `course_memberships`

**`WebsiteSaleSlides` (extends `WebsiteSlides`)** — `controllers/slides.py`:
- `GET /slides/get_course_products` (JSON-RPC, `auth='user'`): Returns all `service_tracking='course'` products with formatted names/prices; used in admin course UI
- `_prepare_additional_channel_values(values, **kwargs)`: For payment channels, calls `product._get_combination_info_variant()` (without sudo) to inject price/discount/availability into QWeb template data attributes

---

## L4: Odoo 18 → 19 Changes, Security

### Version Changes Odoo 18 → 19

**Module structure**: No major architectural restructuring between Odoo 18 and 19. Same 5-model extension pattern (slide_channel, product_product, product_template, sale_order, sale_order_line) and same two-controller pattern (extends WebsiteSale and WebsiteSlides).

**Revenue reporting**: `product_sale_revenues` uses `sale.report`. The `sale_report_action_slides` action filters on `("product_id.channel_ids", "!=", False)` — works because `product.product` has the `channel_ids` O2M field added by this module.

**Product publish sync**: `_synchronize_product_publish()` is a notable addition. It ensures:
1. Publishing any payment channel → linked product published (`is_published = True`)
2. Unpublishing all payment channels using a product → product unpublished

This replaces any manual product publish workflow and keeps the e-commerce buy button in sync with the channel's publish state.

**Enrollment trigger**: `_action_confirm` is consistent across both versions — calls `channels.sudo()._action_add_members()` after `super()`.

### Security

| Concern | Assessment | Notes |
|---------|------------|-------|
| SQL injection | Safe | ORM only; no raw SQL |
| Access control | Mixed (intentional) | `_is_add_to_cart_allowed` uses `sudo()` for published-channel check; `_action_confirm` uses `sudo()` for enrollment |
| `product_sale_revenues` data leak | **Medium risk** | Group-restricted to `sales_team.group_sale_salesman`, but `sale.report` aggregates across all websites — potential cross-website leak in multi-website deployments |
| Anonymous cart add | Low risk | Appropriate for e-commerce; full enrollment requires authenticated user |
| CSRF | Safe | JSON-RPC uses Odoo's built-in CSRF handling |

---

## Related

- [Modules/website_slides](odoo-18/Modules/website_slides.md) — eLearning base: channel model, slide content, membership management
- [Modules/website_sale](odoo-18/Modules/website_sale.md) — eCommerce base: cart, checkout, payment, SO workflow
- [Modules/sale](odoo-18/Modules/sale.md) — Sale order confirmation and workflow
- [Modules/product](odoo-18/Modules/product.md) — Product template and variants
- [Modules/sale_mrp](odoo-18/Modules/sale_mrp.md) — Kit products; used by website_sale_mrp for kit availability display
