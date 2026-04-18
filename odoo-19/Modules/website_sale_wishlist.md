---
title: website_sale_wishlist (Shopper's Wishlist)
draft: false
tags:
  - #odoo
  - #odoo19
  - #modules
  - #website
  - #e-commerce
  - #wishlist
  - #product
created: 2026-04-11
description: Allow shoppers to create and manage personalized wishlists of products for future purchase reference.
---

# website_sale_wishlist

> **Display Name:** Shopper's Wishlist
> **Version:** 1.0
> **Category:** Website/Website
> **Summary:** Allow shoppers to enlist products
> **License:** LGPL-3
> **Author:** Odoo S.A.
> **Module Path:** `odoo/addons/website_sale_wishlist/`
> **Auto-install:** Yes
> **Instance:** `/shop/wishlist`

## Overview

`website_sale_wishlist` is a thin but architecturally rich module that provides wishlist functionality for the e-commerce stack. It builds entirely on top of `website_sale` and extends four core Odoo layers: the ORM model, the website configuration, the HTTP controller API, and the frontend JavaScript interactions.

The module's central design insight is a **dual-layer storage model**: anonymous visitors store wishlist entries in the browser session (server-side `product.wishlist` records with no `partner_id`), while logged-in users store them permanently against their `res.partner` record. Upon login, `_check_wishlist_from_session()` migrates the anonymous layer to the authenticated layer transparently.

---

## Dependencies

```python
'depends': ['website_sale']
```

`website_sale_wishlist` has no other dependencies. It extends `website_sale` product display, cart, and layout infrastructure, and relies on `website` for multi-website context.

**Auto-install:** Yes — installs automatically when `website_sale` is installed.

---

## Module Structure

```
website_sale_wishlist/
├── __manifest__.py
├── __init__.py                   # imports models, controllers
├── models/
│   ├── __init__.py               # imports product_wishlist, res_users, website
│   ├── product_wishlist.py       # Core model + mixin extensions
│   ├── res_users.py              # Login hook for session→account migration
│   └── website.py                # Wishlist page layout fields
├── controllers/
│   ├── __init__.py               # imports main, website_sale
│   ├── main.py                   # JSON-RPC API: add/remove/get_product_ids
│   └── website_sale.py           # Extends WebsiteSale to inject wishlist data
├── views/
│   ├── website_sale_wishlist_template.xml
│   └── website_sale_wishlist_template_svg.xml  # Animated empty-state SVG
├── security/
│   ├── website_sale_wishlist_security.xml       # ir.rule definitions
│   └── ir.model.access.csv
├── static/src/
│   ├── js/
│   │   └── website_sale_wishlist_utils.js      # sessionStorage helpers
│   ├── interactions/                           # Odoo 19 Interaction components
│   │   ├── add_product_to_wishlist_button.js
│   │   ├── product_wishlist.js
│   │   ├── product_detail.js
│   │   └── wishlist_navbar.js
│   ├── website_builder/
│   │   ├── wishlist_page_option_plugin.js      # Visual builder actions
│   │   └── *.xml                               # Option panel templates
│   ├── scss/
│   │   └── website_sale_wishlist.scss
│   └── tests/
└── tests/
    └── test_wishlist_process.py                # HttpCase JS tour
```

---

## Core Model: `product.wishlist`

**File:** `~/odoo/odoo19/odoo/addons/website_sale_wishlist/models/product_wishlist.py`

### Model Definition

```python
class ProductWishlist(models.Model):
    _name = 'product.wishlist'
    _description = 'Product Wishlist'
    _product_unique_partner_id = models.Constraint(
        'UNIQUE(product_id, partner_id)',
        'Duplicated wishlisted product for this partner.',
    )
```

### Fields

| Field | Type | Required | Default | Index | Notes |
|---|---|---|---|---|---|
| `partner_id` | `Many2one(res.partner)` | No | — | `btree_not_null` | Owner of the wishlist entry. Nullable to support session-bound (anonymous) entries. The `btree_not_null` index optimizes both `= some_id` and `IS NOT NULL` lookups. |
| `product_id` | `Many2one(product.product)` | **Yes** | — | (default) | The product variant being wished-for. One `product_id` per `partner_id` enforced by unique constraint. |
| `currency_id` | `Many2one(res.currency)` | No | — | (related) | Derived: `website_id.currency_id`. Readonly. Stored implicitly for monetary display. |
| `pricelist_id` | `Many2one(product.pricelist)` | No | — | (default) | Records the active pricelist when the item was added. Used to determine which price was "the price at time of addition." |
| `price` | `Monetary` | No | — | (default) | Product sale price at time of addition. Stored, not computed. See rationale below. |
| `website_id` | `Many2one(website)` | **Yes** | — | (default) | `ondelete='cascade'` — if the website is deleted, all its wishlist entries are deleted. |
| `active` | `Boolean` | Yes | `True` | (default) | Soft-delete flag. The `res.partner.wishlist_ids` O2M applies `domain=[('active','=',True)]`. |

### Why `price` Is Stored (Not Computed)

The price is stored at addition time intentionally. If a product's price changes — a seasonal discount, a pricelist rule update, a manager manually changing the list price — the wishlist still shows the price "when I added this." This is meaningful UX: the stored price serves as a historical record of the buyer's intent at the time of saving. The `current()` method does not recompute price; it only uses the stored value for display.

### Why `pricelist_id` Is Stored

`price` is stored in the website's currency, but the effective price depends on the active pricelist. Storing `pricelist_id` preserves the context: the wishlist shows "product was $X when added using pricelist Y." This is primarily for audit/debugging; the field is not actively used in computed logic.

### The Unique Constraint and Anonymous Users

The constraint `UNIQUE(product_id, partner_id)` uses SQL semantics where `NULL != NULL`. PostgreSQL treats multiple rows with `partner_id = NULL` as distinct. This means the DB constraint does **not** prevent duplicate wishlist entries for anonymous users — the session layer (`sessionStorage` + `request.session`) prevents duplicates in practice for the same browser session.

For logged-in users, the constraint is enforced at the DB level: a partner cannot add the same product variant to their wishlist twice.

---

## Methods

### `current()` — `@api.model`

```python
@api.model
def current(self):
    """Get all wishlist items that belong to current user or session,
    filter products that are unpublished."""
    if not request:
        return self

    if request.website.is_public_user():
        wish = self.sudo().search([('id', 'in', request.session.get('wishlist_ids', []))])
    else:
        wish = self.search([
            ("partner_id", "=", self.env.user.partner_id.id),
            ('website_id', '=', request.website.id)
        ])

    return wish.filtered(
        lambda wish:
            wish.sudo().product_id.product_tmpl_id.website_published
            and wish.sudo().product_id.product_tmpl_id._is_add_to_cart_possible()
    )
```

**Execution branches:**

- **No `request` context** (e.g., JSON-RPC from a background cron, Odoo.sh worker): returns empty recordset — no context to determine user or session.
- **Public/anonymous user** (`is_public_user() == True`): reads `request.session.get('wishlist_ids', [])` — a list of `product.wishlist` record IDs stored server-side in the session. Records are fetched with `sudo()` because record rules would otherwise block access.
- **Logged-in user**: searches by `partner_id = self.env.user.partner_id.id` AND `website_id = request.website.id`.

**Post-filter logic:**

The `.filtered()` call runs in Python after the SQL search. For each wishlist record, it:
1. Calls `.sudo()` on the product to bypass record rules that might hide unpublished products.
2. Checks `product_tmpl_id.website_published == True` — unpublished products are excluded.
3. Checks `_is_add_to_cart_possible()` — excludes products that are no longer sellable (e.g., all variants have `available_threshold` exceeded, or the product was archived).

**Performance note for large wishlists:** The `.filtered()` with two `.sudo().product_id.product_tmpl_id` traversals per iteration is an N+1 pattern. For partners with hundreds of wishlist items, this could cause performance degradation. A `prefetch_id` strategy or a direct SQL domain would be more efficient for high-volume stores.

---

### `_add_to_wishlist(pricelist_id, currency_id, website_id, price, product_id, partner_id=False)` — `@api.model`

```python
@api.model
def _add_to_wishlist(self, pricelist_id, currency_id, website_id, price, product_id, partner_id=False):
    wish = self.env['product.wishlist'].create({
        'partner_id': partner_id,
        'product_id': product_id,
        'currency_id': currency_id,
        'pricelist_id': pricelist_id,
        'price': price,
        'website_id': website_id,
    })
    return wish
```

Factory method called exclusively from the controller. Parameters come directly from `request` context:
- `pricelist_id`: `request.pricelist.id` — the active pricelist for the current user/website.
- `currency_id`: `request.website.currency_id.id` — the website's base currency.
- `website_id`: `request.website.id` — ensures the wishlist entry is scoped to the current website.
- `price`: Fetched via `product._get_combination_info_variant()['price']` in the controller — the product's effective price for the active pricelist and combination.
- `partner_id`: `False` for anonymous users; `request.env.user.partner_id.id` for logged-in users.

**No uniqueness enforcement here for anonymous users** — the controller caller is responsible for client-side prevention of double-click submissions.

---

### `_check_wishlist_from_session()` — `@api.model`

```python
@api.model
def _check_wishlist_from_session(self):
    """Assign all wishlist without partner from this the current session"""
    session_wishes = self.sudo().search([
        ('id', 'in', request.session.get('wishlist_ids', []))
    ])
    partner_wishes = self.sudo().search([
        ("partner_id", "=", self.env.user.partner_id.id)
    ])
    partner_products = partner_wishes.mapped("product_id")
    # Remove session products already present for the user
    duplicated_wishes = session_wishes.filtered(
        lambda wish: wish.product_id <= partner_products
    )
    session_wishes -= duplicated_wishes
    duplicated_wishes.unlink()
    # Assign the rest to the user
    session_wishes.write({"partner_id": self.env.user.partner_id.id})
    request.session.pop('wishlist_ids')
```

**Step-by-step algorithm:**

1. `session_wishes`: fetch all `product.wishlist` records whose IDs are in the browser session, with no `partner_id` (created while anonymous).
2. `partner_wishes`: fetch all existing wishlist entries for the now-authenticated partner.
3. `partner_products`: extract the `product_id` records from the partner's existing wishlist (as a `product.product` recordset).
4. `duplicated_wishes`: any session wishlist record whose `product_id` is already in `partner_products` is a duplicate. These are deleted immediately.
5. Remaining `session_wishes` (non-duplicates) are assigned to the partner via `write({'partner_id': ...})`.
6. `request.session.pop('wishlist_ids')` clears the session list so the migration runs exactly once.

**Edge cases:**
- If the partner already has a wishlist entry for a session product: the session entry is deleted, not merged. The partner keeps their existing entry (with its original price, currency, and creation date).
- If the migration fails partway (e.g., write permission denied), partial migration can occur. The session list is popped regardless.
- The method uses `sudo()` throughout because the session records were created with `sudo()` and the current user's record rules would otherwise block reads.

---

### `_gc_sessions(*args, **kwargs)` — `@api.autovacuum`

```python
@api.autovacuum
def _gc_sessions(self, *args, **kwargs):
    """Remove wishlists for unexisting sessions."""
    self.with_context(active_test=False).search([
        ("create_date", "<", fields.Datetime.to_string(
            datetime.now() - timedelta(weeks=kwargs.get('wishlist_week', 5))
        )),
        ("partner_id", "=", False),
    ]).unlink()
```

**Purpose:** Delete all orphan wishlist entries — records with no `partner_id` (anonymous session entries) older than `wishlist_week` weeks.

**Key details:**
- `active_test=False`: ensures even soft-deleted records are removed. Since `unlink()` is used (not `write({'active': False})`), this is belt-and-suspenders.
- `partner_id = False`: targets only anonymous entries. Logged-in users' wishlists are never GC'd.
- `wishlist_week` defaults to 5 but can be overridden via `kwargs` (pulled from `ir.config_parameter` if the cron is invoked that way).
- Runs as an `@api.autovacuum` method — Odoo schedules these automatically as low-priority background jobs.

---

## Cross-Model Extensions

### `res.partner` — `wishlist_ids`

```python
class ResPartner(models.Model):
    _inherit = 'res.partner'

    wishlist_ids = fields.One2many(
        'product.wishlist', 'partner_id',
        string='Wishlist',
        domain=[('active', '=', True)]
    )
```

Reverse O2M of `product.wishlist.partner_id`. The `domain=[('active','=',True)]` means archived/hidden wishlist entries are excluded from this field. Purely a convenience accessor — the canonical access path is `product.wishlist.current()`.

### `product.template` — `_is_in_wishlist()`

```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _is_in_wishlist(self):
        self.ensure_one()
        return self in self.env['product.wishlist'].current().mapped(
            'product_id.product_tmpl_id'
        )
```

Returns `bool`. Checks whether this product template's ID appears in the current user's wishlist at the template level (i.e., any variant of this template is in the wishlist). Called from the product detail page CTA template to determine button label and icon state.

### `product.product` — `_is_in_wishlist()`

```python
class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _is_in_wishlist(self):
        self.ensure_one()
        return self in self.env['product.wishlist'].current().mapped('product_id')
```

Returns `bool`. Checks at the variant level — the wishlist entry's `product_id` must match this exact variant. The cart page "Save for Later" feature uses this.

### `website` — Layout Fields

**File:** `models/website.py`

```python
wishlist_opt_products_design_classes = fields.Char(
    default=(
        'o_wsale_products_opt_layout_catalog o_wsale_products_opt_design_thumbs '
        'o_wsale_products_opt_name_color_regular '
        'o_wsale_products_opt_thumb_cover o_wsale_products_opt_img_secondary_show '
        'o_wsale_products_opt_img_hover_zoom_out_light o_wsale_products_opt_has_cta '
        'o_wsale_products_opt_actions_inline o_wsale_products_opt_has_description '
        'o_wsale_products_opt_actions_promote o_wsale_products_opt_cc1 '
    ),
)
wishlist_grid_columns = fields.Integer(default=5)
wishlist_mobile_columns = fields.Integer(default=2)
wishlist_gap = fields.Char(default="16px")
```

Four fields persisted per `website` record. They are consumed in the `product_wishlist` template as `data-*` attributes and CSS custom properties:
- `wishlist_opt_products_design_classes` → `class` attribute on `#o_comparelist_table` (the wishlist grid container).
- `wishlist_grid_columns` → `data-wishlist-grid-columns` attribute; SCSS loops 2–6 columns from this.
- `wishlist_mobile_columns` → `data-wishlist-mobile-columns` attribute; CSS sets 1 or 2 columns on mobile.
- `wishlist_gap` → `--o-wsale-wishlist-grid-gap` CSS custom property.

---

## `res.users` — Login Hook

**File:** `models/res_users.py`

```python
class ResUsers(models.Model):
    _inherit = "res.users"

    def _check_credentials(self, credential, env):
        """Make all wishlists from session belong to its owner user."""
        result = super()._check_credentials(credential, env)
        if request and request.session.get('wishlist_ids'):
            self.env["product.wishlist"]._check_wishlist_from_session()
        return result
```

**Trigger:** Runs on every standard Odoo login — username/password, OAuth, SAML, etc. — as part of `_check_credentials()`. The check `request and request.session.get('wishlist_ids')` makes it a no-op if there's no HTTP request in context or no session wishlists to migrate.

**Execution context:** Runs as the authenticating user. `_check_wishlist_from_session()` internally uses `sudo()`, so it bypasses record rules and can read/write records that the user would not normally have access to (the anonymous session records).

**Programmatic login risk:** Since this fires on `res.users.login()`, programmatic `sudo()` logins (e.g., `request.session.authenticate()`) will also trigger the migration. This is typically the intended behavior.

---

## Controllers

### `WebsiteSaleWishlist` — `controllers/main.py`

Extends Odoo's base `Controller` class (not `main.WebsiteSale`). Provides the public JSON-RPC API for all wishlist operations.

#### `POST /shop/wishlist/add` — `add_to_wishlist(product_id)`

```python
@route('/shop/wishlist/add', type='jsonrpc', auth='public', website=True)
def add_to_wishlist(self, product_id, **kw):
    product = request.env['product.product'].browse(product_id)
    price = product._get_combination_info_variant()['price']

    Wishlist = request.env['product.wishlist']
    if request.website.is_public_user():
        Wishlist = Wishlist.sudo()
        partner_id = False
    else:
        partner_id = request.env.user.partner_id.id

    wish = Wishlist._add_to_wishlist(
        request.pricelist.id,
        request.website.currency_id.id,
        request.website.id,
        price,
        product_id,
        partner_id
    )

    if not partner_id:
        request.session['wishlist_ids'] = request.session.get('wishlist_ids', []) + [wish.id]

    return wish
```

- `auth='public'`: accessible without login, including anonymous visitors.
- `website=True`: automatically sets `request.website` context.
- **Anonymous path**: creates record via `sudo()`, sets `partner_id=False`, appends record ID to `request.session['wishlist_ids']`.
- **Logged-in path**: creates with `partner_id = request.env.user.partner_id.id`.
- The price is fetched fresh via `_get_combination_info_variant()` — not from any prior state — so it reflects the current effective price for the user's pricelist.

**Duplicate-click protection**: The `Interaction` layer (`AddProductToWishlistButton`) checks `sessionStorage` before making this RPC call and immediately disables the button on return. No server-side deduplication for anonymous users.

#### `GET /shop/wishlist` — `get_wishlist()`

```python
@route('/shop/wishlist', type='http', auth='public', website=True, sitemap=False)
def get_wishlist(self, **kw):
    wishes = request.env['product.wishlist'].with_context(display_default_code=False).current()
    return request.render('website_sale_wishlist.product_wishlist', {'wishes': wishes})
```

- `sitemap=False`: the wishlist page is excluded from the XML sitemap.
- `display_default_code=False`: suppresses the internal product variant code from the product name, providing a cleaner display.
- `current()` filters unpublished/invalid products server-side, so the template receives only valid items.

#### `POST /shop/wishlist/remove/<int:wish_id>` — `remove_from_wishlist(wish_id)`

```python
@route('/shop/wishlist/remove/<int:wish_id>', type='jsonrpc', auth='public', website=True)
def remove_from_wishlist(self, wish_id, **kw):
    wish = request.env['product.wishlist'].browse(wish_id)
    if request.website.is_public_user():
        wish_ids = request.session.get('wishlist_ids') or []
        if wish_id in wish_ids:
            request.session['wishlist_ids'].remove(wish_id)
            request.session.touch()
            wish.sudo().unlink()
    else:
        wish.unlink()
    return True
```

- **Anonymous**: verifies `wish_id` is in `session['wishlist_ids']` before removing. Calls `session.touch()` to extend the session lifetime. Then hard-deletes the record via `sudo().unlink()`.
- **Logged-in**: direct `unlink()` — record rules enforce that users can only unlink their own entries.
- No `website_id` check in the anonymous path — `wish_id in session['wishlist_ids']` is the authorization.

#### `GET /shop/wishlist/get_product_ids` — `shop_wishlist_get_product_ids()`

```python
@route('/shop/wishlist/get_product_ids', type='jsonrpc', auth='public', website=True, readonly=True)
def shop_wishlist_get_product_ids(self):
    return request.env['product.wishlist'].current().product_id.ids
```

- `readonly=True`: the route has no side effects.
- Returns only `product_id.ids` (variant IDs), not full wishlist records. The caller (`WishlistNavbar`) uses this to populate `sessionStorage` on page load.

---

### `WebsiteSaleWishlist` (extends `main.WebsiteSale`) — `controllers/website_sale.py`

```python
class WebsiteSaleWishlist(main.WebsiteSale):
```

Overrides the shop product listing to inject wishlist state into the template rendering context.

#### `_get_additional_shop_values(values, **kwargs)` — override

```python
def _get_additional_shop_values(self, values, **kwargs):
    vals = super()._get_additional_shop_values(values, **kwargs)
    vals['products_in_wishlist'] = (
        request.env['product.wishlist'].current().product_id.product_tmpl_id
    )
    return vals
```

Hook into the shop product listing render pipeline. Adds `products_in_wishlist` — a `product.template` recordset — to the template context. Used by `website_sale.shop_product_buttons` to render the filled/empty heart icon per product card without additional RPC calls.

**Template usage** (`website_sale_wishlist.add_to_wishlist` template):

```python
<t t-set="in_wish" t-value="product in products_in_wishlist"/>
```

This is an O(1) record membership check because both `product` and `products_in_wishlist` are `product.template` recordsets — Odoo's recordset containment check is efficient.

#### `_change_website_config(**options)` — override

```python
@route()
def _change_website_config(self, **options):
    result = super()._change_website_config(**options)
    current_website = request.env['website'].get_current_website()
    wishlist_writable_fields = {
        'wishlist_opt_products_design_classes',
        'wishlist_grid_columns',
        'wishlist_mobile_columns',
        'wishlist_gap'
    }
    wishlist_write_vals = {k: v for k, v in options.items() if k in wishlist_writable_fields}
    if wishlist_write_vals:
        current_website.write(wishlist_write_vals)
    return result
```

Intercepts website config save events from the visual builder. Filters the incoming options to only the four wishlist layout fields and writes them to the current `website` record. This allows the visual builder to persist wishlist page design changes.

---

## Security

### Record Rules — `security/website_sale_wishlist_security.xml`

```xml
<!-- Portal and logged-in users: can only see their own wishlist -->
<record id="product_wishlist_rule" model="ir.rule">
    <field name="name">See own Wishlist</field>
    <field name="model_id" ref="model_product_wishlist"/>
    <field name="domain_force">[('partner_id','=', user.partner_id.id)]</field>
    <field name="groups" eval="[(4, ref('base.group_portal')), (4, ref('base.group_user'))]"/>
</record>

<!-- Sales managers: can see all wishlists -->
<record id="all_product_wishlist_rule" model="ir.rule">
    <field name="name">See all wishlist</field>
    <field name="model_id" ref="model_product_wishlist"/>
    <field name="domain_force">[(1, '=', 1)]</field>
    <field name="groups" eval="[(4, ref('sales_team.group_sale_manager'))]"/>
</record>
```

**`product_wishlist_rule`** applies to `base.group_portal` and `base.group_user`. The domain `[('partner_id','=', user.partner_id.id)]` uses the current user's partner ID. Key security implications:
- Does **not** include `website_id` in the domain. On a multi-website Odoo instance, a portal user could potentially read wishlist records from another website if they somehow obtained a recordset for that website. The controller compensates by always adding `website_id` to the search domain.
- `partner_id = user.partner_id.id` means users without a partner record (system users, internal users without linked partners) effectively see no wishlist records.

**`all_product_wishlist_rule`** grants `sales_team.group_sale_manager` full read/write/unlink on all wishlist records across all websites. This is intentional for support and reporting workflows.

### Access Control — `security/ir.model.access.csv`

| ID | Name | Group | R | W | C | D |
|---|---|---|---|---|---|---|
| `access_product_wishlist_default` | Default | *(none)* | 0 | 0 | 0 | 0 |
| `access_product_wishlist_public` | Public | `base.group_public` | 0 | 0 | 0 | 0 |
| `access_product_wishlist_portal` | Portal | `base.group_portal` | 1 | 1 | 1 | 1 |
| `access_product_wishlist_user` | User | `base.group_user` | 1 | 1 | 1 | 1 |

**Critical detail**: `base.group_public` (anonymous) has all-zero access. All anonymous wishlist operations are routed through the `auth='public'` controller endpoints, which use `sudo()` internally. This prevents direct ORM access to `product.wishlist` from public contexts while still enabling the feature.

---

## Session Management — Dual-Layer Architecture

The module maintains two parallel storage layers for wishlist state:

| Layer | Storage | Owner | Contents |
|---|---|---|---|
| Server | `product.wishlist` records (`partner_id=False`) | Anonymous session | Full wishlist objects: price, currency, pricelist, website, product |
| Client | `sessionStorage['wishlist_product_ids']` (JS array of product variant IDs) | Browser tab | Only product variant IDs |

**On page load** (`WishlistNavbar.willStart()`):
```
1. Parse current navbar badge count from DOM
2. If sessionStorage.length !== badge count:
   → RPC /shop/wishlist/get_product_ids
   → Update sessionStorage to match server state
```
This handles multi-tab synchronization: any tab that modifies the wishlist updates the server; other tabs reconcile on their next `willStart()`.

**On add**:
```
1. Controller creates product.wishlist record
2. JS adds productId to sessionStorage locally
3. JS disables button, updates heart icon, runs animation
```

**On login**:
```
1. _check_credentials() → _check_wishlist_from_session()
2. Server migrates session records to partner
3. request.session.pop('wishlist_ids') clears session
4. Next page load → full reconciliation via /shop/wishlist/get_product_ids
```

---

## View Architecture

### Wishlist Button Injection Points

| Template | Inherits | Priority | Location |
|---|---|---|---|
| `website_sale_wishlist.add_to_wishlist` | `website_sale.shop_product_buttons` | 20 | `<t name="buttons_container">` → product grid cards |
| `website_sale_wishlist.product_add_to_wishlist` | `website_sale.cta_wrapper` | 20 | `<xpath expr="//div[@id='product_option_block']">` → product detail page |
| `website_sale_wishlist.product_cart_lines` | `website_sale.cart_lines` | default | After "Delete from cart" → cart page "Save for Later" |

### Wishlist Page Template: `website_sale_wishlist.product_wishlist`

Renders at `/shop/wishlist`. Key structural decisions:
- Uses `website.layout` as the base.
- The grid container `#o_comparelist_table` reuses the same CSS grid as the product catalog, with `o_wishlist_table` and `o_wsale_products_opt_layout_catalog` classes.
- Grid column count from `data-wishlist-grid-columns` (driven by `website.wishlist_grid_columns`) overrides the catalog defaults via SCSS.
- Empty state: animated SVG with CSS `heartBeat` and `swing` keyframe animations on the heart icon and shopping bag.
- "Add to Cart" on the wishlist page uses the new Odoo 19 `cart.add()` service (not the legacy `/shop/cart/update` RPC).
- "Remove from wishlist" triggers the `ProductWishlist` interaction's `_removeProduct()` method, which calls `/shop/wishlist/remove/{wish_id}`.

### Header Navbar Link Template: `header_wishlist_link`

Injected into all `website_sale` header variants (default, mobile, hamburger, vertical, boxed, sidebar, search, stretch, sales_one through sales_four) via template inheritance. Key expressions:
- `wishcount = len(request.env['product.wishlist'].current())` — server-side count, rendered into the page.
- `show_wishes = website.has_ecommerce_access()` — hides the wishlist entirely for users without e-commerce access.
- The badge has class `o_animate_blink` which triggers a CSS animation when the count changes.

---

## Interactions (Odoo 19 Web Ecosystem)

### `AddProductToWishlistButton` (`add_product_to_wishlist_button.js`)

Registered in `public.interactions` as `'website_sale_wishlist.add_product_to_wishlist_button'`. Selector: `.o_add_wishlist, .o_add_wishlist_dyn`.

```javascript
async addProduct(ev) {
    let productId = parseInt(el.dataset.productProductId);
    // Dynamic variant: create/find variant first
    if (!productId) {
        productId = await this.waitFor(rpc('/sale/create_product_variant', {
            product_template_id: parseInt(el.dataset.productTemplateId),
            product_template_attribute_value_ids: wSaleUtils.getSelectedAttributeValues(form),
        }));
    }
    // Prevent double-call
    if (!productId || wishlistUtils.getWishlistProductIds().includes(productId)) return;

    await this.waitFor(rpc('/shop/wishlist/add', { product_id: productId }));
    wishlistUtils.addWishlistProduct(productId);
    wishlistUtils.updateWishlistNavBar();
    wishlistUtils.updateDisabled(el, true);
    // Animate clone toward navbar heart icon
    await wSaleUtils.animateClone(
        $(document.querySelector('.o_wsale_my_wish')),
        $(document.querySelector('#product_detail_main') ?? el.closest('.o_cart_product') ?? form),
        25, 40,
    );
    // Toggle heart icon: fa-heart-o → fa-heart
    if (el.classList.contains('o_add_wishlist')) {
        const iconEl = el.querySelector('.fa');
        if (iconEl) { iconEl.classList.remove('fa-heart-o'); iconEl.classList.add('fa-heart'); }
    }
}
```

**Dynamic variant creation**: If `data-product-product-id` is absent (product page with no pre-selected variant), calls `/sale/create_product_variant` to dynamically create or find the variant matching the selected attribute values. This supports the use case where a customer configures a custom product (e.g., custom text/color) and then adds it to the wishlist before the variant exists in the database.

### `WishlistNavbar` (`wishlist_navbar.js`)

Registered as `'website_sale_wishlist.wishlist_navbar'`. Selector: `.o_wsale_my_wish`.

- `willStart()`: Fetches `/shop/wishlist/get_product_ids` on page load if the server-side count differs from the rendered badge count.
- `start()`: Calls `updateWishlistNavBar()` — updates the badge count from `sessionStorage` and toggles visibility for `o_wsale_my_wish_hide_empty`.

### `ProductWishlist` (`product_wishlist.js`)

Registered as `'website_sale_wishlist.product_wishlist'`. Selector: `.wishlist-section`.

- **Remove (`removeProduct`)**: Calls `/shop/wishlist/remove/{wish_id}`, hides the `<article>` via CSS, updates `sessionStorage`, updates navbar, updates empty-state visibility.
- **Add to Cart (`addToCart`)**: Uses `this.services['cart'].add()` — the new Odoo 19 cart service. Supports `isCombo`, `ptavs` (product template attribute values), and `showQuantity`. After adding to cart, removes from wishlist. If this was the last item, redirects to `/shop/cart`.

### `ProductDetail` (`product_detail.js`)

Registered as `'website_sale_wishlist.product_detail'`. Selector: `#product_detail`.

Listens to `input.product_id` (variant selector radio/select) change events. On variant change:
1. Reads the new `productId` from `input.value`.
2. Finds the nearest `[data-action="o_wishlist"]` button.
3. Checks `sessionStorage` for the new variant's presence.
4. Updates `disabled` state and `data-product-product-id` dataset.

---

## Website Builder Plugin — `wishlist_page_option_plugin.js`

Extends the Odoo 19 Visual Builder with three `BuilderAction` subclasses and a `product_design_list_to_save` resource.

### BuilderActions

| Class | ID | Data target | SCSS output |
|---|---|---|---|
| `WishlistGridColumnsAction` | `wishlistGridColumns` | `data-wishlist-grid-columns` | Column count via SCSS loop |
| `WishlistMobileColumnsAction` | `wishlistMobileColumns` | `data-wishlist-mobile-columns` | 1 or 2 columns on mobile |
| `WishlistSetGapAction` | `wishlistSetGap` | `--o-wsale-wishlist-grid-gap` CSS var | `gap` property on grid |

### `product_design_list_to_save`

```javascript
product_design_list_to_save: {
    selector: ".o_wishlist_table",
    getData(el) {
        const productOptClasses = Array.from(el.classList).filter(
            className => className.startsWith("o_wsale_products_opt_")
        );
        return {
            wishlist_grid_columns: parseInt(el.dataset.wishlistGridColumns) || 5,
            wishlist_mobile_columns: parseInt(el.dataset.wishlistMobileColumns) || 2,
            wishlist_gap: el.style.getPropertyValue("--o-wsale-wishlist-grid-gap") || "16px",
            wishlist_opt_products_design_classes: productOptClasses.join(" "),
        };
    },
},
```

Extracts current visual state from the DOM and maps it back to the four `website` fields when the builder saves. The visual builder thus becomes a WYSIWYG editor for wishlist page layout.

---

## SCSS Architecture — `website_sale_wishlist.scss`

Key design decisions:

**Grid reuse pattern**: The wishlist page reuses the same `o_wsale_products_opt_layout_*` CSS class system from the product catalog. The `#o_comparelist_table` element acts as the grid container. SCSS uses attribute selectors `[data-wishlist-grid-columns="N"]` to override column counts:

```scss
@include media-breakpoint-up(lg) {
    @for $i from 2 through 6 {
        &[data-wishlist-grid-columns="#{$i}"] {
            grid-template-columns: repeat(#{$i}, minmax(0, 1fr));
        }
    }
}
```

**Heart icon state via CSS content override** (not font class swap):

```scss
.o_add_wishlist_dyn {
    &.disabled i::before { content: "\f004"; } // filled heart
}
```

When the button gets `disabled` class (already in wishlist), the CSS overrides the `::before` content to show a filled heart glyph without needing to change the font-awesome class. This keeps the button DOM stable and avoids layout shifts.

**Remove button positioning**: Uses `--o-wsale-wishlist-card-offset-*` CSS variables calculated from the card's `border-radius`. This ensures the remove button (X) is always offset correctly regardless of the card's corner radius setting.

---

## Performance Considerations

1. **`current()` Python filtering**: The `.filtered()` call with `.sudo()` and two-level traversal per iteration is an N+1 read pattern for large wishlists. Consider adding a direct domain filter on `website_published` to push the filter to SQL.

2. **Garbage collection timing**: The `_gc_sessions` vacuum with a 5-week window could allow significant table bloat on high-traffic public stores. Monitor `product_wishlist` table size in relation to session traffic. The window can be shortened by setting `ir.config_parameter` for `wishlist_week` — though this parameter is not exposed in the UI.

3. **`sessionStorage` divergence**: On pages that do not load `WishlistNavbar` (e.g., pure AJAX-loaded content), the session storage can become stale. The `willStart()` reconciliation on `WishlistNavbar` compensates on subsequent full-page loads.

4. **DB unique constraint gap for anonymous users**: The `UNIQUE(product_id, partner_id)` constraint does not prevent anonymous duplicates because `NULL != NULL` in SQL. Concurrent anonymous sessions that somehow receive the same `wish_id` in their session would each add it. This is theoretical; in practice, the UI's single-click handling prevents this.

5. **`_check_wishlist_from_session()` partial failure**: If the `write({'partner_id': ...})` call partially fails (e.g., a constraint on the `website_id` write), the session is still popped. The migration would not be retryable. The session list is cleared regardless of success.

---

## Odoo 18 → Odoo 19 Changes

| Area | Odoo 18 | Odoo 19 |
|---|---|---|
| Session storage | Separate `product.wishlist.store` model (session-specific) | Unified `product.wishlist` with `partner_id=False` for anonymous; `product.wishlist.store` removed |
| Login migration | Separate page/controller route or manual flow | Automatic via `res.users._check_credentials()` hook |
| Public wishlist sharing | Supported via `/shop/wishlist/<token>` public URL | Removed — wishlist is strictly private per account |
| Cart update | `/shop/cart/update` RPC endpoint | New `cart.add()` JS service API |
| Web components | Legacy `@website_sale` QWeb/Old JS widgets | Odoo 19 `Interaction` class + `public.interactions` registry |
| Variant creation for wishlist | Pre-existing variant required | `/sale/create_product_variant` RPC fallback for dynamic variants |
| Heart animation | `$o_sale_product_page.WishlistAnimation` | `wSaleUtils.animateClone()` from `website_sale` |
| CSS grid system | Custom wishlist-specific CSS grid | Reuses `o_wsale_products_opt_*` classes from `website_sale` catalog |
| Design customization | Theme-based or static CSS | Per-website fields + visual builder plugin |
| `res.partner` O2M | Not present | Added for convenience access |

---

## Integration with Other Modules

- **[Modules/website_sale](Modules/website_sale.md)**: Full dependency. `website_sale` provides the product catalog (`shop_product_buttons`, `products_item`, `cart_lines`), pricelist infrastructure, and checkout flow. Wishlist is purely an enhancement layer.
- **`website`**: Extended with `wishlist_opt_products_design_classes`, `wishlist_grid_columns`, `wishlist_mobile_columns`, `wishlist_gap`. The controller uses `request.website` for all context.
- **`product.product` / `product.template`**: Extended with `_is_in_wishlist()` for variant-level and template-level membership checks.
- **`res.partner`**: O2M reverse via `wishlist_ids` for partner-level wishlist access.
- **`res.users`**: Login hook in `_check_credentials()` triggers automatic session migration.
- **`sale.product.template.attribute.value`**: Wishlist add button handles dynamic variant creation via `/sale/create_product_variant` for custom attribute combinations not yet materialized as variants.
