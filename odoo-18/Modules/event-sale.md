---
Module: event_sale
Version: Odoo 18
Type: Integration
Tags: [event, sale, registration, ticket, orm]
---

# event_sale — Event Ticketing and Sale Order Integration

## Overview

**Addon key:** `event_sale`
**Depends:** `event_product`, `sale_management`
**Auto-install:** `True`
**Source path:** `~/odoo/odoo18/odoo/addons/event_sale/`

This module bridges event registration and sale order workflows. It allows event tickets to be sold as products via sale orders, automatically creating `event.registration` records upon SO confirmation. It does NOT manage seat inventory directly — seat capacity is enforced by the `event` module's `seats_available` / ` seats_max` fields on `event.event`.

**Key insight:** There is no `event.sale.order.line.mixin` model in Odoo 18. The mixin-like behavior (linking a sale order line to an event) is implemented directly on `sale.order.line` via the `event_id` and `event_ticket_id` computed/writable fields.

---

## Module Map

```
event_sale
├── models/
│   ├── event_registration.py      ← sale_status compute, UTM sync, SO link
│   ├── event_event.py            ← sale_order_lines_ids, sale_price_subtotal
│   ├── event_ticket.py           ← _get_ticket_multiline_description override
│   ├── sale_order.py             ← action_confirm triggers _init_registrations
│   ├── sale_order_line.py        ← event_id, event_ticket_id, registration_ids
│   ├── product_template.py       ← invoice_policy='order' when service_tracking='event'
│   └── __init__.py
├── wizard/
│   ├── event_configurator.py     ← event/ticket selection wizard on product config
│   └── event_edit_registration.py
└── data/
    └── event_sale_data.xml       ← default values, SMS templates
```

---

## Model: `event.registration` (extends base `event.registration`)

**File:** `models/event_registration.py`
**Inheritance:** `_inherit = 'event.registration'`

Extends the base registration model with sale-order linkage, sale status tracking, and UTM attribution.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `sale_order_id` | `Many2one(sale.order)` | Ondelete cascade. Links registration to the originating SO |
| `sale_order_line_id` | `Many2one(sale.order.line)` | Ondelete cascade. Links to specific SO line |
| `sale_status` | `Selection` (compute+store) | `to_pay` / `sold` / `free`. Precompute=True |
| `state` | `Selection` (compute override) | Overrides base `state` to sync with SO lifecycle |
| `utm_campaign_id` | `Many2one(utm.campaign)` | Computed from `sale_order_id.campaign_id` |
| `utm_source_id` | `Many2one(utm.source)` | Computed from `sale_order_id.source_id` |
| `utm_medium_id` | `Many2one(utm.medium)` | Computed from `sale_order_id.medium_id` |

### `sale_status` Compute — `_compute_registration_status`

This is the core status logic. It groups registrations by their `sale_order_id` and evaluates the SO's state and `amount_total`:

```
SO state = 'cancel'              → registration.state = 'cancel'
SO amount_total = 0 (float_is_zero) → sale_status = 'free'
                                      state = 'open' (if was draft or unset)
SO state = 'sale' (and not cancel) → sale_status = 'sold'
                                      state = 'open' (if was draft or cancel)
SO in draft (not yet sale)       → sale_status = 'to_pay'
                                      state = 'draft'
No SO linked                     → sale_status = 'free', state = 'open'
```

The `float_is_zero` comparison uses `sale_order.currency_id.rounding` as precision, making it currency-aware.

### Key Methods

**`_synchronize_so_line_values(so_line)`**
Called on both `create()` and `write()`. When a `sale_order_line_id` is set, it propagates:
- `partner_id` — skips for public users who are the SO contact (portal flow guard)
- `event_id` — from `so_line.event_id`
- `event_ticket_id` — from `so_line.event_ticket_id`
- `sale_order_id` / `sale_order_line_id`

**`_sale_order_ticket_type_change_notify(new_event_ticket)`**
If someone changes `event_ticket_id` on a registration that already has a sale order, schedules an activity on the SO using the `event_sale.event_ticket_id_change_exception` view template. The responsible user is the event's `user_id`, or failing that the SO's `user_id`, or `base.user_admin`.

**`_get_registration_summary()`**
Extends the base registration summary dict with `sale_status`, translated `sale_status_value`, and `has_to_pay` boolean.

---

## Model: `sale.order.line`

**File:** `models/sale_order_line.py`
**Inheritance:** `_inherit = 'sale.order.line'`

### Fields Added

| Field | Type | Notes |
|-------|------|-------|
| `event_id` | `Many2one(event.event)` | Compute+store+readonly+precompute. Set when `product_id.service_tracking == 'event'` |
| `event_ticket_id` | `Many2one(event.event.ticket)` | Compute+store+readonly+precompute. Reset when `event_id` changes |
| `registration_ids` | `One2many(event.registration)` | `sale_order_line_id` inverse |

### `_compute_event_id`

Only triggered when `product_id.service_tracking == 'event'`. Clears `event_id` if the current product is not in `line.event_id.event_ticket_ids.product_id`.

### `_compute_event_ticket_id`

Resets `event_ticket_id` whenever `event_id` changes (since the ticket must belong to the event).

### `_init_registrations()`

Core registration-creation method. Called by `sale.order.action_confirm()`:

```
for so_line in self:
    if so_line.service_tracking != 'event':
        continue
    registrations_to_create = int(product_uom_qty) - existing_registration_count
    for _count in range(registrations_to_create):
        create {sale_order_line_id, sale_order_id}
```

Registrations are created via `sudo()` to bypass record rules during SO confirmation. This is idempotent — re-running after partial registrations only creates the delta.

### Constraint — `_check_event_registration_ticket`

`@api.constrains` validates that any SO line with `service_tracking == 'event'` must have BOTH `event_id` AND `event_ticket_id` set.

### Display Price — `_get_display_price()`

When an `event_ticket_id` is set, price is sourced from the ticket (applying the pricelist context) rather than the product. This allows event tickets with independent pricing.

### Description — `_get_sale_order_line_multiline_description_sale`

If `event_ticket_id` is set, uses `event_ticket_id._get_ticket_multiline_description()` for the SO line name (which includes product sale description + event display name). Otherwise falls back to product description.

---

## Model: `sale.order`

**File:** `models/sale_order.py`
**Inheritance:** `_inherit = 'sale.order'`

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `attendee_count` | `Integer` (compute) | Non-cancelled registrations linked to this SO |

### `action_confirm()` — Registration Lifecycle Trigger

```python
def action_confirm(self):
    # 1. Collect unconfirmed registrations BEFORE super() runs
    unconfirmed_registrations = self.order_line.registration_ids.filtered(
        lambda reg: reg.state in ["draft", "cancel"]
    )
    # 2. Call super() — triggers sale.order.confirm logic
    res = super().action_confirm()
    # 3. Update mail schedulers on previously-draft registrations
    unconfirmed_registrations._update_mail_schedulers()
    # 4. Validate all event lines have event_id + ticket set
    #    raises ValidationError if not
    # 5. Create registrations for all event lines
    so.order_line._init_registrations()
```

The `unconfirmed_registrations` collection captures registrations already in draft before SO confirmation, then `_update_mail_schedulers()` is called after super, ensuring that registrations created by `_init_registrations()` also get mail schedulers (they start as 'open' after super confirms the SO).

### `write()` — Partner Sync to Registrations

When `partner_id` changes on an SO and any line has `service_tracking == 'event'`, all its registrations get their `partner_id` updated to the new SO partner. This handles the "shop/address" website flow.

### `_notify_get_recipients_groups()` — Portal Ticket Button

When a confirmed SO has registration records, adds a "Get Your Tickets" portal button. The URL is `/event/{event.id}/my_tickets` with a signed hash of registration IDs for access control.

### `_get_product_catalog_domain()` — Catalog Filtering

Removes `service_tracking == 'event'` products from the product catalog picker in sale orders (events are selected via specific event picker, not the standard product line).

---

## Model: `event.event` (extends)

**File:** `models/event_event.py`
**Inheritance:** `_inherit = 'event.event'`

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `sale_order_lines_ids` | `One2many(sale.order.line)` | All SO lines for this event. Group: sales_team |
| `sale_price_subtotal` | `Monetary` (compute) | Total sold revenue for this event |

### `_compute_sale_price_subtotal`

Aggregates all `price_subtotal` from linked SO lines (non-cancelled SOs). Performs real-time currency conversion from each SO's currency to the event's `company_id.currency_id` using current rates (not historical rates). This is a design choice: revenue "as of today" rather than "as of order date".

---

## Model: `event.event.ticket` (extends)

**File:** `models/event_ticket.py`
**Inheritance:** `_inherit = 'event.event.ticket'`

### `_get_ticket_multiline_description()`

Overrides the base ticket method: if the ticket's product has a `description_sale`, prepends it to the ticket description (product description has priority over ticket name in SO line descriptions).

---

## Model: `product.template` (extends)

**File:** `models/product_template.py`
**Inheritance:** `_inherit = 'product.template'`

### `_onchange_type_event()`

When `service_tracking` is set to `'event'`, automatically sets `invoice_policy = 'order'`. This ensures tickets are invoiced based on ordered quantity, not delivered quantity — standard for event registrations.

### `_prepare_service_tracking_tooltip()`

Returns `"Create an Attendee for the selected Event."` as the tooltip for `service_tracking == 'event'` products.

---

## L4: Seat Reservation vs. Confirmed Registration

**There is NO seat decrement in `event_sale` itself.** Seat management is entirely in the `event` module:

- `event.event.seats_max` — maximum capacity
- `event.event.seats_available` — computed as `seats_max - count(active registrations)`
- When a registration is created and confirmed (`state = 'open'`), the event's `seats_available` decreases
- `event_sale` does NOT add any specific seat decrement logic

**Flow for ticket purchase:**
1. SO created with event-line product (qty = number of tickets)
2. SO confirmed → `_init_registrations()` creates registrations (state=draft before super, then `action_confirm` via super sets them to 'open')
3. `_update_mail_schedulers()` called on previously-draft registrations
4. Registrations reaching `state='open'` automatically decrement event seat count (event module logic)

**On SO cancellation:**
- `_compute_registration_status()` sets registration `state = 'cancel'` when `sale_order_id.state == 'cancel'`
- Cancelled registrations release seat capacity (event module behavior)
- No automatic seat release happens at SO cancellation — it happens when registration state transitions to 'cancel'

---

## Flow Diagram

```
sale.order.line (service_tracking='event')
         │
         │ _init_registrations()
         ▼
  event.registration (state='draft')
         │
    action_confirm() on sale.order
         │
         ├─ super().action_confirm() → sale_order.state = 'sale'
         │
         ├─ _update_mail_schedulers() (pre-existing draft registrations)
         │
         ├─ validate event_id + ticket_id present
         │
         └─ _init_registrations() → create missing registrations
                    │
                    ▼
             state='draft' → 'open' (event module trigger)
                    │
         sale_status = 'to_pay' / 'sold' / 'free'
                    │
         utm_campaign_id / source_id / medium_id synced from SO
```

---

## Relations Summary

| From | To | O2M / M2O | Via |
|------|----|-----------|-----|
| `sale.order.line` | `event.registration` | O2M | `registration_ids` |
| `event.registration` | `sale.order` | M2O | `sale_order_id` |
| `event.registration` | `sale.order.line` | M2O | `sale_order_line_id` |
| `event.registration` | `utm.campaign` | M2O | `utm_campaign_id` (compute) |
| `event.event` | `sale.order.line` | O2M | `sale_order_lines_ids` |
| `event.event` | `sale.order` | indirect | via `sale_order_lines_ids.order_id` |
| `mailing.contact` | `mailing.list` | M2M | `mailing_subscription` |

---

## See Also

- [Modules/Event](event.md) — base event module (registration states, seat management, mail schedulers)
- [Modules/Sale](sale.md) — sale order confirmation flow
- [Core/API](API.md) — `@api.depends`, `@api.constrains`
