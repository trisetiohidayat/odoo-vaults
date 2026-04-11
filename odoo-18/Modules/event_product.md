---
Module: event_product
Version: 18.0.0
Type: addon
Tags: #odoo18 #event #product #sale
---

## Overview

Bridges event tickets with product management. Links tickets to products (via `service_tracking='event'`), computes tax-included ticket prices, and propagates product/price fields from ticket types to event tickets.

**Depends:** `event`, `sale`

**Key Behavior:** Ticket `price` is derived from the linked product's `list_price`. Tax-included prices are computed on the ticket. A generic registration product is auto-created for existing ticket types on module install.

---

## Models

### `event.event` (Inherited)

**Inherited from:** `event.event`

| Field | Type | Note |
|-------|------|------|
| `currency_id` | Many2one `res.currency` | Related to `company_id.currency_id` |

### `event.event.ticket` (Inherited)

**Inherited from:** `event.event.ticket`

| Field | Type | Note |
|-------|------|------|
| `price_reduce_taxinc` | Float (compute) | Discounted price including taxes |
| `price_incl` | Float (compute) | Full price including taxes |

| Method | Returns | Note |
|--------|---------|------|
| `_compute_sale_available()` | — | Marks ticket unavailable if `product_id.active=False` |
| `_compute_price_reduce_taxinc()` | — | Tax-included discounted price via `taxes_id.compute_all` |
| `_compute_price_incl()` | — | Tax-included price via `taxes_id.compute_all` |

### `event.type.ticket` (Inherited)

**Inherited from:** `event.type.ticket`

| Field | Type | Note |
|-------|------|------|
| `description` | Text | Copy of product's `description_sale` |
| `product_id` | Many2one `product.product` | Registration product (domain: `service_tracking='event'`) |
| `currency_id` | Many2one (related) | From product |
| `price` | Float (compute) | Derives from `product_id.lst_price`; writable |
| `price_reduce` | Float (compute) | Contextual discount price |

| Method | Returns | Note |
|--------|---------|------|
| `_compute_price()` | — | Sets `price = product.lst_price` |
| `_compute_description()` | — | Copies `product.description_sale` |
| `_compute_price_reduce()` | — | Contextual discount |
| `_init_column(column_name)` | — | On install: creates generic registration product for null columns |
| `_get_event_ticket_fields_whitelist()` | list | Adds `product_id`, `price` to copy whitelist |

### `product.product` (Inherited)

**Inherited from:** `product.product`

| Field | Type | Note |
|-------|------|------|
| `event_ticket_ids` | One2many `event.event.ticket` | Tickets using this product |

### `product.template` (Inherited)

**Inherited from:** `product.template`

| Field | Type | Note |
|-------|------|------|
| `service_tracking` | Selection | Adds `'event'` — Event Registration |

| Method | Returns | Note |
|--------|---------|------|
| `_service_tracking_blacklist()` | list | Adds `'event'` to blacklist |
