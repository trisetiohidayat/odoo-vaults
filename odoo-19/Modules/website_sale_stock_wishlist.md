---
tags:
  - odoo
  - odoo19
  - modules
  - website
  - stock
  - wishlist
  - notifications
  - email
  - ecommerce
description: >
  Bridge module combining website_sale_stock inventory visibility with
  website_sale_wishlist wishlist management. Allows customers to request
  email notifications when out-of-stock wishlist items become available.
---

# website_sale_stock_wishlist

## Overview

- **Name**: Product Availability Notifications
- **Technical Name**: `website_sale_stock_wishlist`
- **Category**: Website/Website
- **Version**: `19.0.1.0.0` (same version scheme as Odoo 19)
- **Author**: Odoo S.A.
- **License**: LGPL-3
- **Summary**: Allows customers to request email notifications when a product on their wishlist comes back in stock. Bridges `website_sale_stock` inventory tracking with `website_sale_wishlist` wishlist management.
- **Auto-install**: `True` — automatically installs when both `website_sale_stock` and `website_sale_wishlist` are present.
- **No new models**: All behaviour is achieved through model extensions, controller patches, and frontend interaction overrides.

## Dependencies

```
depends = ['website_sale_stock', 'website_sale_wishlist']
```

### Full Dependency Tree

```
website_sale_stock_wishlist
├── website_sale_stock
│   ├── website_sale
│   │   └── product  (product.product, product.template)
│   └── stock        (stock.quant, stock.location)
└── website_sale_wishlist
    ├── website_sale
    │   └── product  (product.wishlist)
    └── product      (product.wishlist, product.product)
```

**Key dependency insight**: `product.wishlist` is the UI layer. The actual notification registry lives on `product.product.stock_notification_partner_ids` (defined in `website_sale_stock`). This module bridges the two.

## Module Structure

```
website_sale_stock_wishlist/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── product_template.py          # Extends product.template
│   └── product_wishlist.py          # Extends product.wishlist
├── controllers/
│   ├── __init__.py
│   └── variant.py                   # Extends WebsiteSaleVariantController
├── views/
│   └── website_sale_stock_wishlist_templates.xml
└── static/
    └── src/
        ├── interactions/
        │   ├── website_sale.js                    # Patches WebsiteSale interaction
        │   └── add_product_to_wishlist_button.js  # Patches AddProductToWishlistButton
        ├── js/
        │   └── variant_mixin.js                    # Monkey-patches VariantMixin
        ├── xml/
        │   └── product_availability.xml             # QWeb template for wishlist button
        └── scss/
            └── website_sale_stock_wishlist.scss
```

---

## L1: Business Flow — How Stock Availability Affects Wishlist Notifications

### Scenario 1: Visitor on Product Page — Out-of-Stock Product

```
1. User selects variant on product page
2. POST /website_sale/get_combination_info
   → WebsiteSaleVariantController.get_combination_info_website()
   → [sets context: website_sale_stock_wishlist_get_wish=True]
   → product.template._get_additionnal_combination_info()
   → appends is_in_wishlist to JSON response
3. JSON response: free_qty=0, is_in_wishlist=False
4. VariantMixin._onChangeCombinationStock() runs:
   a. Parent (website_sale_stock) → shows "Out of Stock" badge
   b. Appends website_sale_stock_wishlist.product_availability template
   c. "Add to wishlist" button shown (not in wishlist yet)
5. User clicks "Add to wishlist":
   → AddProductToWishlistButton.addProduct()
   → RPC /shop/wishlist/add
   → product.wishlist record created (partner_id=user.partner_id)
   → JS patch: hides "Add to wishlist" button, shows "Added"
6. User clicks "Get notified when back in stock" (website_sale_stock form):
   → _handleClickSubmitStockNotificationForm()
   → RPC /shop/add/stock_notification
   → partner found/created → stock_notification_partner_ids += partner
   → success message shown
7. Cron fires (hourly): product.product._send_availability_email()
   a. Finds product with stock_notification_partner_ids
   b. Checks free_qty > 0 → sends email to each partner
   c. Removes partner from stock_notification_partner_ids (one-time)
```

### Scenario 2: Visitor on Wishlist Page — Out-of-Stock Product

```
1. User visits /shop/wishlist
   → product.wishlist.current() returns wishes (session-based or partner-based)
   → product_wishlist view renders each wish
2. Template inherits website_sale_wishlist.product_wishlist:
   a. Out-of-stock badge shown (product_extra_information injection)
   b. Add to Cart button disabled (is_sold_out=True + !allow_out_of_stock_order)
3. product.wishlist.stock_notification = True/False shown
4. User clicks bell icon → stock_notification toggle
   → _inverse_stock_notification()
   → product.product.stock_notification_partner_ids += partner
```

### Scenario 3: Product Returns to Stock

```
1. Stock manager receives goods → stock.quant updated
2. product.product free_qty > 0
3. Hourly cron calls product.product._send_availability_email()
   a. self.search([('stock_notification_partner_ids', '!=', False)])
   b. For each product: if not _is_sold_out() → proceed
   c. For each partner: render email → mail.mail.create() → send()
   d. product.stock_notification_partner_ids -= partner (consumed)
4. Partner receives email: "The product 'X' is now available"
5. Next cron run skips this product (no subscribers left)
```

---

## L2: Field Types, Defaults, Constraints

### `product.wishlist` — Extension

**File**: `models/product_wishlist.py`
**Inherited from**: `website_sale_wishlist.models.product_wishlist.ProductWishlist`

#### `stock_notification` — Computed Boolean with Inverse

```python
stock_notification = fields.Boolean(
    compute='_compute_stock_notification',
    default=False,
    required=True,
)
```

| Attribute | Value | Rationale |
|---|---|---|
| `compute` | `_compute_stock_notification` | Read-only computation from `product.product._has_stock_notification()` |
| `default` | `False` | Newly added wishlist items do not auto-subscribe to notifications |
| `required` | `True` | Stored as a non-null column for efficient filtering in kanban views and API queries |

#### `_compute_stock_notification()` — Implementation

```python
@api.depends("product_id", "partner_id")
def _compute_stock_notification(self):
    for record in self:
        record.stock_notification = record.product_id._has_stock_notification(record.partner_id)
```

| Aspect | Detail |
|---|---|
| `@api.depends` | `"product_id", "partner_id"` — recomputes when either changes |
| Batching | Odoo's batch compute processes all records in a single query per related access |
| `product_id._has_stock_notification()` | Returns `partner in product.stock_notification_partner_ids` |
| Public users | `partner_id=False` on session-based wishlist entries → always `False` via this path |
| Session fallback | `website_sale_stock` also checks `request.session['product_with_stock_notification_enabled']` for public users |

#### `_inverse_stock_notification()` — Write-Through Setter

```python
def _inverse_stock_notification(self):
    for record in self:
        if record.stock_notification:
            record.product_id.stock_notification_partner_ids += record.partner_id
```

| Aspect | Detail |
|---|---|
| Trigger | Called when UI toggles the boolean to `True` |
| Action | Adds `record.partner_id` to `product.product.stock_notification_partner_ids` |
| `False` path | No action when toggling off — partner is not removed here |
| Cleanup | `_send_availability_email()` removes partners after sending |
| Silent failure | If `partner_id=False` (public user), silently does nothing |

### `product.template` — Extension

**File**: `models/product_template.py`
**Inherited from**: `product.template` (through `website_sale_stock`)

#### `_get_additionnal_combination_info()` — Wishlist State Injection

```python
def _get_additionnal_combination_info(self, product_or_template, quantity, uom, date, website):
    res = super()._get_additionnal_combination_info(product_or_template, quantity, uom, date, website)

    if not self.env.context.get('website_sale_stock_wishlist_get_wish'):
        return res

    if product_or_template.is_product_variant:
        product_sudo = product_or_template.sudo()
        res['is_in_wishlist'] = product_sudo._is_in_wishlist()

    return res
```

| Aspect | Detail |
|---|---|
| Return type | `dict` — merged into the combination info JSON response |
| Context guard | `website_sale_stock_wishlist_get_wish=True` set by `controllers/variant.py` |
| `sudo()` rationale | Wishlist for public users accessed via session may require elevated perms |
| `_is_in_wishlist()` | Calls `product.wishlist.current()` — search by partner or session |
| Guards | Only appends `is_in_wishlist` for product variants (not product templates) |

---

## L3: Cross-Model Integration, Override Patterns, Workflow Triggers

### Cross-Model Data Flow

```
product.wishlist (this module — UI layer)
    │
    ├── product_id ──────────► product.product
    │                              │
    │                        stock_notification_partner_ids (M2M)
    │                              │
    │                        res.partner (notification recipients)
    │
    └── partner_id ─────────► res.partner

product.template (this module — combination info)
    │
    └── _get_additionnal_combination_info() → appends is_in_wishlist

product.product (website_sale_stock — core infrastructure)
    │
    ├── stock_notification_partner_ids ──► res.partner
    ├── _has_stock_notification() ────────── used by _compute_stock_notification
    ├── _is_sold_out() ───────────────────── used by XML template conditions
    ├── _send_availability_email() ────────── cron entry point (not in this module)
    └── _to_markup_data() ─────────────────── schema.org inventory metadata
```

### Override Patterns Used

#### Pattern 1: Computed Field Extension

```python
# models/product_wishlist.py
class ProductWishlist(models.Model):
    _inherit = "product.wishlist"

    stock_notification = fields.Boolean(
        compute='_compute_stock_notification',
        default=False,
        required=True,
    )
```

Classic Odoo computed field with `required=True` to force column creation and non-null storage.

#### Pattern 2: Decorator-Style Controller Override

```python
# controllers/variant.py
class WebsiteSaleStockWishlistVariantController(WebsiteSaleVariantController):

    @route()
    def get_combination_info_website(self, *args, **kwargs):
        request.update_context(website_sale_stock_wishlist_get_wish=True)
        return super().get_combination_info_website(*args, **kwargs)
```

Minimal decorator-style override — sets context and delegates. Signature changes in parent are handled automatically via `*args, **kwargs`.

#### Pattern 3: OWL Interaction Patch (patchDynamicContent)

```javascript
// static/src/interactions/website_sale.js
patch(WebsiteSale.prototype, {
    setup() {
        super.setup();
        patchDynamicContent(this.dynamicContent, {
            '#wishlist_stock_notification_message': {
                't-on-click': this.onClickWishlistStockNotificationMessage.bind(this),
            },
            '#wishlist_stock_notification_form_submit_button': {
                't-on-click': this.onClickSubmitWishlistStockNotificationForm.bind(this),
            },
        });
    },
});
```

Odoo 17+ interaction system pattern. `patchDynamicContent` dynamically binds event handlers to DOM elements added via XML templates, without subclassing.

#### Pattern 4: VariantMixin Monkey-Patch

```javascript
// static/src/js/variant_mixin.js
const oldChangeCombinationStock = VariantMixin._onChangeCombinationStock;
VariantMixin._onChangeCombinationStock = function (ev, parent, combination) {
    oldChangeCombinationStock.apply(this, arguments);
    if (this.el.querySelector('.o_add_wishlist_dyn')) {
        const messageEl = this.el.querySelector('div.availability_messages');
        if (messageEl && !this.el.querySelector('#stock_wishlist_message')) {
            messageEl.append(
                renderToElement('website_sale_stock_wishlist.product_availability', combination) || ''
            );
        }
    }
};
```

Closure-based monkey-patch with pre-pending of parent method. The guard `!#stock_wishlist_message` prevents duplicate appends on repeated variant changes.

### Template Inheritance Patterns

#### `t-set` Override for Extra Information

```xml
<!-- views/website_sale_stock_wishlist_templates.xml -->
<template id="product_wishlist" inherit_id="website_sale_wishlist.product_wishlist">
    <xpath expr="//t[@t-call='website_sale.products_item']" position="inside">
        <t t-set="product_extra_information">
            <!-- injected into the parent template's output slot -->
        </t>
    </xpath>
</template>
```

This uses Odoo's named output slot pattern. `website_sale.products_item` has a `<t t-out="product_extra_information"/>` call. Multiple modules can inject into this slot via `t-set` overrides on the same selector.

#### Full Button Replacement

```xml
<xpath expr="//button[@id='add_to_cart_button']" position="replace">
    <!-- Full replacement needed because disabled state depends on stock check -->
</xpath>
```

A full replacement (not just attribute modification) is used because `t-att-disabled` cannot combine stock logic with the existing button's other dynamic attributes cleanly.

---

## L4: Version Changes, Security, Performance

### Odoo 18 → 19 Changes

The `website_sale_stock_wishlist` module had significant changes between Odoo 18 and 19, driven primarily by the Odoo 17+ frontend architecture overhaul.

| Change | Odoo Version | Detail |
|---|---|---|
| **Frontend rewrite to OWL** | Odoo 17 | The entire frontend was rewritten from jQuery events to OWL (Odoo Web Library) components. Static JS files changed from event binding to interaction patches. |
| **Interaction system** | Odoo 17 | `website_sale.js` became an OWL interaction. `patchDynamicContent()` replaced manual `addEventListener()` calls. |
| **`variant_mixin.js` monkey-patch** | Odoo 17 | Variant handling moved to `VariantMixin` class. The mixin patch pattern replaced older `$on` event handlers. |
| **`AddProductToWishlistButton` interaction** | Odoo 17 | `website_sale_wishlist` introduced `AddProductToWishlistButton` as an OWL interaction. This module patches it to handle wishlist post-add UI. |
| **`stock_notification` field added** | Odoo 17 | The boolean toggle on `product.wishlist` was introduced in Odoo 17 as part of the wishlist-stock bridge. |
| **`product.product._is_sold_out()` signature** | Odoo 18 | Method signature refined to use `website._get_product_available_qty()` with `sudo()` for accurate stock checks. |
| **`_send_availability_email()` cron** | Odoo 17 | The cron job moved from `ir.cron` with manual mail sending to `mail.render.mixin._render_encapsulate()` for consistent email templating. |
| **Odoo 19: No breaking changes** | Odoo 19 | The architecture remained stable in Odoo 19. The module version is `19.0.1.0.0`. |
| **`is_product_variant` check** | Odoo 17 | The `is_product_variant` boolean on `product.template` replaced older `type == 'product'` checks in combination info logic. |

### Odoo 17 → 18 Specific Changes

The primary Odoo 18 changes affecting this module (from `website_sale_stock` and `website_sale_wishlist`):

| Change | Impact on This Module |
|---|---|
| `product.product._is_sold_out()` now calls `website._get_product_available_qty(self.sudo())` | More accurate sold-out detection considering website-specific warehouse |
| `product.wishlist.current()` supports `website_id` filtering | Wishlist isolation per website improved |
| `VariantMixin` became the canonical variant change handler | Mixin patch in `variant_mixin.js` directly extends the handler |

### Security Analysis

| Area | Analysis | Risk Level |
|---|---|---|
| **Record rules** | `product.wishlist` for public users has `partner_id=False`. The `stock_notification` computed field reads `stock_notification_partner_ids` on `product.product` — a field that requires standard product read access. Public users have product read access for the shop to function. | Low |
| **Email exposure** | `stock_notification_partner_ids` is a Many2many on `product.product`. Any user with read access to product variants can see which partners are subscribed. In multi-company setups, ACLs on `res.partner` should be reviewed. | Medium |
| **Notification registration** | A user could toggle `stock_notification=True` on another user's wishlist entry (if they know the wishlist record ID) because the inverse setter only checks `partner_id`. However, they can only add their own `partner_id` — not someone else's. | Low |
| **Mail sending as superuser** | `_send_availability_email()` runs as superuser (via `ir.cron` `state='code'`). This bypasses record rules but the partner must exist in the DB (validated via `_partner_find_from_emails_single`). Only real partners receive emails. | Low |
| **Session-based wishlist** | Public users rely on `request.session['product_with_stock_notification_enabled']` for stock notifications — a session variable. If the session is hijacked, an attacker could theoretically register their own email for another user's wishlist product. `website_sale_stock` handles session-based registration via `/shop/add/stock_notification` endpoint with proper CSRF. | Medium |
| **CSRF protection** | The notification form submit goes through the standard `WebsiteSale` interaction which has CSRF enabled by default. | Low |
| **SQL injection** | All data access uses ORM — no raw SQL. | Low |

### Performance Notes

| Concern | Analysis | Mitigation |
|---|---|---|
| **`stock_notification` recompute** | `@api.depends("product_id", "partner_id")` is broad. Any change to product variant or partner recomputes all wishlist lines for that user. | Batching handles records efficiently in single query per model access. |
| **`_is_in_wishlist()` double-call** | On the wishlist page, called once in `product_template._get_additionnal_combination_info()` and once in the QWeb template per item. Each call runs `product.wishlist.current()` which re-runs the search. | Wishlist page size is typically small (< 50 items). Acceptable overhead. |
| **`_send_availability_email()` scalability** | Searches all `product.product` with non-empty `stock_notification_partner_ids`. Thousands of products with many subscribers = heavy cron. | Consider splitting: `domain=[('free_qty', '>', 0)]` pre-filter in the cron search, or `limit=100` with cron chaining. |
| **`_is_sold_out()` per product** | Called in XML templates for each wishlist item. Each call queries `website._get_product_available_qty()` — potentially N queries for N wishlist items. | The template rendering batches via the template engine, but individual product stock checks may still be separate queries. |
| **Session-based wishlist lookup** | `product.wishlist.current()` reads `request.session['wishlist_ids']` for public users. Session loss (cookie expiry) orphans wishlist records from the session. | Records remain in DB; re-login reconnects partner-based wishlist. |

---

## Core Notification Mechanism (Provided by `website_sale_stock`)

The email-sending logic lives in `website_sale_stock`, not in this module. This module bridges wishlist UI to that infrastructure.

### `product.product` Fields (from `website_sale_stock`)

```python
stock_notification_partner_ids = fields.Many2many(
    'res.partner',
    relation='stock_notification_product_partner_rel',
    string='Back in stock Notifications'
)
```

The explicit `relation` parameter ensures the join table name is stable across upgrades.

### `_send_availability_email()` — Cron Entry Point (from `website_sale_stock`)

```python
def _send_availability_email(self):
    for product in self.search([('stock_notification_partner_ids', '!=', False)]):
        if product._is_sold_out():
            continue  # Still out of stock — skip
        for partner in product.stock_notification_partner_ids:
            # Render email in partner's language
            self_ctxt = self.with_context(lang=partner.lang)
            product_ctxt = product.with_context(lang=partner.lang)
            body_html = self_ctxt.env['ir.qweb']._render(
                'website_sale_stock.availability_email_body',
                {'product': product_ctxt},
            )
            full_mail = product_ctxt.env['mail.render.mixin']._render_encapsulate(
                'mail.mail_notification_light', body_html,
                add_context={'model_description': _("Product")},
                context_record=product_ctxt,
            )
            mail_values = {
                'subject': _("The product '%(product_name)s' is now available", ...),
                'email_from': (product.company_id.partner_id or self.env.user).email_formatted,
                'email_to': partner.email_formatted,
                'body_html': full_mail,
            }
            mail = self_ctxt.env['mail.mail'].sudo().create(mail_values)
            mail.send(raise_exception=False)
            product.stock_notification_partner_ids -= partner  # Consume
```

**One-time notification**: Each partner is removed from the M2M after the email is sent. Re-notification requires re-subscription.

**Cron configuration** (`website_sale_stock/data/ir_cron_data.xml`):
- Name: `Product: send email regarding products availability`
- Interval: every 1 hour
- Model: `product.product`
- Code: `model._send_availability_email()`

---

## Extension Points

### Adding a Wishlist Stock Status to the Cart

To show out-of-stock badges on cart lines:

```xml
<xpath expr="//tr[@t-foreach='order.website_order_line']" position="inside">
    <t t-set="line_product" t-value="line.product_id"/>
    <span t-if="line_product._is_sold_out() and not line_product.allow_out_of_stock_order"
          class="badge bg-danger">Out of stock</span>
</xpath>
```

### Hooking into Notification Registration

To run custom logic when a user subscribes to stock notifications:

```python
# Override in a custom module
class ProductWishlistExtended(models.Model):
    _inherit = "product.wishlist"

    def _inverse_stock_notification(self):
        super()._inverse_stock_notification()
        for record in self:
            if record.stock_notification and record.partner_id:
                # Custom analytics or CRM event
                self.env['crm.lead'].sudo().create({
                    'name': f'Stock notification: {record.product_id.name}',
                    'partner_id': record.partner_id.id,
                    'type': 'lead',
                })
```

### Disabling Notifications for Specific Products

Override `_inverse_stock_notification()` to skip certain product categories:

```python
def _inverse_stock_notification(self):
    for record in self:
        if record.stock_notification:
            if record.product_id.categ_id.notificate_blacklist:
                continue
            record.product_id.stock_notification_partner_ids += record.partner_id
```

---

## Related Modules

- [[Modules/website_sale_stock]] — Provides `_send_availability_email()` cron, `product.product` stock fields, and `stock_notification_partner_ids`
- [[Modules/website_sale_wishlist]] — Provides `product.wishlist` model, `/shop/wishlist` controller, and `AddProductToWishlistButton` interaction
- [[Modules/website_sale]] — Core e-commerce; provides `VariantMixin`, `WebsiteSale` interaction, and combination info endpoint
- [[Modules/Product]] — Product variant model; all stock and wishlist operations ultimately target `product.product`
- [[Modules/Stock]] — `stock.quant` for inventory tracking; `stock.location` for warehouse-specific stock levels
