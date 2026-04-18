---
title: Events Product
description: Bridge module linking products to event tickets, enabling registration fee pricing, invoicing, and pricelist integration for event management.
tags: [odoo19, event, product, sale, invoicing, module]
model_count: 6
models:
  - event.event (extends)
  - event.event.ticket (extends)
  - event.type.ticket (extends)
  - event.registration (extends)
  - product.template (extends)
  - product.product (extends)
dependencies:
  - event
  - product
  - account
category: Marketing/Events
source: odoo/addons/event_product/
created: 2026-04-14
uuid: e5c1a8f2-7b3d-4e9a-8f1c-2d6b0e5a8c3f
---

# Events Product

## Overview

**Module:** `event_product`
**Category:** Marketing/Events
**Depends:** `event`, `product`, `account`
**Auto-install:** True
**License:** LGPL-3
**Author:** Odoo S.A.

`event_product` is the foundational bridge module connecting Odoo's [Modules/event](event.md) and [Modules/Product](Product.md) ecosystems. It establishes the product-ticket relationship that underlies the entire event registration fee system. Without this module, event tickets cannot be priced, sold, or invoiced through Odoo's standard sales and accounting flows.

The module does not sell anything by itself; instead it provides the infrastructure that other modules like [Modules/event_sale](event_sale.md) consume. Its core responsibilities are:

1. **Product linkage** - Tie `product.product` records to `event.event.ticket` records.
2. **Pricing propagation** - Sync ticket prices from product's `lst_price` and apply tax-inclusive pricing.
3. **Service tracking extension** - Add `'event'` as a `service_tracking` option on `product.template`.
4. **Generic product** - Create a default "Event Registration" product on install for immediate use.
5. **Sale status tracking** - Compute whether a registration has been sold, is free, or awaits payment.

The dependency chain flows like this: `event` (core event model) + `product` (product master data) + `account` (currency/invoicing) → `event_product` → `event_sale` (actual sales logic).

## Module Structure

```
event_product/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── event_event.py          # Adds currency_id to event.event
│   ├── event_event_ticket.py   # Ticket pricing with tax computation
│   ├── event_type_ticket.py    # Ticket template linking to product
│   ├── event_registration.py   # Sale status computation
│   ├── product_template.py      # 'event' service tracking option
│   └── product_product.py       # event_ticket_ids + constraint
├── views/
│   ├── event_ticket_views.xml
│   └── event_registration_views.xml
└── data/
    ├── event_product_data.xml    # Default "Event Registration" product
    ├── event_product_demo.xml    # Demo product
    └── event_demo.xml            # Demo events
```

## Extended Models

### `event.event` (extends)

File: `models/event_event.py`

The `event.event` model receives a single computed field:

| Field | Type | Description |
|-------|------|-------------|
| `currency_id` | Many2one `res.currency` | Derived from `company_id.currency_id`, read-only. All ticket prices in this event are expressed in this currency. |

```python
class EventEvent(models.Model):
    _inherit = 'event.event'

    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        related='company_id.currency_id', readonly=True)
```

This field is purely informational -- it surfaces the company's currency on the event form and is used by the ticket views to display price labels consistently. Because it is `readonly=True` and `related`, no write access is granted; the currency always follows the event's `company_id`.

### `event.event.ticket` (extends)

File: `models/event_event_ticket.py`

This is the central model of the module. Each ticket is a pricing variant within an event (e.g., "Early Bird", "Regular", "VIP"). The ticket inherits its price from the linked `product_id` and enriches it with tax computations.

**New Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `price_reduce_taxinc` | Float | Tax-inclusive discounted price (lowest price after global discounts). Computed via sudo. |
| `price_incl` | Float | Full tax-inclusive price for the regular (non-reduced) price. |

**Field Changes:**

| Field | Behavior Change | Description |
|-------|----------------|-------------|
| `price` | `compute='_compute_price'` + `store=True` | When a `product_id` is set, `price` is auto-populated from `product_id.lst_price`. |
| `description` | `compute='_compute_description'` + `store=True` | Inherited from `product_id.description_sale`. |

**Computed Methods:**

```python
@api.depends('product_id')
def _compute_price(self):
    for ticket in self:
        if ticket.product_id and ticket.product_id.lst_price:
            ticket.price = ticket.product_id.lst_price or 0
        elif not ticket.price:
            ticket.price = 0
```

The `_compute_price` method runs whenever `product_id` changes. It copies the product's list price as the default ticket price, giving event managers a sensible starting point. Manual overrides are preserved unless `product_id` is changed again.

```python
@api.depends('product_id', 'price')
def _compute_price_reduce_taxinc(self):
    for event in self:
        tax_ids = event.product_id.taxes_id.filtered(
            lambda r: r.company_id == event.event_id.company_id
        )
        taxes = tax_ids.compute_all(
            event.price_reduce,
            event.event_id.company_id.currency_id,
            1.0, product=event.product_id
        )
        event.price_reduce_taxinc = taxes['total_included']
```

This computes the tax-inclusive discounted price. The discount comes from `product_id._get_contextual_discount()` which factors in active pricelist rules. The `compute_sudo=True` flag means this runs with elevated privileges so it works in the public website context.

```python
@api.depends('product_id', 'product_id.taxes_id', 'price')
def _compute_price_incl(self):
    for event in self:
        if event.product_id and event.price:
            tax_ids = event.product_id.taxes_id.filtered(
                lambda r: r.company_id == event.event_id.company_id
            )
            taxes = tax_ids.compute_all(
                event.price, event.currency_id, 1.0,
                product=event.product_id
            )
            event.price_incl = taxes['total_included']
        else:
            event.price_incl = 0
```

**`_compute_sale_available`:**

```python
@api.depends('product_id.active')
def _compute_sale_available(self):
    inactive_product_tickets = self.filtered(
        lambda ticket: not ticket.product_id.active
    )
    for ticket in inactive_product_tickets:
        ticket.sale_available = False
    super(EventEventTicket,
          self - inactive_product_tickets)._compute_sale_available()
```

If the linked product is archived (inactive), the ticket is marked unavailable for sale. This prevents orphaned registrations for products that have been deactivated.

### `event.type.ticket` (extends)

File: `models/event_type_ticket.py`

Ticket templates define default values for event tickets. The `event_type_ticket` model bridges ticket templates to products.

**New / Modified Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `product_id` | Many2one `product.product` | Required, constrained to `service_tracking = 'event'`. Defaults to the generic "Event Registration" product via `_default_product_id()`. |
| `description` | Text | Computed from `product_id.description_sale`, `store=True`, `readonly=False`. |
| `price` | Float | Computed from `product_id.lst_price`, `store=True`. |
| `price_reduce` | Float | Tax-exclusive discounted price, computed from contextual discount. |

**`_init_column` Hook:**

```python
def _init_column(self, column_name):
    if column_name != "product_id":
        return super()._init_column(column_name)

    self.env.cr.execute(
        "SELECT id FROM %s WHERE product_id IS NULL" % self._table
    )
    ticket_type_ids = self.env.cr.fetchall()
    if not ticket_type_ids:
        return

    default_event_product = self.env.ref(
        'event_product.product_product_event', raise_if_not_found=False
    )
    if default_event_product:
        product_id = default_event_product.id
    else:
        product_id = self.env['product.product'].create({
            'name': 'Generic Registration Product',
            'list_price': 0,
            'standard_price': 0,
            'type': 'service',
        }).id
        self.env['ir.model.data'].create({
            'name': 'product_product_event',
            'module': 'event_product',
            'model': 'product.product',
            'res_id': product_id,
        })

    self.env.cr.execute(
        f'UPDATE {self._table} SET product_id = %s WHERE id IN %s;',
        (product_id, tuple(ticket_type_ids))
    )
```

This is a low-level database hook that runs once during module installation. It retroactively assigns the default event registration product to any ticket type records that somehow have a null `product_id`. This handles edge cases where data migration creates orphaned records.

**`_get_event_ticket_fields_whitelist`:**

```python
@api.model
def _get_event_ticket_fields_whitelist(self):
    return super()._get_event_ticket_fields_whitelist() + ['product_id', 'price']
```

This method returns fields that should be copied from the ticket template to individual event tickets when an event is created from a template. By adding `product_id` and `price`, Odoo ensures the product linkage is preserved when events are created from templates.

### `event.registration` (extends)

File: `models/event_registration.py`

The registration model gains a computed `sale_status` field that describes the commercial state of a registration.

| Field | Type | Description |
|-------|------|-------------|
| `sale_status` | Selection | One of `'to_pay'` (Not Sold), `'sold'` (Sold), `'free'` (Free). Computed with `compute_sudo=True`. The `_has_order()` method returns `False` by default; `event_sale` overrides it to check for linked sale order lines. |

```python
def _compute_registration_status(self):
    if not self._has_order():
        for reg in self:
            if not reg.sale_status:
                reg.sale_status = 'free'
            if not reg.state:
                reg.state = 'open'
```

When no sale order is linked (the base case), registrations default to `'free'` status. The `_has_order()` hook is designed to be overridden by `event_sale` which provides the actual sale order integration.

**Why this matters:** Event managers can see at a glance which attendees have paid, which are awaiting payment, and which attended without charge. The `sale_status` field is visible in the registration kanban view and list view, enabling efficient check-in workflows.

### `product.template` (extends)

File: `models/product_template.py`

The product template receives a new `service_tracking` option and a blacklist entry.

**Modified Fields:**

| Field | Change | Description |
|-------|--------|-------------|
| `service_tracking` | Added `'event'` option | When selected, Odoo creates service lines for event registration. `ondelete='set default'` resets to the default when the product category is deleted. |

```python
def _service_tracking_blacklist(self):
    return super()._service_tracking_blacklist() + ['event']
```

This method returns model names that should be excluded from automatic service tracking. Adding `'event'` to the blacklist means event products are not automatically linked to project tasks or manufacturing orders through the standard service tracking mechanism.

### `product.product` (extends)

File: `models/product_product.py`

The product product model gets a one2many to tickets and a validation constraint.

**New Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `event_ticket_ids` | One2many `event.event.ticket` | All event tickets that use this product as their registration product. |

**Validation Constraint:**

```python
@api.constrains('event_ticket_ids', 'service_tracking')
def _check_event_ticket_service_tracking(self):
    for product in self:
        if product.event_ticket_ids and product.service_tracking != 'event':
            raise ValidationError(_(
                'Products linked to an event ticket must have "%(tracking)s" '
                'set to "%(event)s".',
                tracking=service_tracking['string'],
                event=dict(service_tracking['selection'])['event'],
            ))
```

This constraint enforces data integrity: any product that appears in `event_ticket_ids` must have `service_tracking = 'event'`. The inverse is not enforced -- you can have `service_tracking = 'event'` with no tickets. The constraint fires on write and create.

## Data Files

### `event_product_data.xml`

On first install (`noupdate="1"`), the module creates:

1. **Product Category:** `Events` under `product_category_services`.
2. **Generic Product:** `product_product_event` -- "Event Registration" service product:
   - `list_price`: 30.0
   - `standard_price`: 10.0
   - `type`: `service`
   - `service_tracking`: `event`
   - Category: `Events`

This gives users a ready-to-use registration product immediately after installing the module.

## Business Flow

The event-product lifecycle works as follows:

```
1. Event Manager creates an Event Type (event.type)
   └── Adds ticket templates (event.type.ticket)
       └── Each template links to a product.product
           └── product.service_tracking = 'event'

2. Event Manager creates an Event from the Type
   └── Odoo creates event.event.ticket records for each template
       └── price is auto-populated from product.lst_price
       └── description is auto-populated from product.description_sale

3. Website visitor / Attendee registers for event
   └── event.registration created with sale_status = 'free'
       └── (event_sale overrides _has_order to link to sale.order.line)

4. After payment (event_sale flow):
   └── sale_status transitions to 'sold'
   └── Account move created for invoicing (via account module)
```

## Cross-Module Dependencies

| Module | Role | Integration Point |
|--------|------|-------------------|
| [Modules/event](event.md) | Core event model | Extended by `event_product` |
| [Modules/Product](Product.md) | Product master data | `product.product` and `product.template` are extended |
| [Modules/event_sale](event_sale.md) | Actual sales | Consumes `event_product`; overrides `_has_order()` |
| [Modules/account](Account.md) | Accounting/currency | `event.event.currency_id` uses `account.account` currency |

## Security

The module does not define its own access control records. It relies on the ACLs of the models it extends:

- `event.event.ticket`: Inherits from `event` module ACLs
- `product.product`: Inherits from `product` module ACLs
- `event.registration`: Inherits from `event` module ACLs

Users need at least read access to `product.product` and `event.event` to use ticket pricing features.

## Extension Points

| Extension Point | How to Extend |
|-----------------|---------------|
| Default event product | Inherit `_default_product_id()` on `event.type.ticket` to provide a different default product |
| Price computation | Override `_compute_price()` on `event.event.ticket` to add custom pricing logic |
| Tax computation | Override `_compute_price_incl()` to use a different tax set or rounding |
| Sale status logic | Override `_has_order()` on `event.registration` (as `event_sale` does) |
| Service tracking | Override `_service_tracking_blacklist()` to add or remove models from the blacklist |

## Related

- [Modules/event](event.md) -- Core event management (talks, tracks, multi-day scheduling)
- [Modules/event_sale](event_sale.md) -- Selling event tickets via e-commerce and sales orders
- [Modules/event_sms](event_sms.md) -- SMS reminders for event registrations
- [Modules/event_mail](event_mail.md) -- Email scheduling for events
- [Modules/Product](Product.md) -- Product master data and pricing
