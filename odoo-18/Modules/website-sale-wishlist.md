---
Module: website_sale_wishlist
Version: Odoo 18
Type: Extension
Tags: #odoo18, #e-commerce, #wishlist, #website, #session
Related Modules: [website_sale](Modules/website-sale.md), [product](Modules/product.md), [res_partner](Modules/res-partner.md)
---

# website_sale_wishlist — Product Wishlist

**Addon path:** `~/odoo/odoo18/odoo/addons/website_sale_wishlist/`
**Module key:** `website_sale_wishlist`
**Depends on:** `website_sale`
**Summary:** Allow shoppers to save products to personalized wishlists for future purchase.

---

## Architecture Overview

```
website_sale_wishlist
  ├── models/
  │     ├── product_wishlist.py    ← product.wishlist, res.partner extensions
  │     └── res_users.py           ← res.users: session→partner sync on login
  └── controllers/
        └── main.py                ← JSON routes: add, remove, list wishlist
```

**Key concept:** Wishlists are stored as database records in `product.wishlist`. Anonymous (public) users get wishlist entries stored without a `partner_id`, with IDs saved in `request.session['wishlist_ids']`. On login, session wishlists are merged into the partner's wishlist.

---

## Models

### `product.wishlist` (Core Model)

**Module:** `website_sale_wishlist` | **Inherits:** `base.model`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `partner_id` | `Many2one(res.partner)` | Owner of the wishlist entry. `False` for anonymous/session wishlists. |
| `product_id` | `Many2one(product.product)` | The product variant being wished for. Required. |
| `currency_id` | `Many2one(res.currency)` | Related to `website_id.currency_id` (readonly). Stored at time of adding. |
| `pricelist_id` | `Many2one(product.pricelist)` | Pricelist active when item was added. Used to display original price. |
| `price` | `Monetary` | Price of the product when it was added to the wishlist. |
| `website_id` | `Many2one(website)` | The website where the wishlist entry was created. `ondelete='cascade'`, required. |
| `active` | `Boolean` | Soft-delete flag. `default=True`, required. Allows "removing" without DB deletion. |

#### SQL Constraints

```python
('product_unique_partner_id', 'UNIQUE(product_id, partner_id)',
 'Duplicated wishlisted product for this partner.')
```

> **Constraint note:** The unique constraint is only on `(product_id, partner_id)`. Session wishlists (where `partner_id=False`) are NOT subject to this constraint at the DB level — multiple session wishlist entries can exist for the same product. However, the application code prevents duplicates through the `_add_to_wishlist()` method logic.

#### Key Methods

**`current()` — Get current user's wishlist**

```python
@api.model
def current(self):
    if not request:
        return self

    if request.website.is_public_user():
        # Anonymous: read from session
        wish = self.sudo().search([
            ('id', 'in', request.session.get('wishlist_ids', []))
        ])
    else:
        # Logged in: read from partner
        wish = self.search([
            ("partner_id", "=", self.env.user.partner_id.id),
            ('website_id', '=', request.website.id)
        ])

    return wish.filtered(
        lambda wish:
            wish.sudo().product_id.product_tmpl_id.website_published
            and wish.sudo().product_id.product_tmpl_id._can_be_added_to_cart()
    )
```

**Logic:**
- Public user: reads wishlist IDs from `request.session['wishlist_ids']`, then loads actual records
- Logged-in user: queries by `partner_id = current_user.partner_id.id` AND `website_id = current_website`
- Results are filtered to only include **published** products that are **addable to cart**
- Returns a filtered recordset (never creates new records)

**`_add_to_wishlist(pricelist_id, currency_id, website_id, price, product_id, partner_id=False)`**

```python
@api.model
def _add_to_wishlist(self, pricelist_id, currency_id, website_id, price, product_id, partner_id=False):
    wish = self.env['product.wishlist'].create({
        'partner_id': partner_id,      # False for anonymous
        'product_id': product_id,
        'currency_id': currency_id,
        'pricelist_id': pricelist_id,
        'price': price,               # Current price at time of adding
        'website_id': website_id,
    })
    return wish
```

- Creates a new `product.wishishlist` record
- If `partner_id=False`: called for anonymous session wishlists
- Does **not** check for duplicates — caller (`add_to_wishlist` controller) must handle

**`_check_wishlist_from_session()` — Merge session wishlist into partner wishlist on login**

```python
@api.model
def _check_wishlist_from_session(self):
    # Get all session wishlist entries
    session_wishes = self.sudo().search([
        ('id', 'in', request.session.get('wishlist_ids', []))
    ])
    # Get all partner wishlist entries
    partner_wishes = self.sudo().search([
        ("partner_id", "=", self.env.user.partner_id.id)
    ])
    partner_products = partner_wishes.mapped("product_id")

    # Remove session products already in partner wishlist
    duplicated_wishes = session_wishes.filtered(
        lambda wish: wish.product_id <= partner_products
    )
    session_wishes -= duplicated_wishes
    duplicated_wishes.unlink()  # Remove true duplicates

    # Assign remaining session wishlists to the partner
    session_wishes.write({"partner_id": self.env.user.partner_id.id})
    request.session.pop('wishlist_ids')  # Clear session
```

**Steps on login:**
1. Find session wishlists from `request.session['wishlist_ids']`
2. Find partner's existing wishlists
3. Remove session entries for products already in partner's wishlist
4. Assign remaining session entries to the partner
5. Clear `wishlist_ids` from session

**`_gc_sessions(*args, **kwargs)` — Garbage collection**

```python
@api.autovacuum
def _gc_sessions(self, *args, **kwargs):
    self.with_context(active_test=False).search([
        ("create_date", "<", fields.Datetime.to_string(
            datetime.now() - timedelta(weeks=kwargs.get('wishlist_week', 5))
        )),
        ("partner_id", "=", False),  # Only session wishlists
    ]).unlink()
```

- Runs as a vacuum job (cron)
- Deletes anonymous wishlists older than 5 weeks by default
- Uses `active_test=False` to include soft-deleted entries

---

### `res.partner` (Extended)

**Module:** `website_sale_wishlist` | **Inherits:** `res.partner`

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `wishlist_ids` | `One2many(product.wishlist)` | All wishlist entries for this partner. `domain=[('active', '=', True)]` |

```python
wishlist_ids = fields.One2many(
    'product.wishlist', 'partner_id',
    string='Wishlist',
    domain=[('active', '=', True)]
)
```

> **Note:** This is a reverse One2many from `product.wishlist.partner_id`. It only shows active wishlist entries (`active=True`). Inactive entries (soft-deleted) are hidden.

#### Computed `wishlist_count`

The `wishlist_count` field is **not defined in `website_sale_wishlist`** — it is computed in `sale` or `website_sale` as a related/computed field on `res.partner`. The `wishlist_ids` One2many provides the underlying data.

---

### `res.users` (Extended)

**Module:** `website_sale_wishlist` | **Inherits:** `res.users`

#### Method Overridden

**`_check_credentials(self, credential, env)`**

```python
def _check_credentials(self, credential, env):
    """Make all wishlists from session belong to its owner user."""
    result = super()._check_credentials(credential, env)
    if request and request.session.get('wishlist_ids'):
        self.env["product.wishlist"]._check_wishlist_from_session()
    return result
```

**Trigger:** Called during login (`auth_login`) when user credentials are verified.

**Purpose:** When a user logs in, any wishlist items stored in the session are transferred to their partner record.

> This hook works because `auth_login` eventually calls `res.users.write({'login_date': now})` which triggers `_check_credentials`. The key condition is `request and request.session.get('wishlist_ids')` — if the session has wishlist IDs, the merge runs.

---

### `product.product` (Extended)

**Module:** `website_sale_wishlist` | **Inherits:** `product.product`

#### Methods Added

**`_is_in_wishlist()`**

```python
def _is_in_wishlist(self):
    self.ensure_one()
    return self in self.env['product.wishlist'].current().mapped('product_id')
```

- Returns `True` if the current product variant is in the current user's wishlist
- Calls `product.wishlist.current()` — handles session vs. partner automatically
- Used in templates to show/hide "Add to Wishlist" button vs. "Already in Wishlist"

---

### `product.template` (Extended)

**Module:** `website_sale_wishlist` | **Inherits:** `product.template`

#### Methods Added

**`_is_in_wishlist()`**

```python
def _is_in_wishlist(self):
    self.ensure_one()
    return self in self.env['product.wishlist'].current().mapped('product_id.product_tmpl_id')
```

- Returns `True` if any variant of this template is in the wishlist
- Maps wishlist `product_id` records to their `product_tmpl_id`
- Used on listing pages where individual variants may not be shown

---

## Wishlist Storage: Session vs. Partner — L4 Analysis

### Anonymous User (Public)

```
request.session['wishlist_ids'] = [wishlist_id_1, wishlist_id_2, ...]
product.wishlist.partner_id = False
```

- Wishlist entries created without `partner_id`
- IDs stored in the session (server-side session, not just browser cookie)
- Session is tied to the browser via `request.session` (secured by session salt)
- On page load: `product.wishlist.current()` reads IDs from session, loads records via sudo

### Logged-In User

```
product.wishlist.partner_id = request.env.user.partner_id.id
request.session['wishlist_ids'] = [] (cleared after login)
```

- Wishlist entries are permanently associated with the partner record
- Queried directly from DB via `partner_id = current_partner_id`
- Visible on any device/session where the user logs in

### Session-to-Partner Sync on Login

```
1. User browses as public → adds items to wishlist
   → wishlist_ids stored in session

2. User clicks "Sign In" → _check_credentials() fires

3. _check_wishlist_from_session():
   a. Load session wishlist records
   b. Load partner wishlist records
   c. Remove session entries where product already in partner list
   d. Assign remaining session entries → partner_id = user.partner_id.id
   e. Clear session wishlist_ids

4. User is now logged in with their wishlist items preserved
```

**Conflict resolution:** If a product exists in both session and partner wishlists, the session entry is deleted (unlinked), keeping only the partner entry.

**No auto-sync on logout:** If a user logs out, their partner wishlist remains. The next anonymous session will start fresh.

---

## Wishlist vs. Compare List — L4

| Aspect | Wishlist | Compare List |
|--------|----------|--------------|
| Module | `website_sale_wishlist` | `website_sale_comparison` |
| Purpose | Save for later purchase | Side-by-side product comparison |
| Storage model | `product.wishlist` record per item | `product.product` IDs in session |
| Partner-linked | Yes (on login) | No (session-only) |
| Price tracking | Yes (stores price at time of adding) | No |
| Multi-website | Yes (per `website_id`) | No |
| Garbage collection | Yes (`_gc_sessions`, 5 weeks) | No |

The wishlist stores more metadata than the compare list (price, pricelist, website), enabling future features like "price drop alert" when `price < wishlist.price`.

---

## Controller Routes

### `POST /shop/wishlist/add`

```python
@route('/shop/wishlist/add', type='json', auth='public', website=True)
def add_to_wishlist(self, product_id, **kw):
    website = request.website
    pricelist = website.pricelist_id
    product = request.env['product.product'].browse(product_id)
    price = product._get_combination_info_variant()['price']

    Wishlist = request.env['product.wishlist']
    if request.website.is_public_user():
        Wishlist = Wishlist.sudo()
        partner_id = False
    else:
        partner_id = request.env.user.partner_id.id

    wish = Wishlist._add_to_wishlist(
        pricelist.id, pricelist.currency_id.id,
        request.website.id, price, product_id, partner_id
    )

    if not partner_id:
        # Anonymous: store ID in session
        request.session['wishlist_ids'] = request.session.get('wishlist_ids', []) + [wish.id]

    return wish
```

### `GET /shop/wishlist`

Returns rendered `website_sale_wishlist.product_wishlist` template with all current wishlist items.

### `DELETE /shop/wishlist/remove/<wish_id>`

```python
@route('/shop/wishlist/remove/<int:wish_id>', type='json', auth='public', website=True)
def remove_from_wishlist(self, wish_id, **kw):
    wish = request.env['product.wishlist'].browse(wish_id)
    if request.website.is_public_user():
        wish_ids = request.session.get('wishlist_ids') or []
        if wish_id in wish_ids:
            request.session['wishlist_ids'].remove(wish_id)
            request.session.touch()
            wish.sudo().unlink()  # Hard delete (no active flag)
    else:
        wish.unlink()  # Hard delete
    return True
```

---

## Security Model

- Anonymous users: wishlist records are accessed via `sudo()` to bypass record rules
- The SQL unique constraint on `(product_id, partner_id)` prevents a single partner from adding the same product twice
- For anonymous users: the session-based ID list prevents duplicate additions at the application level

---

## Key Takeaways

1. **`product.wishlist`** is the core model — stores partner_id, product_id, website_id, price snapshot, and active flag
2. **Session wishlists** for anonymous users: IDs stored in `request.session['wishlist_ids']`, records have `partner_id=False`
3. **Login sync** happens via `res.users._check_credentials()` → `_check_wishlist_from_session()` — merges session items into partner wishlist, deduplicates
4. **`wishlist_count`** is derived from the `wishlist_ids` One2many on `res.partner`
5. **Price snapshot** (`price` field) stores the price at time of adding — useful for "price dropped" alerts
6. **Garbage collection** via `_gc_sessions()` autovacuum deletes anonymous wishlists older than 5 weeks
7. **Product visibility filter** in `current()` automatically hides unpublished products from wishlist views
