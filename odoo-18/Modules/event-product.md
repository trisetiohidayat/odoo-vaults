---
Module: event_product
Version: Odoo 18
Type: Integration
Tags: #odoo #odoo18 #event #product #ticketing #inventory
---

# event_product — Event Ticket Products

**Module:** `event_product`
**Addon Path:** `odoo/addons/event_product/`
**Depends:** `event`, `product`, `account`
**Category:** Marketing/Events
**Auto-install:** Yes (with `event`, `product`, `account`)
**License:** LGPL-3

Bridges event tickets with the product and accounting system. Links `event.event.ticket` to `product.product` records, enabling tax-inclusive pricing computation and the standard product invoicing workflow for event registrations.

---

## Architecture

```
product (base)
  product.template   — service_tracking = 'event' option added here
  product.product   — event_ticket_ids (One2many back-link)

event (base)
  event.event       — currency_id (Many2one→res.currency, related to company)
  event.event.ticket — price, product_id
  event.type.ticket — price, product_id (template for tickets)

event_product (this module)
  product.template   + service_tracking option: 'event' → Event Registration
  product.product   + event_ticket_ids One2many → event.event.ticket
  event.event       + currency_id (related to company_id.currency_id)
  event.event.ticket + price_incl, price_reduce_taxinc, sale_available override
  event.type.ticket + product_id, price, price_reduce, description, currency_id
```

---

## Models Extended

### `product.template` — Product Template (EXTENDED)

Inherits from `product.product.template` (from the `product` module).

#### Field Changes

**`service_tracking` — Selection extended**

```python
service_tracking = fields.Selection(selection_add=[
    ('event', 'Event Registration'),
], ondelete={'event': 'set default'})
```

| Value | Behavior |
|-------|----------|
| `('no', 'Nothing')` | Default. No tracking. |
| `('order', 'Invoice')` | Create an invoice. |
| `('order_point', 'Invoice + DDT')` | Create invoice and delivery. |
| `('task', 'Project')` | Create task in project. |
| `('project_only', 'Project Only')` | Create project only. |
| `('event', 'Event Registration')` | **Added by this module.** Link to event. |

**`ondelete='event': 'set default'`**: When a product with `service_tracking='event'` is deleted, its `product_variant_ids` are reset to a default fallback product instead of cascade-deleting variants.

#### Method Changes

**`_prepare_service_tracking_tooltip()`** — Not overridden in this module (handled by `event_sale`).
- `event_sale` adds a tooltip explaining that linking a product to an event ticket creates registrations when the sale order is confirmed.

**`_service_tracking_blacklist()`** — Extended

```python
def _service_tracking_blacklist(self):
    return super()._service_tracking_blacklist() + ['event']
```

Adds `'event'` to the service-tracking blacklist for `sale.order` product picking. This prevents event registration products from being selected in the standard product catalog on a sale order (they are selected via the event ticket UI instead).

---

### `product.product` — Product Product (EXTENDED)

Inherits from `product.product` (from the `product` module).

#### Fields Added

| Field | Type | Relation | Description |
|-------|------|----------|-------------|
| `event_ticket_ids` | One2many | `event.event.ticket` → `product_id` | All event tickets that use this product as their sale item |

#### Key Notes

- This is the inverse side of the Many2one on `event.event.ticket` (`product_id`)
- Allows a product to be shared across multiple event tickets (e.g., a "General Admission" ticket product used across multiple events)
- When a product is archived (`active=False`), the `sale_available` compute on `event.event.ticket` sets the ticket unavailable via `_compute_sale_available()`

---

### `event.event` — Event (EXTENDED)

Inherits from `event.event` (from the `event` module).

#### Fields Added

| Field | Type | Relation | Description |
|-------|------|----------|-------------|
| `currency_id` | Many2one | `res.currency` | Related to `company_id.currency_id`, readonly |

#### Key Notes

- Currency is derived from the event's company, not from the product
- Used as the currency context when computing `event.event.ticket` prices (see `_compute_price_incl` on `event.event.ticket`)
- Allows events from different companies to price tickets in their respective currencies

---

### `event.type.ticket` — Event Type Ticket Template (EXTENDED)

Inherits from `event.type.ticket` (`event/models/event_ticket.py`). Provides template defaults when an event type is applied to an event.

#### Fields Added / Overridden

| Field | Type | Description |
|-------|------|-------------|
| `product_id` | Many2one `product.product` | **Required field.** Domain: `service_tracking == 'event'`. Defaults to `product_product_event` (generic registration product via XML-Ref). |
| `currency_id` | Many2one `res.currency` | Related to `product_id.currency_id` |
| `price` | Float | **Compute** from `product_id.lst_price`. `store=True, readonly=False`. |
| `price_reduce` | Float | **Compute** from `product_id` contextual discount. `compute_sudo=True`. |
| `description` | Text | **Compute** from `product_id.description_sale`. `store=True, readonly=False`. |

#### Methods

**`_default_product_id()`** — `api.model`
- Returns `self.env.ref('event_product.product_product_event')` (the generic registration product)
- Falls back to `False` if the XML-Ref is not found

**`_compute_price()`** — `api.depends('product_id')`
- Sets `price = product_id.lst_price` if a product is set
- If no product is set and price is 0, keeps price at 0
- Since `readonly=False, store=True`, the computed price can still be manually overridden

**`_compute_description()`** — `api.depends('product_id')`
- Copies `product_id.description_sale` to the ticket description
- Initialises to `False` for embedded tree views where product is not yet set

**`_compute_price_reduce()`** — `api.depends('product_id', 'price')` + `PRICE_CONTEXT_KEYS`
- Uses `product_id._get_contextual_discount()` to apply current pricelist/contextual discount
- `price_reduce = (1.0 - contextual_discount) * price`

**`_init_column(column_name)`** — `api.model`
- Migration helper: when the module is installed on an existing database with null `product_id` values
- Creates a generic "Generic Registration Product" product via `product_product_event` XML-Ref
- Backfills all existing null `product_id` columns with the default product ID

**`_get_event_ticket_fields_whitelist()`** — `api.model`
- Returns `['sequence', 'name', 'description', 'seats_max']` + `['product_id', 'price']`
- Extends the parent whitelist: both `product_id` and `price` are now copied when an event type's ticket template is applied to create event tickets

#### Key Notes

- `product_id` is a **required** field on `event.type.ticket` (unlike on `event.event.ticket` where it can be left empty)
- The product's `service_tracking` must equal `'event'` (enforced by domain)
- This model is primarily a template that feeds defaults into `event.event.ticket`

---

### `event.event.ticket` — Event Ticket (EXTENDED)

Inherits from `event.event.ticket` (`event/models/event_ticket.py`), which itself inherits from `event.type.ticket`.

#### Fields Added / Overridden

| Field | Type | Description |
|-------|------|-------------|
| `price_reduce_taxinc` | Float (computed) | Price after discount, including taxes. `compute_sudo=True`. |
| `price_incl` | Float (computed, writable) | Full price including taxes. `readonly=False, compute_sudo=True`. |

#### Methods

**`_compute_sale_available()`** — `api.depends('product_id.active')` (override)

```python
def _compute_sale_available(self):
    inactive_product_tickets = self.filtered(lambda ticket: not ticket.product_id.active)
    for ticket in inactive_product_tickets:
        ticket.sale_available = False
    super(EventTicket, self - inactive_product_tickets)._compute_sale_available()
```

Purpose: If a ticket's linked product is archived (`active=False`), the ticket is immediately unavailable for sale. The parent compute checks expiration and seat limits.

**`_compute_price_reduce_taxinc()`** — `api.depends('product_id', 'price_reduce')`

```python
for event in self:
    tax_ids = event.product_id.taxes_id.filtered(lambda r: r.company_id == event.event_id.company_id)
    taxes = tax_ids.compute_all(event.price_reduce, event.event_id.company_id.currency_id, 1.0, product=event.product_id)
    event.price_reduce_taxinc = taxes['total_included']
```

- Computes the tax-inclusive price after applying the contextual (pricelist) discount
- Filters taxes to only those matching the event's company
- Used on e-commerce/product configurator to show the final customer-facing price

**`_compute_price_incl()`** — `api.depends('product_id', 'product_id.taxes_id', 'price')`

```python
for event in self:
    if event.product_id and event.price:
        tax_ids = event.product_id.taxes_id.filtered(lambda r: r.company_id == event.event_id.company_id)
        taxes = tax_ids.compute_all(event.price, event.currency_id, 1.0, product=event.product_id)
        event.price_incl = taxes['total_included']
    else:
        event.price_incl = 0
```

- Computes the list price inclusive of taxes
- `event.currency_id` comes from the `event_product`-added related field on `event.event`
- Used when displaying the ticket price in event forms and e-commerce

---

## L4: How Event Product Integration Works

### Product-to-Ticket Link

```
product.product (service_tracking='event')
  └─ event_ticket_ids[] → event.event.ticket
        └─ event_id → event.event
              └─ event_type_id → event.type
                    └─ event_type_ticket_ids[] (template)
```

The chain is:
1. `product.product` with `service_tracking = 'event'` is the saleable item
2. `event.event.ticket` has a required `product_id` pointing to that product
3. The ticket inherits the product's price, description, and tax configuration
4. When sold via `event_sale`, the `sale.order.line` with `service_tracking='event'` uses the product and ticket

### Tax Price Computation Flow

```
product.product.taxes_id  (e.g., tax_ids = [tax_22%])
        ↓
event.event.ticket.price (lst_price from product or manually overridden)
        ↓
event.event.currency_id  (from event.company_id.currency_id)
        ↓
taxes_id.compute_all(price, currency, qty=1.0, product=product)
        ↓
price_incl / price_reduce_taxinc
```

### Default Product Migration

On first install, `_init_column` ensures every existing `event_type_ticket` record gets a `product_id` without requiring a migration script. This is a common Odoo pattern for safely adding required fields to existing databases.

### Comparison with event_booth_sale

`event_product` links tickets (registrations) to products, while `event_booth_sale` links booths (physical spaces) to products. Both share the pattern: product → service_tracking option, product_id on the event sub-model, price compute from product.

---

## See Also

- [Core/API](API.md) — @api.depends, @api.onchange, @api.constrains
- [Modules/Stock](stock.md) — event tickets as inventory
- `event_sale` — sale.order integration (creates registrations from ticket sales)
- `event_booth_sale` — booth sales (booth categories linked to products)
