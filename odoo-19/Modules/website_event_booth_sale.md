---
tags: [odoo, odoo19, module, website, event, booth, e-commerce, sale, website_sale]
description: L4 documentation for website_event_booth_sale — e-commerce cart integration for paid event booth reservations
---

# website_event_booth_sale

> Online Event Booth Sale — Sells event exhibition booths through the Odoo e-commerce website with full payment integration. Bridges `event_booth_sale` with `website_sale` to route booth reservations through the standard Odoo checkout and payment flow. Free booths (zero price) are confirmed immediately without redirecting to payment.

---

## Module Overview

| Attribute | Value |
|---|---|
| **Category** | Marketing/Events |
| **Version** | 1.0 |
| **Depends** | `event_booth_sale`, `website_event_booth`, `website_sale` |
| **Auto-install** | `True` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

**Path:** `odoo/addons/website_event_booth_sale/`

**Dependency chain** (bottom to top):

```
website_event_booth_sale
├── website_event_booth     → website_event + event_booth
│   ├── website_event       → event
│   │   └── event
│   └── event_booth        → event
│       └── event
├── event_booth_sale       → event_booth + sale + event_sale
│   ├── event_booth        → event
│   ├── sale               → product, partner
│   └── event_sale        → event + sale
└── website_sale           → sale + website
    └── sale
```

**Purpose:** This module does not define new data models. Its three roles are:
1. **Override the booth registration confirmation flow** to route through the e-commerce cart instead of directly confirming booths
2. **Add a "has_payment_step" context** to the registration pages to show/hide the payment step
3. **Extend `sale.order.line` and `sale.order`** to handle booth-specific cart operations

---

## L1: Models, Fields, and Methods

### `product.template` — Extended

**File:** `models/product_template.py`

```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def _get_product_types_allow_zero_price(self):
        return super()._get_product_types_allow_zero_price() + ["event_booth"]
```

**What it does:** Adds `"event_booth"` to the list of product types that are allowed to have a zero sale price without triggering the standard Odoo warning. Booth categories can be set to free (price = 0), and this extension ensures the product passes the zero-price validation during cart operations.

**Inheritance:** This method extends the parent `sale` module's `_get_product_types_allow_zero_price` which originally only allows `"service"` to have zero price in certain contexts.

---

### `sale.order` — Extended

**File:** `models/sale_order.py`

#### `_cart_find_product_line(*args, event_booth_pending_ids=None, **kwargs)`

```python
def _cart_find_product_line(self, *args, event_booth_pending_ids=None, **kwargs):
    lines = super()._cart_find_product_line(
        *args, event_booth_pending_ids=event_booth_pending_ids, **kwargs,
    )
    if not event_booth_pending_ids:
        return lines
    return lines.filtered(
        lambda line: any(booth.id in event_booth_pending_ids for booth in line.event_booth_pending_ids)
    )
```

**Purpose:** When adding booths to the cart, this override ensures that if the same booth is already in the cart (on any existing line), that line is returned — not a new line. This prevents duplicate cart lines for the same booth.

**Without this override:** If `_cart_add` is called twice for the same booth, Odoo's standard `_cart_find_product_line` would not find the existing line (because it matches by `product_id` only), creating two cart lines for the same booth.

**With this override:** The existing line containing the booth is found and returned, allowing `_cart_add` to update the existing line instead of creating a new one.

#### `_verify_updated_quantity(order_line, product_id, new_qty, uom_id, **kwargs)`

```python
def _verify_updated_quantity(self, order_line, product_id, new_qty, uom_id, **kwargs):
    product = self.env['product.product'].browse(product_id)
    if product.service_tracking == 'event_booth' and new_qty > 1:
        return 1, _('You cannot manually change the quantity of an Event Booth product.')
    return super()._verify_updated_quantity(order_line, product_id, new_qty, uom_id, **kwargs)
```

**Purpose:** Enforces that event booth cart lines can never have `quantity > 1`. Booths are sold one at a time — each booth is a separate line item. Attempting to set quantity to 2 or more returns an error with quantity forced back to 1.

**This is a cart-level guard only.** The `event_booth_sale` module has additional validation in `sale.order.line._update_event_booths()` that checks booth availability when confirming the order.

#### `_prepare_order_line_values(*args, event_booth_pending_ids=False, registration_values=None, **kwargs)`

```python
def _prepare_order_line_values(self, *args, event_booth_pending_ids=False,
                               registration_values=None, **kwargs):
    values = super()._prepare_order_line_values(
        *args,
        event_booth_pending_ids=event_booth_pending_ids,
        registration_values=registration_values,
        **kwargs,
    )
    if not event_booth_pending_ids:
        return values
    booths = self.env['event.booth'].browse(event_booth_pending_ids)
    values['event_id'] = booths.event_id.id
    values['event_booth_registration_ids'] = [
        Command.create({
            'event_booth_id': booth.id,
            **registration_values,
        }) for booth in booths
    ]
    return values
```

**Purpose:** When a cart line is created for booths, this method:
1. Sets `event_id` on the SO line to the event the booths belong to
2. Creates `event.booth.registration` records for each selected booth, linking the booth to the SO line

The SO line acts as a container for booth registrations. Multiple booths can be on one SO line (e.g., a visitor books Booth A3 and Booth A4 in one transaction).

#### `_prepare_order_line_update_values(order_line, quantity, *, event_booth_pending_ids=False, registration_values=None, **kwargs)`

```python
def _prepare_order_line_update_values(self, order_line, quantity, **kwargs):
    values = super()._prepare_order_line_update_values(order_line, quantity, **kwargs)
    if not event_booth_pending_ids:
        return values
    booths = self.env['event.booth'].browse(event_booth_pending_ids)
    values['event_booth_registration_ids'] = [
        Command.delete(registration.id)
        for registration in order_line.event_booth_registration_ids
    ] + [
        Command.create({
            'event_booth_id': booth.id,
            **registration_values,
        }) for booth in booths
    ]
    return values
```

**Purpose:** When the cart is updated (e.g., user changes booth selection), this method:
1. Deletes all existing `event.booth.registration` records for the SO line
2. Creates new `event.booth.registration` records for the updated booth selection

**`FIXME VFE` comment in source:** The code notes "investigate if it ever happens" — indicating uncertainty about whether this update flow is actually triggered in practice. The `_cart_find_product_line` override is designed to find existing lines by booth, making this update path potentially unreachable in normal usage.

---

### `sale.order.line` — Extended

**File:** `models/sale_order_line.py`

#### `_compute_name_short()`

```python
@api.depends('event_booth_ids')
def _compute_name_short(self):
    wbooth = self.filtered(lambda line: line.event_booth_pending_ids)
    for record in wbooth:
        record.name_short = record.event_booth_pending_ids.event_id.name
    super(SaleOrderLine, self - wbooth)._compute_name_short()
```

**Purpose:** `name_short` is the short label shown in the cart (the text next to the product in the cart line). For booth lines, this is set to the event name instead of the product name. This helps users identify which event the booth belongs to when reviewing their cart.

**Logic:** Lines with pending booth registrations get `name_short = event.name`. All other lines fall through to the parent implementation.

---

## L2: Field Types, Defaults, Constraints

### Field Types — Booth Lines on `sale.order.line`

The fields below are defined in `event_booth_sale` (the base module). This module extends their behavior through overrides.

| Field | Type | Defined in | Description |
|---|---|---|---|
| `event_booth_category_id` | Many2one `event.booth.category` | `event_booth_sale` | Booth category for this line |
| `event_booth_pending_ids` | Many2many `event.booth` | `event_booth_sale` | Booths tentatively reserved in cart |
| `event_booth_registration_ids` | One2many `event.booth.registration` | `event_booth_sale` | Confirmed booth registrations |
| `event_booth_ids` | One2many `event.booth` | `event_booth_sale` | Fully confirmed booths |

### Event `booth.registration` Lifecycle (event_booth_sale)

```
Cart line created
  → _prepare_order_line_values() creates event_booth_registration records
  → booths remain state='available' (tentative reservation)

Order confirmed (sale.order.action_confirm)
  → sale.order.line._update_event_booths()
    → event_booth_registration_ids.action_confirm()
      → booth.action_confirm({'partner_id': partner, ...})
      → booth.state = 'unavailable'
      → _cancel_pending_registrations()
         [Other carts with same booth → sale order cancelled]
```

### Constraints

| Constraint | Location | Rule |
|---|---|---|
| `_unique_registration` SQL | `event.booth.registration` | `UNIQUE(sale_order_line_id, event_booth_id)` — one registration per booth per SO line |
| `_check_event_booth_registration_ids` | `sale.order.line` | All booths on one SO line must belong to the same event |
| Quantity guard | `sale.order._verify_updated_quantity` | Booth lines cannot have qty > 1 |
| Availability check | `sale.order.line._update_event_booths` | Unavailable booths at confirmation time raise ValidationError |

### Computed Fields (from event_booth_sale)

| Field | Compute | Dependencies | Notes |
|---|---|---|---|
| `event_booth_pending_ids` | `_compute_event_booth_pending_ids` | `event_booth_registration_ids` | Derives from registration records |
| `name` | `_compute_name` | — | Full multiline description (event + booth names) |
| `price_reduce` | `_get_display_price` | `event_booth_pending_ids`, `pricelist_item_id` | Sums booth prices with or without discount |

---

## L3: Cross-Model, Override Patterns, Workflow Triggers

### Cross-Module Architecture

```
website_event_booth_sale module:

Controller: event_booth.py (this module)
  └─ event_booth_registration_confirm()
       ├─ Validates booths and email (from website_event_booth)
       ├─ Gets or creates cart: request.cart or request.website._create_cart()
       ├─ _cart_add(product_id=booth_category.product_id, quantity=1,
       │            event_booth_pending_ids=booths.ids, registration_values=booth_values)
       │    └─ sale.order._prepare_order_line_values()
       │         └─ Creates event.booth.registration records
       ├─ If amount_total > 0 → redirect to /shop/cart (payment step)
       └─ If amount_total == 0 → action_confirm() → immediate confirmation

event.booth.registration (event_booth_sale)
  ├─ sale_order_line_id ───────────────────────→ sale.order.line
  ├─ event_booth_id ─────────────────────────→ event.booth
  └─ action_confirm() ───────────────────────→ Confirms booth + cancels conflicting carts

sale.order.line (event_booth_sale, extended by this module)
  ├─ event_booth_pending_ids (M2M) ───────────────→ event.booth
  ├─ event_booth_registration_ids (O2M) ─────────→ event.booth.registration
  ├─ event_booth_ids (O2M) ───────────────────────→ event.booth
  └─ event_id ─────────────────────────────────────→ event.event
```

### Workflow Trigger: Booth Purchase Flow (Complete)

```
Step 1: Browse booth page
  GET /event/<slug>/booth
  → website_event_booth._prepare_booth_main_values()
  → Booth browsing page rendered (categories, availability)
  → has_payment_step = request.cart.amount_total OR any(booth_category.price)

Step 2: Select booths and confirm
  POST /event/<slug>/booth/confirm  (website_event_booth_sale override)
  → Validates booths availability and email
  → Gets or creates cart (request.cart or request.website._create_cart())
  → _cart_add(
      product_id=booth_category.product_id,
      quantity=1,
      event_booth_pending_ids=booths.ids,
      registration_values={partner_id, contact_name, contact_email, contact_phone}
    )
      → sale.order._cart_find_product_line(event_booth_pending_ids=booths.ids)
        [Finds existing cart line if same booth already in cart]
      → sale.order._prepare_order_line_values(event_booth_pending_ids=booths.ids)
        [Creates event.booth.registration records]
      → sale.order.line._inverse_event_booth_pending_ids()
        [Creates event.booth.registration for each booth]

Step 3a: Paid booths — redirect to cart
  If order.amount_total > 0:
    → Returns JSON: {'redirect': '/shop/cart'}
    → Visitor proceeds through checkout
    → Payment received
    → sale.order.action_confirm()
      → sale.order.line._update_event_booths()
        → event_booth_registration_ids.action_confirm()
          → booth.action_confirm(...)
          → _cancel_pending_registrations()
    → Booth state = 'unavailable'

Step 3b: Free booths — immediate confirmation
  If order.amount_total == 0:
    → order_sudo.action_confirm()
    → booth registrations confirmed immediately
    → request.website.sale_reset()
    → Returns JSON: {'success': True, contact info}
```

### Override Pattern: `has_payment_step` Context Flag

Both controller methods prepend `has_payment_step` to the values passed to the parent templates:

```python
# In _prepare_booth_contact_form_values:
values = super()._prepare_booth_contact_form_values(...)
values['has_payment_step'] = (
    request.cart.amount_total > 0 or
    values.get('booth_category', request.env['event.booth.category']).price > 0
)

# In _prepare_booth_main_values:
values = super()._prepare_booth_main_values(...)
values['has_payment_step'] = (
    request.cart.amount_total > 0 or
    any(booth_category.price > 0
         for booth_category in values.get('available_booth_category_ids', ...))
)
```

This flag controls whether a "Proceed to Payment" step is shown in the registration flow. If the booth is free (price = 0) and the cart has no other items, the flow skips payment and confirms immediately.

---

## L4: Version Changes Odoo 18→19, Security

### Odoo 18 → 19 Changes

#### Change 1: `event_booth_pending_ids` on `_cart_find_product_line`

**Odoo 18:** The `_cart_find_product_line` method signature did not explicitly pass `event_booth_pending_ids` as a keyword argument. The override pattern may have used positional arguments or a different method signature.

**Odoo 19:** The override explicitly accepts `event_booth_pending_ids=None` as a keyword argument and passes it through:

```python
def _cart_find_product_line(self, *args, event_booth_pending_ids=None, **kwargs):
    lines = super()._cart_find_product_line(
        *args, event_booth_pending_ids=event_booth_pending_ids, **kwargs,
    )
```

This pattern is more robust — it forwards any additional kwargs to the parent and only filters by booths when `event_booth_pending_ids` is provided.

#### Change 2: `event_booth_registration_ids` on `_prepare_order_line_update_values`

**Odoo 18:** The `_prepare_order_line_update_values` method may not have had explicit booth registration handling. In Odoo 19, the pattern was clarified: the method receives `event_booth_pending_ids` and `registration_values`, then replaces all existing registrations with new ones.

**`FIXME VFE` in source:** The comment `"""Delete existing booth registrations and create new ones with the update values."""` indicates that the Odoo team is uncertain whether this code path is actually exercised in practice. The `_cart_find_product_line` override should prevent duplicate cart lines, which would prevent this update path from being reached.

#### Change 3: `name_short` compute refinement

**Odoo 18:** The `_compute_name_short` on `sale.order.line` may have used a simpler pattern for booth lines.

**Odoo 19 (current):** The implementation explicitly filters to only lines with `event_booth_pending_ids` before applying the custom name:

```python
wbooth = self.filtered(lambda line: line.event_booth_pending_ids)
for record in wbooth:
    record.name_short = record.event_booth_pending_ids.event_id.name
super(SaleOrderLine, self - wbooth)._compute_name_short()
```

The `self - wbooth` subtraction ensures non-booth lines call the parent method without interference.

### Security Analysis

#### Access Control

This module does not define its own ACLs. Security is inherited from:

| Model | ACL from | Public read? |
|---|---|---|
| `sale.order` | `sale` module | No |
| `sale.order.line` | `sale` module | No |
| `product.template` | `product` module | Yes (inherited from website) |
| `event.booth` | `event_booth` module | No |
| `event.booth.registration` | `event_booth_sale` module | No |

**Cart access:** The cart (`request.cart`) is accessed with elevated privileges (`request.cart` uses sudo internally). Visitors can only access their own cart through the session. The `sale.order._cart_find_product_line` override correctly filters by booth to prevent cross-visitor cart pollution.

#### Zero-Price Product Validation Bypass

The `_get_product_types_allow_zero_price` extension adds `"event_booth"` to the list of types allowed to have zero price. Without this:
- A booth category with `list_price = 0` would fail the standard sale order validation when added to the cart
- Free booth registrations (complimentary booths, sponsor booths) would be blocked

**Security concern:** This bypasses the standard price validation. In practice, free booths are a legitimate business case for event organizers offering complimentary or sponsored booth space.

**Risk mitigation:** The free-booth flow still creates a proper `sale.order` record (with amount = 0) and goes through `action_confirm()`. The registration is tracked in the same way as paid booths.

#### Cart Poisoning Attack Vector

**Scenario:** An attacker adds a booth to the cart, then manipulates the cart to add a different booth to the same cart line.

**Mitigation:** Each booth gets its own `event.booth.registration` record. The SQL unique constraint on `(sale_order_line_id, event_booth_id)` prevents the same booth from being registered twice on the same SO line. If the attacker tries to replace booth A with booth B on the same line:
1. The existing `event_booth.registration` for booth A is deleted (via `_prepare_order_line_update_values` or the inverse setter)
2. Booth A is released back to available state

**Risk level:** Low. The unique constraint and state machine prevent double-booking.

#### Information Disclosure

| Data | Visibility | Risk |
|---|---|---|
| Booth availability | Public (via JSON-RPC) | Low — public registration page requires this |
| Booth booking contact details | Only visible to event managers | Low — ACLs control access |
| Cart contents | Private to session owner | Low — enforced by session |
| Booth prices | Public on registration page | Low — normal e-commerce behavior |

### Performance Considerations

| Operation | Query count | Notes |
|---|---|---|
| Add booth to cart | 1 SO line create + N registration creates | Fast, O(N) where N = booth count |
| Update cart (change booth selection) | 1 unlink + N creates | `_cart_find_product_line` finds existing line first |
| Free booth confirmation | 1 `action_confirm()` per booth | One `write` + one `message_post` per booth |
| Cart page load | Normal sale cart + booth line rendering | No additional queries beyond standard cart |

**Cart dedup optimization:** The `_cart_find_product_line` override with `event_booth_pending_ids` filtering is O(n) on the existing cart lines. For carts with many items, this is still fast since the cart is session-scoped and typically has < 20 lines.

**No N+1 on booth prices:** `sale.order.line._get_display_price()` computes the total price for all booths in the line in a single pass:

```python
total_price = sum(booth.booth_category_id.price_reduce for booth in event_booths)
```

### Extension Points

| Extension point | How to use |
|---|---|
| Add a setup fee per booth | Override `sale.order._prepare_order_line_values` to add extra line items |
| Restrict booths by partner type | Override `_check_booth_registration_values` (from `website_event_booth`) to add validation |
| Custom confirmation email | Extend `event_booth_sale.action_confirm()` or add a `_post_confirmation_hook()` |
| Booths with multi-event packages | Extend `_prepare_order_line_values` to handle multiple `event_id` values (constrained by `_check_event_booth_registration_ids`) |
| Automatic booth release on cart expiry | Hook into `sale.order._cart_expire()` (from `website_sale`) to call `action_set_available()` |
| Different payment providers | Standard Odoo payment provider flow — no modification needed |

---

## See Also

- [Modules/event_booth](Modules/event_booth.md) — core booth data model (`event.booth`, `event.booth.category`)
- [Modules/event_booth_sale](Modules/event_booth_sale.md) — pricing and sale order integration for booths
- [Modules/website_event_booth](Modules/website_event_booth.md) — public booth registration portal (free booths, no payment)
- [Modules/Sale](Modules/Sale.md) — sale order and cart mechanics
- [Modules/website_sale](Modules/website_sale.md) — website e-commerce integration
- [Modules/Event](Modules/event.md) — event management base module

---

**Tags:** `#module` `#booth-registration` `#website` `#e-commerce` `#event-booth` `#cart`
