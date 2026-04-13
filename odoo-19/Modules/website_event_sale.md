---
tags: [odoo, odoo19, modules, ecommerce, event, website_sale]
description: Sell event tickets online through the eCommerce cart and checkout flow. Bridges website_event, event_sale, and website_sale.
---

# website_event_sale — Online Event Ticketing

> Sell event tickets through the eCommerce website (online ticketing portal). Bridges `website_event`, `event_sale`, and `website_sale`. Handles the full flow from ticket selection on the event page, through cart management with seat availability guards, to payment confirmation and attendee registration creation.

**Category:** Website/Website  
**Depends:** `website_event`, `event_sale`, `website_sale`  
**Auto-install:** True  
**Author:** Odoo S.A.  
**License:** LGPL-3  
**Module root:** `odoo/addons/website_event_sale/`

---

## Module Dependency Chain

```
website_event_sale
├── website_event      → event website pages, registration forms, ticket selection UI
├── event_sale         → ticket-as-product, sale.order.line event linkage, seat tracking
└── website_sale       → shopping cart, pricelists, checkout flow, payment
```

`website_event_sale` is the integration layer that wires the event ticket purchasing experience into the standard eCommerce cart and checkout. It does not define the core ticket or registration models — those live in `event_sale`.

---

## File Inventory

| File | Kind | Purpose |
|---|---|---|
| `__manifest__.py` | Manifest | Module metadata, depends, data files, assets |
| `__init__.py` | Bootstrap | Imports `controllers`, `models`, `report` |
| `models/__init__.py` | Bootstrap | Imports 4 model files |
| `models/product.py` | Model | `ProductProduct` (image exposure, placeholder) + `ProductTemplate` (zero-price allow) |
| `models/product_pricelist.py` | Model | `ProductPricelistItem` onchange warning for event tickets |
| `models/sale_order.py` | Model | `SaleOrder` — cart seat-guards, registration cancellation, abandoned mail filter |
| `models/sale_order_line.py` | Model | `SaleOrderLine` — display name, strikethrough price, reorder block |
| `controllers/__init__.py` | Bootstrap | Imports controller modules |
| `controllers/main.py` | Controller | `WebsiteEventSaleController` — registration-to-cart pipeline, confirmation flow |
| `controllers/payment.py` | Controller | `PaymentPortalOnsite` — post-payment hard seat verification |
| `controllers/sale.py` | Controller | `WebsiteEventSale` — confirmation page data enrichment |
| `report/__init__.py` | Bootstrap | Imports report module |
| `report/event_sale_report.py` | Report | Adds `is_published` to `event.sale.report` |
| `report/event_sale_report_views.xml` | View | Search filter for published events on the report |
| `views/event_event_views.xml` | View | Makes `company_id` required on event form |
| `views/website_event_templates.xml` | Template | Pricelist selector, ticket price display, registration modal buttons |
| `views/website_sale_templates.xml` | Template | Cart line product links, cart summary slot display, confirmation page |
| `data/event_data.xml` | Data | Sets `website_menu = True` on demo event type |

---

## Models

### `product.product` — extended (`models/product.py`)

#### `event_ticket_ids` — `One2many('event.event.ticket', 'product_id')`

Defined on `product.product` to allow access rules to traverse from product → tickets. The reverse of the ticket's `product_id` link. Primarily used for ACL traversal and image exposure decisions.

#### `_can_return_content(field_name=None, access_token=None)` — override

```python
def _can_return_content(self, field_name=None, access_token=None):
    if (
        field_name in ["image_%s" % size for size in [1920, 1024, 512, 256, 128]]
        and self.sudo().event_ticket_ids
    ):
        return True
    return super()._can_return_content(field_name, access_token)
```

**Purpose:** Allow public (unauthenticated) users to fetch product images for event tickets even if the underlying product is unpublished.

- Uses `sudo()` because the public user has no read access to event tickets by default.
- Only image fields are whitelisted (1920, 1024, 512, 256, 128px variants). No other product data is exposed to public users.
- `event_ticket_ids` is used as the sentinel: if the product is linked to any ticket, its images are public.
- Called by the `website_content` controller when serving product images via `/web/image/product.product/<id>/image_xxx`.

#### `_get_product_placeholder_filename()` — override

```python
def _get_product_placeholder_filename(self):
    if self.event_ticket_ids:
        return 'website_event_sale/static/img/event_ticket_placeholder_thumbnail.png'
    return super()._get_product_placeholder_filename()
```

Returns a themed event-ticket placeholder image instead of the generic product placeholder when the product has associated event tickets.

---

### `product.template` — extended (`models/product.py`)

#### `_get_product_types_allow_zero_price()` — override

```python
def _get_product_types_allow_zero_price(self):
    return super()._get_product_types_allow_zero_price() + ["event"]
```

**Purpose:** Allow `"event"` product type to have a unit price of `0` without triggering `website_sale`'s zero-price validation error at `_cart_add` time.

**Mechanism:** Appends `"event"` to the list returned by `website_sale`'s `ProductTemplate._get_product_types_allow_zero_price()`. Free event tickets are a first-class use case (e.g., early-bird free registrations, webinar invites).

---

### `product.pricelist.item` — extended (`models/product_pricelist.py`)

#### `_onchange_event_sale_warning()` — `@api.onchange`

**Trigger:** Changes to `applied_on`, `product_id`, `product_tmpl_id`, or `min_quantity`.

**Three-branch warning logic:**

| Condition | Message |
|---|---|
| `min_quantity > 0` and `applied_on` in `'3_global'` or `'2_product_category'` | *"A pricelist item with a positive min. quantity will not be applied to the event tickets products."* |
| `applied_on == '1_product'` and `product_tmpl_id.service_tracking == 'event'` | *"A pricelist item with a positive min. quantity cannot be applied to this event tickets product."* |
| `applied_on == '0_product_variant'` and `product_id.service_tracking == 'event'` | Same as above |

**Design rationale:** Global/category-level quantity-based discounts cannot meaningfully target ticket products because ticket quantities are determined by seat count, not by generic product qty rules. The onchange does not block saving — it is purely advisory UI feedback. A salesperson can still save the pricelist rule; it simply will not apply to event tickets.

**`service_tracking` check:** The check for `service_tracking == 'event'` to detect event-ticket products aligns with Odoo's product-service tracking feature. This is the integration point between `event_product` (which adds the `event` option to `service_tracking`) and the eCommerce pricing layer.

---

### `sale.order` — extended (`models/sale_order.py`)

Extends `website_sale`'s cart management with event-specific seat guards and registration lifecycle. This is the primary integration point with `event_sale`'s `sale.order.line` event fields.

#### `_cart_find_product_line(*, event_slot_id=False, event_ticket_id=False, **kwargs)` — override

```python
def _cart_find_product_line(self, *args, event_slot_id=False, event_ticket_id=False, **kwargs):
    lines = super()._cart_find_product_line(
        *args, event_slot_id=event_slot_id, event_ticket_id=event_ticket_id, **kwargs,
    )
    if not event_slot_id and not event_ticket_id:
        return lines  # No event filtering needed
    return lines.filtered(
        lambda line: line.event_slot_id.id == event_slot_id
                     and line.event_ticket_id.id == event_ticket_id
    )
```

**Purpose:** Find the specific cart line matching a ticket+slot combination, refining the generic `product_id + uom_id + linked_line_id` lookup from `website_sale`.

- The parent `website_sale.SaleOrder._cart_find_product_line` already handles `event_slot_id` and `event_ticket_id` via `**kwargs` passing them to `_cart_update_order_line`, but does not use them for line matching.
- This override adds explicit `(slot, ticket)` filtering so that multiple attendees buying the same ticket for the same slot aggregate onto one cart line.
- **Multi-slot correctness:** The same ticket type can exist across multiple slots. Without this filter, a user who buys Ticket A for Slot 1 and then Ticket A for Slot 2 would see only one cart line. The explicit slot+ticket filter ensures separate lines.

#### `_verify_updated_quantity(order_line, product_id, new_qty, uom_id, *, event_slot_id=False, event_ticket_id=False, **kwargs)` — override

```python
def _verify_updated_quantity(self, order_line, product_id, new_qty, uom_id, *, ...):
    new_qty, warning = super()._verify_updated_quantity(...)

    if not event_ticket_id:
        if not order_line.event_ticket_id or new_qty < order_line.product_uom_qty:
            return new_qty, warning
        else:
            return order_line.product_uom_qty, _("You cannot raise manually the event ticket quantity in your cart")

    # Adding new ticket (or updating existing line)
    ticket = self.env['event.event.ticket'].browse(event_ticket_id).exists()
    if not ticket:
        raise UserError(_("The provided ticket doesn't exist"))
    slot = self.env['event.slot'].browse(event_slot_id).exists()
    if event_slot_id and not slot:
        raise UserError(_("The provided ticket slot doesn't exist"))

    existing_qty = order_line.product_uom_qty if order_line else 0
    qty_added = new_qty - existing_qty
    warning = ''

    ticket_seats_available = (
        ticket.event_id._get_seats_availability([(slot, ticket)])[0]
        if slot else ticket.seats_available
    )
```

**Seat availability enforcement — three outcomes:**

| Condition | New qty | Warning message |
|---|---|---|
| `seats_limited AND ticket_seats_available <= 0` | `existing_qty` (revert; remove line if exists) | "Sorry, The %(ticket)s tickets for the %(event)s event are sold out." |
| `seats_limited AND qty_added > ticket_seats_available` | `existing_qty + ticket_seats_available` (partial fill) | "Sorry, only %(remaining_seats)d seats are still available for the %(ticket)s ticket for the %(event)s event%(slot)s." |
| Otherwise | unchanged `new_qty` | `warning` |

**Partial fill design:** When `qty_added > ticket_seats_available`, the new quantity becomes `existing_qty + ticket_seats_available`. If the user had 3 tickets and tries to add 2 more but only 1 seat is left, the quantity stays at 3. The intent is conservative: never auto-increase beyond what the user explicitly had.

**Manual raise block:** If `event_ticket_id` is present but `new_qty <= existing_qty` (quantity decrease), the parent result is returned unchanged. If `new_qty > existing_qty` and no `event_ticket_id` is passed, the method checks `order_line.event_ticket_id`. If the user tries to manually increase qty beyond existing, it reverts to `existing_qty` with a message "You cannot raise manually the event ticket quantity in your cart" — preventing users from circumventing seat checks.

**TODO in source (L4):** The developer notes that the current logic checks `qty_added` rather than total cart quantity. This is appropriate because `event_sale` auto-confirms registrations on SO confirmation, so confirmed registrations are the authoritative seat counters. However, if registrations are not auto-confirmed (e.g., manual approval workflow), this logic could allow double-booking since confirmed registrations would not yet exist.

**Race condition (L4):** Two concurrent cart additions for the last seat will both pass `_verify_updated_quantity` since availability is checked without row-level locking. The payment controller's `_validate_transaction_for_order` re-checks after payment.

#### `_prepare_order_line_values(product_id, *args, event_slot_id=False, event_ticket_id=False, **kwargs)` — override

```python
def _prepare_order_line_values(self, product_id, *args, event_slot_id=False, event_ticket_id=False, **kwargs):
    values = super()._prepare_order_line_values(
        product_id, *args, event_ticket_id=event_ticket_id, **kwargs,
    )
    if not event_ticket_id:
        return values
    ticket = self.env['event.event.ticket'].browse(event_ticket_id)
    if ticket.product_id.id != product_id:
        raise UserError(_("The ticket doesn't match with this product."))
    values['event_id'] = ticket.event_id.id
    values['event_ticket_id'] = ticket.id
    values['event_slot_id'] = event_slot_id
    return values
```

**Purpose:** Inject event linkage fields into the newly created `sale.order.line` values dict before `create()`.

**Ticket/product spoofing prevention:** Validates `ticket.product_id.id == product_id` before setting any fields. This prevents a malicious user from crafting a POST that supplies an `event_ticket_id` for a product different from the one being added to cart. The ticket's linked product ID is the authoritative source of truth.

**`event_slot_id` injection:** May be `False` for single-slot events; will be a valid `event.slot` ID for multi-slot events. The `_cart_update_order_line` method in the same class propagates this correctly.

#### `_cart_update_order_line(order_line, quantity, **kwargs)` — override

```python
def _cart_update_order_line(self, order_line, quantity, **kwargs):
    old_qty = order_line.product_uom_qty
    updated_line = super()._cart_update_order_line(order_line, quantity, **kwargs)

    if (
        updated_line
        and updated_line.event_ticket_id
        and (diff := old_qty - updated_line.product_uom_qty) > 0
    ):
        attendees = self.env['event.registration'].search(
            domain=[
                ('state', '!=', 'cancel'),
                ('sale_order_id', '=', self.id),
                ('event_slot_id', '=', order_line.event_slot_id.id),
                ('event_ticket_id', '=', order_line.event_ticket_id.id),
            ],
            offset=updated_line.product_uom_qty,
            limit=diff,
            order='create_date asc',
        )
        attendees.action_cancel()
    return updated_line
```

**Purpose:** On cart quantity decrease, cancel excess `event.registration` records that were auto-created from the original quantity.

**Offset/limit pattern:** `offset=updated_line.product_uom_qty` skips the first N registrations (to keep) and `limit=diff` cancels the remainder. Assumes registrations are ordered by `create_date asc`. If registrations are created out of order (e.g., manual creation interleaved with cart operations), the wrong registrations could be cancelled. For normal cart flows this is safe.

**Edge case (L4):** Registrations in states other than `cancel` — `open`, `done` — are cancelled by `action_cancel()`. `done` registrations may have badge/ticket data already issued; cancelling them does not reverse that data. The `action_cancel()` workflow may trigger email notifications depending on event settings.

**Performance:** Single `search` with `offset`/`limit` — one SQL query regardless of quantity decrease.

#### `_filter_can_send_abandoned_cart_mail()` — override

```python
def _filter_can_send_abandoned_cart_mail(self):
    return super()._filter_can_send_abandoned_cart_mail().filtered(
        lambda so: all(ticket.sale_available for ticket in so.order_line.event_ticket_id),
    )
```

**Purpose:** Exclude carts containing expired or sold-out tickets from abandoned-cart email reminders.

- Filters `super()` result (all draft/quotation SOs) to keep only those where every ticket on every line has `sale_available = True`.
- `sale_available` is a `compute_sudo=True` field based on `is_launched`, `is_expired`, and `is_sold_out`.
- Runs as the SO's `user_id` (salesperson), not superuser; ACLs are respected.
- **Scheduler context:** Runs in the daily cron for abandoned cart emails, not per-user. For databases with many draft carts this filters all draft SOs.

---

### `sale.order.line` — extended (`models/sale_order_line.py`)

#### `_compute_name_short()` — override

```python
@api.depends('product_id.display_name', 'event_ticket_id.display_name')
def _compute_name_short(self):
    super()._compute_name_short()
    for line in self:
        if line.event_ticket_id:
            line.name_short = line.event_ticket_id.display_name
```

**Purpose:** In the website cart mini-display (used in the cart dropdown and checkout summary), show the ticket name instead of the underlying product name. The `name_short` field is used by `website_sale` templates for the compact cart line display.

#### `_should_show_strikethrough_price()` — override

```python
def _should_show_strikethrough_price(self):
    return super()._should_show_strikethrough_price() and not self.event_id
```

**Purpose:** Hide "was/now" strikethrough pricing for event tickets.

**Rationale:** Event tickets typically have a single public price. Showing a "discounted from X" strikethrough is not meaningful when there is no previous list price that applies to event contexts. Tickets have their own `price` field, not a product `lst_price` that would produce a discount comparison.

#### `_is_reorder_allowed()` — override

```python
def _is_reorder_allowed(self):
    return not self.event_id and super()._is_reorder_allowed()
```

**Purpose:** Prevent event tickets from being added via the "Reorder" (SO history) button.

**Rationale:** Seat availability changes over time; replaying an old ticket order could fail (sold out) or produce incorrect results. The event or ticket configuration may also have changed since the original order (different price, different slots, etc.). Reorders for standard products are allowed.

---

## Controllers

### `WebsiteEventSaleController` — `controllers/main.py`

**Inherits:** `website_event.controllers.main.WebsiteEventController`

Extends the event registration flow to integrate with the eCommerce cart.

#### `_process_tickets_form(event, form_details)` — override

```python
def _process_tickets_form(self, event, form_details):
    res = super()._process_tickets_form(event, form_details)
    for item in res:
        item['price'] = item['ticket']['price'] if item['ticket'] else 0
    return res
```

**Purpose:** Augment each ticket entry in `form_details` with `price` from the ticket object. The parent `WebsiteEventController._process_tickets_form` returns ticket metadata including `ticket` (the ticket record). This override extracts `ticket.price` and adds it to each item's data dict. Used by `registration_confirm` to build cart data.

#### `_create_attendees_from_registration_post(event, registration_data)` — override

**Full flow for registrations submitted from the event page:**

```
1. If no registration has event_ticket_id → super() (free events, no cart)
2. If all tickets are free (price == 0) AND no existing cart → super()
3. Otherwise (sale mode):
   a. Get or create SO: request.cart or request.website._create_cart()
   b. Aggregate by (slot_id, ticket_id): tickets_data[slot_id, ticket_id] += count
   c. For each unique pair: order_sudo._cart_add(product_id, quantity, event_ticket_id, event_slot_id)
   d. Store returned line_id in cart_data[slot_id, ticket_id]
   e. Inject sale_order_id and sale_order_line_id into each registration_data dict
   f. super() — creates registrations linked to cart lines
```

**Aggregation design:** Collapses multiple attendees buying the same ticket type into one cart line with `quantity=N`. This is essential for group purchases where one person fills in details for multiple attendees.

**Ticket browsing with `sudo()`:** `event_ticket_by_id` is built using `sudo()` because the public registration form runs as the public user, who lacks read access to event tickets. Ticket prices are considered public information in most event scenarios; authentication is required at checkout.

#### `registration_confirm(event, **post)` — override

**Handles the final step of the event registration page (after attendee details are submitted):**

```
1. super() — processes attendee data
2. order_sudo = request.cart
3. If no ticket lines → super() result (free event with no cart)
4. If any registration has ticket:
   a. amount_total > 0 (paid order):
      - If anonymous cart: collect/update address from first attendee
      - Store sale_last_order_id in session
      - Redirect /shop/checkout?try_skip_step=true
   b. amount_total == 0 (free order):
      - order_sudo.action_confirm() → auto-creates registrations via event_sale
      - Reset website sale session
      - Redirect /shop/confirmation
```

**Anonymous cart address collection:** `CustomerPortal()._create_or_update_address()` is called to collect/update the SO's partner address from the first attendee's details. This avoids a blank address on the SO for guest checkouts.

**Free order auto-confirmation:** `order_sudo.action_confirm()` triggers `event_sale`'s `_init_registrations()` logic, which creates registrations. For free orders (amount_total == 0), `_compute_registration_status` sets them directly to `state='open'`.

---

### `PaymentPortalOnsite` — `controllers/payment.py`

**Inherits:** `website_sale.controllers.payment.PaymentPortal`

#### `_validate_transaction_for_order(transaction, sale_order)` — override

**Purpose:** Re-verify seat availability at payment time — after the cart-level soft check already passed.

```python
def _validate_transaction_for_order(self, transaction, sale_order):
    super()._validate_transaction_for_order(transaction, sale_order)

    registration_domain = [
        ('sale_order_id', '=', sale_order.id),
        ('event_ticket_id', '!=', False),
        ('state', '!=', 'cancel'),
    ]
    registrations_per_event = request.env['event.registration'].sudo()._read_group(
        registration_domain, ['event_id'], ['id:recordset']
    )
    for event, registrations in registrations_per_event:
        count_per_slot_ticket = request.env['event.registration'].sudo()._read_group(
            [('id', 'in', registrations.ids)],
            ['event_slot_id', 'event_ticket_id'], ['__count']
        )
        event._verify_seats_availability([
            (slot, ticket, count)
            for slot, ticket, count in count_per_slot_ticket
        ])
```

**Hard seat check:** `_verify_seats_availability()` raises `ValidationError` if any ticket's reserved+confirmed count exceeds `seats_max`. This is the authoritative check after payment. If seats were consumed by another concurrent buyer between cart-add and payment, the transaction is rejected.

**`sudo()`:** Uses elevated privileges to read registrations without raising access errors. Data is used only for seat counting; no sensitive registration data is exposed.

**Why needed (L4):** The cart-level check in `_verify_updated_quantity` is a soft guard (partial fill). The payment-level check is a hard guard. The two-layer approach: (1) cart catches most issues early with partial-fill warnings; (2) payment catches race conditions and edge cases that survived the cart check.

---

### `WebsiteEventSale` — `controllers/sale.py`

**Inherits:** `website_sale.controllers.main.WebsiteSale`

#### `_prepare_shop_payment_confirmation_values(order)` — override

Extends the standard order confirmation context with event-specific data:

```python
values['events'] = order.order_line.event_id  # unique events in this order
attendee_per_event_read_group = request.env['event.registration'].sudo()._read_group(
    [('sale_order_id', '=', order.id), ('state', 'in', ['open', 'done'])],
    groupby=['event_id'],
    aggregates=['id:recordset'],
)
values['attendee_ids_per_event'] = {
    event: regs.grouped('event_slot_id') if event.is_multi_slots else regs
    for event, regs in attendee_per_event_read_group
}
values['urls_per_event'] = {
    event.id: {
        slot.id: event._get_event_resource_urls(slot=slot)
        for slot in value.grouped('event_slot_id')
    } if event.is_multi_slots else event._get_event_resource_urls()
    for event, value in attendee_per_event_read_group
}
```

| Key | Value |
|---|---|
| `events` | `order.order_line.event_id` — all unique events in the order |
| `attendee_ids_per_event` | Dict: `event` → list of registrations (grouped by `event_slot_id` if `is_multi_slots`) |
| `urls_per_event` | Dict: `event.id` → `{slot.id: {iCal_url, google_url}, ...}` or global calendar URLs |

**Registration domain:** `('sale_order_id', '=', order.id), ('state', 'in', ['open', 'done'])` — excludes cancelled registrations.

**Calendar link generation:** For each slot, calls `event._get_event_resource_urls(slot=slot)`. For non-multi-slot events, calls `event._get_event_resource_urls()` (global event URLs). The result is a dict mapping event/slot IDs to calendar URL dicts, passed to the QWeb template for rendering.

---

## Report

### `EventSaleReport` — `report/event_sale_report.py`

**Inherits:** `event.sale.report` (from `event_sale`)

#### `is_published` — `Boolean`, readonly

```python
is_published = fields.Boolean('Published Events', readonly=True)

def _select_clause(self, *select):
    return super()._select_clause('event_event.is_published as is_published', *select)
```

**Purpose:** Mirrors `event_event.is_published` into the report view, enabling the "Published Events" filter in the report's search view.

---

## Views (XML)

### `views/event_event_views.xml`

**`event_form_mandatory_company`:** Makes `company_id` **required** on `event.event` forms when `website_event_sale` is installed. Required because ticket sales must be attributed to a company for correct currency conversion and accounting.

### `report/event_sale_report_views.xml`

**`event_sale_report_view_search`:** Adds a **"Published Events"** filter to the search view of `event.sale.report`. Domain: `[('is_published', '=', True)]`. Allows event managers to filter the sales report to show only published events.

### `views/website_event_templates.xml`

**`modal_ticket_registration` (inherits `website_event.modal_ticket_registration`):**

1. **Pricelist selector** injected into the ticket modal (renders `website_sale.pricelist_list`).
2. **Price display on multi-ticket rows** (collapsed list): shows strikethrough `price` + `price_reduce` with tax toggle based on `website.show_line_subtotals_tax_selection`; "Free" badge if `price == 0`.
3. **Price display on single-ticket row** (uncollapsed): same pattern with badge styling.
4. **Price-range header** updated to show `"From X to Y"` when tickets have different prices.
5. **CSS class modification** on multi-select div: suppresses margin when ticket is unavailable/expired/not-launched.

**`registration_attendee_details`:** Replaces the "Continue" button with conditional logic:
- Mandatory login enabled + public user + paying ticket → "Sign In" button.
- Paying tickets → "Go to Payment".
- Free tickets → "Confirm Registration".

### `views/website_sale_templates.xml`

**`cart_line_product_link_inherit_website_event_sale`:** Replaces the product link `href` with: if `line.event_id` exists → `/event/{slug(event_id)}/register`; otherwise → `product_id.website_url`.

**`cart_summary_inherit_website_event_sale`:** Adds `line.event_slot_id.display_name` below the product name in the cart summary for multi-slot events.

**`event_confirmation` (inherits `website_sale.confirmation`):**
- Renders a full event card (cover image, name, subtitle) for each event in the order.
- **Non-multi-slot:** shows ticket access info directly below the event card.
- **Multi-slot:** iterates over each slot, showing slot start/end datetime (in event timezone) and ticket access widget for registrations in that slot.
- Includes event calendar links (iCal, Google Calendar) per event/slot.
- Calls `website_event.event_confirmation_end_page_hook` for downstream customization.

---

## Cross-Module Field Reference

`event_sale` adds these fields to `sale.order.line`:

| Field | Type | Description |
|---|---|---|
| `event_id` | `Many2one event.event` | Event for this ticket line |
| `event_slot_id` | `Many2one event.slot` | Slot for multi-slot events; False otherwise |
| `event_ticket_id` | `Many2one event.event.ticket` | Ticket type being purchased |
| `is_multi_slots` | `Boolean` (related) | `event_id.is_multi_slots` |
| `registration_ids` | `One2many event.registration` | Registrations created from this line |

`event` core adds to `event.event.ticket`:

| Field | Type | Description |
|---|---|---|
| `sale_available` | `Boolean` (compute, sudo) | `is_launched AND NOT is_expired AND NOT is_sold_out` |
| `seats_available` | `Integer` (compute) | `seats_max - seats_reserved - seats_used` |
| `seats_limited` | `Boolean` | Whether `seats_max > 0` |
| `seats_max` | `Integer` | Maximum capacity for this ticket |
| `product_id` | `Many2one product.product` | The product variant linked to this ticket |
| `price` | `Float` | Unit price excl. tax |
| `price_incl` | `Float` | Unit price incl. tax |
| `price_reduce` | `Float` | Active price after discounts |
| `price_reduce_taxinc` | `Float` | Active price incl. tax |

---

## Data Flows

### Cart Addition Flow (Website)

```
User selects ticket(s) on /event/{slug}/register
  → _process_tickets_form()            [adds price to form data]
  → registration_confirm()               [receives POST, processes attendees]
    → _create_attendees_from_registration_post()
        → order_sudo._cart_add(product_id, qty, event_ticket_id, event_slot_id)
            → SaleOrder._cart_find_product_line()      [filtered by slot+ticket]
            → SaleOrder._verify_updated_quantity()       [seat availability check]
            → SaleOrder._prepare_order_line_values()      [sets event_id, ticket_id, slot_id]
            → SaleOrder._cart_update_order_line()        [creates or updates line]
        → Registrations created with sale_order_line_id linkage
    → amount_total > 0 → redirect /shop/checkout?try_skip_step=true
    → amount_total == 0 → action_confirm() + /shop/confirmation
```

### Quantity Decrease (Cart) Flow

```
User reduces ticket qty in cart
  → _cart_update_order_line(old_qty, new_qty)
      → diff = old_qty - new_qty > 0
      → search event.registration (offset=new_qty, limit=diff, order='create_date asc')
      → action_cancel() on excess registrations
```

### Payment Confirmation Flow

```
Payment provider returns to /shop/payment/transaction/{id}
  → PaymentPortal._validate_transaction_for_order()
      → event._verify_seats_availability()           [hard seat check]
      → Raises ValidationError if seats exhausted
  → WebsiteEventSale._prepare_shop_payment_confirmation_values()
  → Renders event_confirmation with attendees + calendar links
```

---

## L4 Analysis

### Performance Considerations

- **`_verify_updated_quantity`:** Called on every cart add/update/remove. Each invocation triggers `_get_seats_availability()` or reads `seats_available` — a computed field that internally uses `_read_group` on `event_registration`. For events with thousands of registrations, the query cost is O(n) on the registration table per cart interaction.

- **`sudo()` on registration reads in payment controller:** `_validate_transaction_for_order` uses `sudo()` to read all registrations regardless of the payment user's ACL. This is acceptable since the data is used only for seat counting; no registration content is exposed.

- **`_filter_can_send_abandoned_cart_mail`:** Filters all draft SOs in a database with potentially many carts. Runs in the scheduler (daily cron) context, not per-user.

- **No caching on `sale_available`:** Computed live. For very high-traffic event pages with many concurrent visitors, each page load recomputes seat availability via `_compute_seats` (which uses raw SQL on `event_registration`). The SQL query is: `SELECT event_ticket_id, state, count(*) FROM event_registration WHERE event_ticket_id IN %s AND state IN ('open', 'done') AND active = true GROUP BY event_ticket_id, state`. This is the only place in the event module where raw SQL is used (from the base `event` module), specifically to avoid N+1 queries across all tickets.

### Odoo 18 → 19 Changes

| Change | Detail |
|---|---|
| **Multi-slot event support** | The `event_slot_id` field, slot-aware cart line filtering, grouped registrations per slot, and per-slot calendar links on the confirmation page represent significant new functionality driven by the new `event.slot` model. |
| **`_cart_find_product_line` override** | The explicit `(slot, ticket)` filtering in addition to product filtering is new in 19 to handle multi-slot events where the same ticket type can exist across multiple slots. |
| **`is_published` on `event.sale.report`** | Added in 19 in `website_event_sale` to allow filtering the sales report by publication status. |
| **`service_tracking` check in pricelist onchange** | The `_onchange_event_sale_warning` check for `service_tracking == 'event'` to detect event-ticket products aligns with Odoo's product-service tracking feature refactor. |
| **`_prepare_order_line_values` ticket validation** | Explicitly validates `ticket.product_id.id == product_id` to prevent ticket/product spoofing via crafted POST parameters. This is a security fix introduced in 19. |
| **`_cart_update_order_line` registration cancellation** | Offset/limit pattern with `order='create_date asc'` for cancellation assumes registration ordering; new in 19 to handle qty decreases from the website cart. |

### Security Considerations

- **`sudo()` on ticket browse in controller:** `event_ticket_by_id` is built using `request.env['event.event.ticket'].sudo().browse(...)`. This allows the public registration form to read ticket prices without authentication. Ticket prices are public information in most event scenarios; payment requires login at checkout.

- **`_can_return_content` bypass:** Allows unpublished product images to be served if the product is linked to a ticket. Intentional: unpublished events should still show ticket images on the registration page. Only image fields are whitelisted — no other product data is exposed.

- **`event_slot_id` injection from user-supplied input:** `_prepare_order_line_values` sets `event_slot_id` from a user-supplied POST parameter via `_create_attendees_from_registration_post`. The method only checks that the record `exists()` — it does not verify the user has ACL rights to that specific slot. In practice, slot IDs are only discoverable by browsing the event page, so this is low risk.

- **Registration cancellation ordering:** `_cart_update_order_line` cancels registrations by `create_date asc` offset. A malicious user with ability to manipulate registration creation times could theoretically cancel the wrong registrations. Impractical in normal use.

### Edge Cases and Failure Modes

| Scenario | Behavior |
|---|---|
| All tickets free, no cart exists | Skips cart entirely; registrations created directly by `super()` |
| Cart with mixed free + paid tickets | Paid tickets go to checkout; free registrations still created |
| Concurrent cart adds exhausting seats | Both pass cart-level check; payment-time `_validate_transaction_for_order` catches conflict |
| User decreases qty below existing registrations | Excess registrations cancelled in `create_date asc` order |
| Ticket sold out after cart addition | Cart still shows ticket; payment fails with `ValidationError`; abandoned cart email excluded |
| Multi-slot event: same ticket type across multiple slots | Each `(slot, ticket)` pair is a separate cart line |
| `limit_max_per_order > 0` on ticket | Not enforced in `website_event_sale`; relies on `event_sale` backend logic |
| `min_quantity > 0` on pricelist for event product | Warning shown in UI but not blocked; discount simply not applied |
| Anonymous cart at checkout | Address collected from first attendee data before redirecting to checkout |
| `is_public_user()` on confirmation | Ticket access links hidden if user is not logged in (not relevant for confirmed registrations) |
| Ticket deleted after cart line is created | `_check_event_registration_ticket` in `event_sale` will fire on the next SO confirm, blocking confirmation |

---

## Extension Points

| Method | File | Signature | Purpose |
|---|---|---|---|
| `_cart_find_product_line` | `sale_order.py` | `*, event_slot_id, event_ticket_id` | Find/filter cart line by slot+ticket |
| `_verify_updated_quantity` | `sale_order.py` | `order_line, product_id, new_qty, uom_id, *, event_slot_id, event_ticket_id` | Validate seat availability |
| `_prepare_order_line_values` | `sale_order.py` | `product_id, *, event_slot_id, event_ticket_id` | Attach event/ticket IDs to order line |
| `_cart_update_order_line` | `sale_order.py` | `order_line, quantity` | Handle registration cancellation |
| `_filter_can_send_abandoned_cart_mail` | `sale_order.py` | `(self)` | Exclude sold-out carts from reminders |
| `_compute_name_short` | `sale_order_line.py` | `(self)` | Show ticket name in cart |
| `_should_show_strikethrough_price` | `sale_order_line.py` | `(self)` | Hide discount display for tickets |
| `_is_reorder_allowed` | `sale_order_line.py` | `(self)` | Block reorder of event lines |
| `_get_product_types_allow_zero_price` | `product.py` | `(self)` | Allow free event tickets |
| `_onchange_event_sale_warning` | `product_pricelist.py` | `(self)` | Warn about inapplicable pricelist rules |
| `_process_tickets_form` | `controllers/main.py` | `event, form_details` | Augment form data with price |
| `_create_attendees_from_registration_post` | `controllers/main.py` | `event, registration_data` | Pipeline registrations to cart |
| `registration_confirm` | `controllers/main.py` | `event, **post` | Final registration step |
| `_validate_transaction_for_order` | `controllers/payment.py` | `transaction, sale_order` | Hard seat check at payment |
| `_prepare_shop_payment_confirmation_values` | `controllers/sale.py` | `order` | Add event data to confirmation context |

---

## Related

- [Modules/event](Modules/event.md) — Base event management (`event.registration` lifecycle)
- [Modules/event_product](Modules/event_product.md) — Product-event linking (`service_tracking = 'event'`, `product_id` on tickets)
- [Modules/event_sale](Modules/event_sale.md) — Event ticket product type definition, SO-line event binding
- [Modules/website_event](Modules/website_event.md) — Event website pages and menus
- [Modules/website_sale](Modules/website_sale.md) — eCommerce cart and checkout flow
- [Modules/Sale](Modules/sale.md) — Sale order processing
