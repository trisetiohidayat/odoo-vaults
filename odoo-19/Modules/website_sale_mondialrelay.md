---
tags:
  - odoo
  - odoo19
  - modules
  - website_sale
  - delivery
  - mondial_relay
---

# website_sale_mondialrelay

> eCommerce Mondial Relay Delivery — allows customers to select a Point Relais pickup point as their shipping address on the eCommerce storefront.

**Module:** `website_sale_mondialrelay`
**Category:** `Website/Website`
**Depends:** `website_sale`, `delivery_mondialrelay`
**License:** LGPL-3
**Auto-install:** `True`
**Author:** Odoo S.A.

---

## L1: Core Functionality — How Customers Select a Point Relais at Checkout

`website_sale_mondialrelay` bridges the website checkout flow (`website_sale`) with the Mondial Relay carrier integration (`delivery_mondialrelay`). It enables two critical user-facing flows on the eCommerce portal:

1. **Selecting a Point Relais** as the shipping address during checkout via a JS widget that calls a JSON-RPC endpoint.
2. **Rendering the selected pickup point** on the order confirmation and summary screens.

It does **not** implement the Mondial Relay WebService — that is handled by `delivery_mondialrelay`. This module handles only the web/UI layer and the `sale.order` ORM guardrails.

**End-to-end checkout flow:**

```
1. Customer selects "Mondial Relay" carrier at checkout
   → JS widget detects data-is-mondialrelay=True on the carrier radio input
   → Widget opens, customer searches and selects a Point Relais
   ────────────────────────────────────────────
2. JSON-RPC: /website_sale_mondialrelay/update_shipping
   → Server creates/resolves res.partner contact (ref='MR#FR007840')
   → sale.order.partner_shipping_id = that partner
   → Returns re-rendered address snippet
   ────────────────────────────────────────────
3. Customer clicks "Proceed to Payment"
   → sale.order._check_cart_is_ready_to_be_paid()
   → Validates: Point Relais address ←→ MR carrier must coexist
   ────────────────────────────────────────────
4. Order confirmed
   → delivery_mondialrelay/action_confirm validates same invariant
   → stock.picking created with MR tracking link
```

---

## L2: Field Types, Defaults, Constraints

### `delivery.carrier` — Fields from `delivery_mondialrelay`

| Field | Type | Default | Access | Notes |
|-------|------|---------|--------|-------|
| `is_mondialrelay` | Boolean (computed, searchable) | `product_id.default_code == 'MR'` | All | Detection by product code convention |
| `mondialrelay_brand` | Char | `'BDTEST  '` (8 chars, trailing spaces) | `base.group_system` | MR-assigned brand code |
| `mondialrelay_packagetype` | Char | `"24R"` (standard parcel) | `base.group_system` | `24R`/`24L`/`24X` |

**`is_mondialrelay` compute:**
```python
@api.depends('product_id.default_code')
def _compute_is_mondialrelay(self):
    for c in self:
        c.is_mondialrelay = c.product_id.default_code == "MR"

def _search_is_mondialrelay(self, operator, value):
    if operator != 'in':
        return NotImplemented
    return [('product_id.default_code', '=', 'MR')]
```

**Why not a stored Boolean?** The compute depends on `product_id.default_code`, which is editable. A stored computed Boolean would require an `onchange` to recompute when the product changes. The unstored compute with searchable support is the pattern used throughout Odoo's delivery modules.

### `res.partner` — Fields from `delivery_mondialrelay`

| Field | Type | Detection | Notes |
|-------|------|-----------|-------|
| `is_mondialrelay` | Boolean | `ref and ref.startswith('MR#')` | Computed from `ref` — no extra column needed |

**Why `ref.startswith('MR#')`?** The `ref` field serves as a stable relay identifier. Format: `MR#<relay_id>` (e.g., `MR#FR007840`). This avoids adding a dedicated Boolean column and enables deduplication in `_mondialrelay_search_or_create`.

### `sale.order` — Extended by `website_sale_mondialrelay`

| Method | Role | Key Fields |
|--------|------|-----------|
| `_check_cart_is_ready_to_be_paid()` | Payment gate guard | `partner_shipping_id.is_mondialrelay`, `carrier_id.is_mondialrelay`, `delivery_set` |
| `_compute_partner_shipping_id()` | Silent address reset on carrier switch | `partner_id`, `carrier_id` |

### `choose.delivery.carrier` — Backend wizard (from `delivery_mondialrelay`)

| Field | Type | Notes |
|-------|------|-------|
| `is_mondialrelay` | Boolean (computed) | Controls widget visibility |
| `mondialrelay_last_selected` | Char | JSON string of selected relay data |
| `mondialrelay_last_selected_id` | Char (computed) | Format: `"CC-REF"` |
| `mondialrelay_brand` | Char (related) | Passed to JS widget |
| `mondialrelay_colLivMod` | Char (related) | Passed to JS widget |
| `mondialrelay_allowed_countries` | Char (computed) | Comma-joined country codes |
| `shipping_zip` | Char (related) | Widget initial search parameter |

---

## L3: Cross-Model Relationships, Override Patterns, Workflow Triggers

### Module Dependency Chain

```
stock_delivery
    └── delivery_mondialrelay       # carrier backend, res.partner extensions, pick/wizard
            └── website_sale_mondialrelay  # checkout UI, sale.order guards
                    └── website_sale        # eCommerce controllers, delivery method templates
```

### Cross-Model Call Chain

```
MondialRelay.update_shipping (JSON-RPC)
    → request.cart (website_sale controller mixin)
    → _mondialrelay_search_or_create()  [delivery_mondialrelay/res_partner.py]
        → creates res.partner (ref='MR#...', parent_id=customer, type='delivery')
    → sale.order.partner_shipping_id = that partner
    → ir.qweb._render('website_sale.address_on_checkout', {...})

sale.order._check_cart_is_ready_to_be_paid()
    → Validates carrier/address consistency
    → Raises ValidationError if mismatch

sale.order._compute_partner_shipping_id()
    → super() runs website_sale standard logic
    → Resets shipping to partner_id if MR→non-MR carrier switch

WebsiteSaleMondialrelay._prepare_address_update()
    → Blocks editing of MR partner via address form

WebsiteSaleMondialrelay._check_delivery_address()
    → Skips address validation for MR partners

WebsiteSaleDeliveryMondialrelay._order_summary_values()
    → Injects MR-specific fields into order summary JSON
    → Consumed by JS widget for widget initialization

choose.delivery.carrier.button_confirm() [backend wizard]
    → Mirrors update_shipping logic for backend sales orders
```

### `_mondialrelay_search_or_create()` — `@api.model`

```python
@api.model
def _mondialrelay_search_or_create(self, data):
    ref = 'MR#%s' % data['id']  # e.g., 'MR#FR007840'
    partner = self.search([
        ('id', 'child_of', self.commercial_partner_id.ids),
        ('ref', '=', ref),
        ('street', '=', data['street']),
        ('zip', '=', data['zip']),
    ])
    if not partner:
        partner = self.create({
            'ref': ref, 'name': data['name'],
            'street': data['street'], 'street2': data.get('street2'),
            'zip': data['zip'], 'city': data['city'],
            'country_id': self.env.ref('base.%s' % data['country_code'][:2].lower()).id,
            'type': 'delivery', 'parent_id': self.id,
        })
    return partner
```

**Deduplication key:** Three fields (`ref`, `street`, `zip`) must all match. A relay that relocates creates a new contact — the old contact is abandoned but harmless.

**Scope:** `child_of commercial_partner_id` searches the entire commercial partner subtree. This handles multi-address customer hierarchies.

**Country resolution:** `data['country_code']` is lowercased 2-letter ISO prefix. `base.fr`, `base.be`, etc. exist in Odoo's base data for all countries.

### `_check_cart_is_ready_to_be_paid()` — Decision Table

| `partner_shipping_id.is_mondialrelay` | `delivery_set` | `carrier_id.is_mondialrelay` | Result |
|---|---|---|---|
| `True` | `True` | `False` / null | `ValidationError`: "Point Relais can only be used with the delivery method Mondial Relay." |
| `False` | any | `True` | `ValidationError`: "Delivery method Mondial Relay can only ship to Point Relais." |
| `False` | `False` | `False` | Falls through to `super()` |
| `True` | `True` | `True` | Falls through to `super()` |
| `True` | `False` | any | Falls through to `super()` (no delivery line yet) |

**Why `delivery_set` gates the first branch:** Without this check, the first branch would fire whenever a Point Relais address was active and no carrier had been set yet. The `delivery_set` flag ensures the guard only fires after a delivery line has been added to the cart.

### `_compute_partner_shipping_id()` — Silent Reset Flow

```python
def _compute_partner_shipping_id(self):
    super()._compute_partner_shipping_id()  # website_sale default: shipping=billing
    for order in self.filtered('website_id'):
        if order.partner_shipping_id.is_mondialrelay and not order.carrier_id.is_mondialrelay:
            order.partner_shipping_id = order.partner_id  # Silent reset to billing address
```

Triggered whenever `partner_shipping_id` or `carrier_id` changes. Filters to `website_id` presence — backend orders are unaffected.

### Override Patterns

| Location | Pattern | Purpose |
|----------|---------|---------|
| `sale.order` | Classical `_inherit` | Two method overrides |
| `http.Controller` | Mixin class `MondialRelay` | Standalone JSON-RPC |
| `WebsiteSale` | Mixin `WebsiteSaleMondialrelay` | Address form hooks |
| `Delivery` (website_sale) | Mixin `WebsiteSaleDeliveryMondialrelay` | Order summary injection |
| QWeb templates | `xpath` inherits | UI attribute injection |

### Workflow Triggers

| Trigger | Action | Description |
|---------|--------|-------------|
| Customer selects MR carrier in checkout JS | Widget fires `/update_shipping` | Creates/resolves MR partner |
| Customer clicks "Proceed to Payment" | `_check_cart_is_ready_to_be_paid()` | Validates carrier/address match |
| Carrier changes to/from MR | `_compute_partner_shipping_id()` | Silent reset or allow |
| Order confirmed | `delivery_mondialrelay/action_confirm` | Second carrier/address validation |
| Backend `button_confirm` on wizard | `choose.delivery.carrier/button_confirm` | Backend equivalent of update_shipping |

### QWeb Template Overrides

Four templates inherited via xpath, spread across `templates.xml` and `delivery_form_templates.xml`:

| Template | Parent | What it adds |
|----------|--------|-------------|
| `mondialrelay_delivery_method` | `website_sale.delivery_method` | `data-is-mondialrelay` attribute on carrier radio input |
| `website_sale_mondialrelay_billing_address_list` | `website_sale.billing_address_list` | Tooltip disabling "billing = delivery" for MR |
| `website_sale_mondialrelay_address_card` | `website_sale.address_card` | `data-is-mondialrelay` on address div |
| `address_on_checkout` | `website_sale.address_on_checkout` | MR logo + address text for selected relay |

---

## L4: Version Odoo 18→19 Changes, Security Analysis, Edge Cases

### Version Odoo 18 → Odoo 19 Changes

**No behavioral changes** to `website_sale_mondialrelay` between Odoo 18 and Odoo 19. The module's structure is stable:

- The `is_mondialrelay` detection mechanism (`product_id.default_code == 'MR'`) is unchanged
- The `ref.startswith('MR#')` pattern on `res.partner` is unchanged
- The `mondialrelay_brand` default `'BDTEST  '` (8 characters, trailing spaces) remains — this is a test/example brand code; production deployments must update this to their actual MR-assigned brand code
- `auto_install: True` behavior is unchanged
- The `_compute_partner_shipping_id` silent reset behavior is unchanged

Potential change in Odoo 19 **framework** that affects this module: the `website_sale` checkout flow may have changed its address management JavaScript, which would affect the JS widget integration. No specific breaking changes were identified in the module's controller overrides.

### Security Analysis

| Area | Detail | Risk Level |
|------|--------|------------|
| **Public JSON-RPC** | `/website_sale_mondialrelay/update_shipping` is `auth="public"` | Low — gated by `_is_anonymous_cart()` |
| **Anonymous cart gate** | Raises `AccessDenied` for anonymous carts | Low — prevents anonymous child contact creation |
| **sudo on partner** | `partner_id.sudo()._mondialrelay_search_or_create()` | Low — relay contact is scoped to commercial partner subtree |
| **Country restriction** | `assert` check on server-side | Low — primary enforcement is in JS widget |
| **Field-level ACL** | `mondialrelay_packagetype` restricted to `base.group_system` | Low — portal users cannot modify package type |
| **Address edit prevention** | `_prepare_address_update` + `_check_delivery_address` | Low — customers cannot modify relay data |
| **No outbound HTTP** | Module makes no outbound WebService calls | Low — WebService handled by `delivery_mondialrelay` |

**Why `auth="public"` without strong CSRF protection?** The route is designed to be called by unauthenticated website visitors during checkout (before login). Odoo's CSRF is automatically disabled for `website=True` routes. The `_is_anonymous_cart()` check ensures only users with a real cart (even if not logged in, they have a `sale.order` record) can update shipping.

**Race condition — concurrent relay selection:**
```
Cart has partner_shipping_id = A
Tab 1: selects relay FR007840 → partner_shipping_id = MR#FR007840
Tab 2: selects relay BE001122 → partner_shipping_id = MR#BE001122
Result: last write wins — normal for eCommerce checkout
```

### `_mondialrelay_search_or_create` Race Condition Analysis

In the normal case (relay already selected once): only a 3-clause `search()` runs — cheap with indexed `ref` and `zip`.

On first selection: one `create()` runs.

**Concurrent first selection (same relay):**
- Both `search()`es return empty simultaneously
- Both attempt `create()`
- First succeeds; second gets a unique constraint violation on `ref` (if `ref` is unique-per-commercial-partner) or creates a duplicate (if not)
- If a duplicate is created: the next call finds one via `search()` — not harmful, just potentially wasteful

**Production recommendation:** Add a unique constraint `unique(parent_id, ref)` on `res.partner` to prevent duplicate relay contacts:
```python
# In delivery_mondialrelay data file
from odoo.tools import file_open
# Or via SQL migration
```

### Edge Cases — Complete Reference

1. **User switches carrier MR → non-MR after selecting pickup point**
   `_compute_partner_shipping_id()` silently resets shipping to `partner_id`. The previously selected pickup point is abandoned. No notification shown — by design.

2. **Pickup point moves between selection and payment**
   `_mondialrelay_search_or_create` checks `ref + street + zip`. If the relay relocated, a new contact is created. The old contact persists but is never re-selected because its `ref` (the old relay ID) is stale.

3. **Carrier has no country restrictions (`country_ids` empty)**
   `if order_sudo.carrier_id.country_ids:` is falsy — entire country validation block skipped. Widget shows all available relay points.

4. **Anonymous cart**
   `AccessDenied` raised on `update_shipping`. User must be logged in to select a pickup point. This prevents public users from creating child contacts.

5. **Customer has no `phone` on partner record**
   `phone` passed to `_mondialrelay_search_or_create` will be `False`. Created relay contact has no phone. Not breaking — `phone` is optional.

6. **Multiple orders with the same relay**
   Each `sale.order` re-uses the same `res.partner` contact. `write_date` is updated by the most recent order's RPC call — harmless.

7. **`carrier_id` is `False` (not yet set)**
   `False.is_mondialrelay` evaluates to `False` without raising. Neither branch of `_check_cart_is_ready_to_be_paid` fires. Safe to proceed without a carrier selected.

8. **`Pays` field with locale suffix (e.g., `"ES-ct"`)**
   Only the first 2 characters (`"ES"`) are used for country resolution. The suffix (Catalonia) is discarded — correct behavior since MR's country-level support doesn't distinguish subnational regions.

9. **`partner_id` is a company (`is_company=True`)**
   Reset writes the company's main address (not a specific contact). The MR relay is still a child of the company.

10. **Concurrent cart edits from two browser tabs**
    Last write wins — standard eCommerce checkout pattern. No row-level locking in `update_shipping`.

---

## Related Files

- `/Users/tri-mac/odoo/odoo19/odoo/addons/website_sale_mondialrelay/__manifest__.py`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/website_sale_mondialrelay/models/sale_order.py`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/website_sale_mondialrelay/controllers/controllers.py`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/website_sale_mondialrelay/views/templates.xml`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/website_sale_mondialrelay/views/delivery_form_templates.xml`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/website_sale_mondialrelay/views/delivery_carrier_views.xml`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/delivery_mondialrelay/models/delivery_carrier.py` — `is_mondialrelay`, `mondialrelay_brand`, `mondialrelay_packagetype`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/delivery_mondialrelay/models/res_partner.py` — `is_mondialrelay`, `_mondialrelay_search_or_create`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/delivery_mondialrelay/models/sale_order.py` — `action_confirm` mismatch guard
- `/Users/tri-mac/odoo/odoo19/odoo/addons/delivery_mondialrelay/wizard/choose_delivery_carrier.py` — backend wizard
- `/Users/tri-mac/odoo/odoo19/odoo/addons/delivery/wizard/choose_delivery_carrier.py` — base transient wizard

---

## See Also

- [Modules/delivery_mondialrelay](modules/delivery_mondialrelay.md) — Carrier backend: `is_mondialrelay` detection, `res.partner` relay contacts, `action_confirm` guard, backend wizard
- [Modules/website_sale](modules/website_sale.md) — eCommerce base: `WebsiteSale` controller, `Delivery` mixin, `address_on_checkout` template
- [Modules/delivery](modules/delivery.md) — Delivery method base: `choose.delivery.carrier` transient wizard, delivery rate computation
- [Modules/stock_delivery](modules/stock_delivery.md) — Stock delivery integration: `stock.picking` generation from `sale.order`
