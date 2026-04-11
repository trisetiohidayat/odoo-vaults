---
Module: event_booth_sale
Version: 18.0.0
Type: addon
Tags: #odoo18 #event #booth #sale #registration
---

## Overview

Enables paid booth reservations for events. Links `event.booth` (and categories) to sale order lines, with a two-phase registration lifecycle: pending reservations during quoting, confirmed on SO confirmation.

**Depends:** `event_sale`, `sale`

**Key Behavior:** Booths are reserved via `event.booth.registration` records created from sale order line pending booths. On SO confirmation, registrations are confirmed and competing orders cancelled. Invoice payment marks booths as paid.

---

## Models

### `event.booth` (Inherited)

**Inherited from:** `event.booth`

| Field | Type | Note |
|-------|------|------|
| `event_booth_registration_ids` | One2many `event.booth.registration` | Pending registrations |
| `sale_order_line_registration_ids` | Many2many `sale.order.line` | SO lines with reservations |
| `sale_order_line_id` | Many2one `sale.order.line` | Final (confirmed) SO line |
| `sale_order_id` | Many2one (related) | Related SO |
| `is_paid` | Boolean | Paid flag set on invoice payment |

| Method | Returns | Note |
|--------|---------|------|
| `_unlink_except_linked_sale_order()` | — | Prevents deletion of booths linked to SO |
| `action_set_paid()` | — | Sets `is_paid=True` |
| `action_view_sale_order()` | Action | Opens linked SO form |
| `_get_booth_multiline_description()` | str | Returns `"Event: booth1\n- booth2..."` for SO line description |

### `event.booth.category` (Inherited)

**Inherited from:** `event.booth.category`

| Field | Type | Note |
|-------|------|------|
| `product_id` | Many2one `product.product` | Booth service product (service_tracking='event_booth') |
| `price` | Float | Computed from product `list_price + price_extra`; writable |
| `price_incl` | Float | Price including taxes; computed |
| `currency_id` | Many2one (related) | From product |
| `price_reduce` | Float | Discounted price; computed |
| `price_reduce_taxinc` | Float | Discounted price with tax; computed |
| `image_1920` | Image | Falls back to product image if category image absent |

| Method | Returns | Note |
|--------|---------|------|
| `_init_column(column_name)` | — | On install: auto-creates generic booth product for existing null categories |
| `_compute_price()` | — | Sets `price = product.list_price + product.price_extra` |
| `_compute_price_incl()` | — | Tax-included price via `taxes_id.compute_all` |
| `_compute_price_reduce()` | — | Contextual discount price |
| `_compute_price_reduce_taxinc()` | — | Tax-included discounted price |
| `_compute_image_1920()` | — | Falls back to product image |

### `event.type.booth` (Inherited)

**Inherited from:** `event.type.booth`

| Field | Type | Note |
|-------|------|------|
| `product_id` | Many2one (related) | Related from category |
| `price` | Float (related) | From category |
| `currency_id` | Many2one (related) | From product |

### `event.booth.registration` (New)

**Model:** `event.booth.registration`

| Field | Type | Note |
|-------|------|------|
| `sale_order_line_id` | Many2one `sale.order.line` | Source SO line |
| `event_booth_id` | Many2one `event.booth` | Target booth |
| `partner_id` | Many2one (related) | From SO line partner |
| `contact_name` | Char | From partner; writable |
| `contact_email` | Char | From partner; writable |
| `contact_phone` | Char | From partner phone/mobile; writable |

| SQL Constraint | Note |
|---------------|------|
| `unique(sale_order_line_id, event_booth_id)` | One registration per booth per SO line |

| Method | Returns | Note |
|--------|---------|------|
| `_compute_contact_*()` | — | Auto-fills from `partner_id` if field is empty |
| `action_confirm()` | — | Confirms linked booth with contact data; cancels competing registrations |
| `_cancel_pending_registrations()` | — | Posts message to competing orders and cancels them |

### `sale.order` (Inherited)

**Inherited from:** `sale.order`

| Field | Type | Note |
|-------|------|------|
| `event_booth_ids` | One2many `event.booth` | Linked booths via `sale_order_id` |
| `event_booth_count` | Integer (compute) | Count of linked booths |

| Method | Returns | Note |
|--------|---------|------|
| `action_confirm()` | — | Validates all booth lines configured; calls `_update_event_booths` |
| `action_view_booth_list()` | Action | Opens booth list filtered to this SO |
| `_get_product_catalog_domain()` | Domain | Excludes `service_tracking == 'event_booth'` products |

### `sale.order.line` (Inherited)

**Inherited from:** `sale.order.line`

| Field | Type | Note |
|-------|------|------|
| `event_booth_category_id` | Many2one `event.booth.category` | Booth category |
| `event_booth_pending_ids` | Many2many `event.booth` | Selected booths (pending) |
| `event_booth_registration_ids` | One2many `event.booth.registration` | Confirmed registrations |
| `event_booth_ids` | One2many `event.booth` | Confirmed booths |
| `is_event_booth` | Boolean (compute) | True if `product.service_tracking == 'event_booth'` |

| Method | Returns | Note |
|--------|---------|------|
| `_compute_event_booth_pending_ids()` | — | Derives from `event_booth_registration_ids` |
| `_inverse_event_booth_pending_ids()` | — | Creates/cancels registrations when pending booths change |
| `_search_event_booth_pending_ids()` | Domain | Search on pending booths |
| `_check_event_booth_registration_ids()` | — | Constrain: all registrations must be for same event |
| `_onchange_product_id_booth()` | — | Reset event if product not in pending booths |
| `_onchange_event_id_booth()` | — | Reset pending booths if event changes |
| `_update_event_booths(set_paid)` | — | Confirms booths on SO confirm; sets paid on invoice payment |
| `_get_sale_order_line_multiline_description_sale()` | str | Custom description from booth names |
| `_get_display_price()` | Monetary | Sums booth category prices |
| `_use_template_name()` | Boolean | False when booth pending (don't overwrite description) |

### `product.template` (Inherited)

**Inherited from:** `product.template`

| Field | Type | Note |
|-------|------|------|
| `service_tracking` | Selection | Adds `'event_booth'` — Booth Registration |

### `product.product` (Inherited)

**Inherited from:** `product.product`

| Method | Returns | Note |
|--------|---------|------|
| `_onchange_type_event_booth()` | — | Sets `invoice_policy='order'` when type changes to booth |

### `account.move` (Inherited)

**Inherited from:** `account.move`

| Method | Returns | Note |
|--------|---------|------|
| `_invoice_paid_hook()` | — | Calls `_update_event_booths(set_paid=True)` on paid invoice lines |

---

## Critical Notes

- **Registration Lifecycle:** `pending` → on SO confirm, `action_confirm` creates booth.registration → confirmed → competing registrations cancelled.
- **`_unlink_except_linked_sale_order`:** Uses `sudo()` because salesmen don't have direct booth access rights.
- **`_init_column`:** On module install, creates a generic booth product if existing categories have null `product_id`.
- **Competition Cancellation:** When a registration is confirmed, `_cancel_pending_registrations` cancels the entire sale order of any other registration for the same booth and posts a message listing which booths were reserved.
- **`service_tracking='event_booth'`** on product.product sets `invoice_policy='order'` automatically.
