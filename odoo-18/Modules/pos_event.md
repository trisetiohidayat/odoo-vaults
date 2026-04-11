---
Module: pos_event
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_event #event #ticketing #pos
---

## Overview

Enables selling event tickets at the Point of Sale. Integrates `event` module with POS — cashiers can sell event tickets, register attendees, and print badges/tickets directly from POS.

**Depends:** `point_of_sale`, `event`

---

## Models

### `event.event` (Extension)
**Inheritance:** `event.event`, `pos.load.mixin`

| Field | Type | Notes |
|---|---|---|
| `image_1024` | Image | PoS-specific image, max 1024x1024 |

**Methods:**
- `_load_pos_data_domain(data)` -> `event_ticket_ids` in data['event.event.ticket']['data']
- `_load_pos_data_fields(config_id)` -> `['id', 'name', 'seats_available', 'event_ticket_ids', 'registration_ids', 'seats_limited', 'write_date', 'question_ids', 'general_question_ids', 'specific_question_ids', 'badge_format']`

---

### `event.event.ticket` (Extension)
**Inheritance:** `event.event.ticket`, `pos.load.mixin`

**Methods:**
- `_load_pos_data_domain(data)` -> filters by:
  - `event_id.is_finished = False`
  - `event_id.company_id = config.company_id`
  - `product_id` in loaded products
  - AND `(end_sale_datetime >= now OR end_sale_datetime = False)`
  - AND `(start_sale_datetime <= now OR start_sale_datetime = False)`
- `_load_pos_data_fields(config_id)` -> `['id', 'name', 'event_id', 'seats_used', 'seats_available', 'price', 'product_id', 'seats_max', 'start_sale_datetime', 'end_sale_datetime']`

---

### `event.question` (Extension)
**Inheritance:** `event.question`, `pos.load.mixin`

**Methods:**
- `_load_pos_data_domain(data)` -> `event_id in [event_ids]`
- `_load_pos_data_fields(config_id)` -> `['title', 'question_type', 'event_type_id', 'event_id', 'sequence', 'once_per_order', 'is_mandatory_answer', 'answer_ids']`

---

### `event.question.answer` (Extension)
**Inheritance:** `event.question.answer`, `pos.load.mixin`

**Methods:**
- `_load_pos_data_domain(data)` -> `question_id in [question_ids]`
- `_load_pos_data_fields(config_id)` -> `['question_id', 'name', 'sequence']`

---

### `event.registration` (Extension)
**Inheritance:** `event.registration`, `pos.load.mixin`

| Field | Type | Notes |
|---|---|---|
| `pos_order_id` | Many2one `pos.order` | Related via `pos_order_line_id` |
| `pos_order_line_id` | Many2one `pos.order.line` | Ondelete cascade, copy=False |

**Methods:**
- `_load_pos_data_domain(data)` -> `False` (no pre-existing registrations loaded into POS)
- `_load_pos_data_fields(config_id)` -> `['id', 'event_id', 'event_ticket_id', 'pos_order_line_id', 'pos_order_id', 'phone', 'email', 'name', 'company_name', 'registration_answer_ids', 'registration_answer_choice_ids', 'write_date']`
- `create(vals_list)` -> calls `_update_available_seat()` after super
- `write(vals)` -> calls `_update_available_seat()` after super
- `_update_available_seat()` -> sudo-searches all open pos.sessions and calls `config_id._update_events_seats(self.event_id)` to broadcast seat availability updates

---

### `event.registration.answer` (Extension)
**Inheritance:** `event.registration.answer`, `pos.load.mixin`

**Methods:**
- `_load_pos_data_domain(data)` -> `False`
- `_load_pos_data_fields(config_id)` -> `['question_id', 'registration_id', 'value_answer_id', 'value_text_box', 'partner_id', 'write_date', 'event_id']`

---

### `pos.config` (Extension)
**Inheritance:** `pos.config`

**Methods:**
- `_update_events_seats(events)` -> builds seat availability data per event/ticket and sends `UPDATE_AVAILABLE_SEATS` notification to all POS clients via `_notify`

---

### `pos.session` (Extension)
**Inheritance:** `pos.session`

**Methods:**
- `_load_pos_data_models(config_id)` -> adds: `'event.event.ticket'`, `'event.event'`, `'event.registration'`, `'event.question'`, `'event.question.answer'`, `'event.registration.answer'`
- `_load_pos_data_relations(model, response)` -> for `event.registration`: forces `compute=False` on `email`, `phone`, `name`, `company_name` relations to prevent frontend from sending these back as modified

---

### `pos.order` (Extension)
**Inheritance:** `pos.order`

| Field | Type | Notes |
|---|---|---|
| `attendee_count` | Integer | Compute: count of `lines.event_registration_ids` |

**Computed:** `_compute_attendee_count` -> `len(order.lines.mapped('event_registration_ids'))`

**Methods:**
- `action_view_attendee_list()` -> returns `event.event_registration_action_tree` action with domain `('pos_order_id', 'in', self.ids)`
- `read_pos_data(data, config_id)` -> for paid/done/invoiced orders: reads related event registrations, events, tickets, answers; triggers `action_send_badge_email()` per registration
- `_process_order(order, existing_order)` -> handles refund: if refunded orderline has event registrations, cancels corresponding registrations proportional to refund qty
- `print_event_tickets()` -> calls `event.action_report_event_registration_full_page_ticket` for all registration lines
- `print_event_badges()` -> calls `event.action_report_event_registration_badge` for all registration lines

---

### `pos.order.line` (Extension)
**Inheritance:** `pos.order.line`

| Field | Type | Notes |
|---|---|---|
| `event_ticket_id` | Many2one `event.event.ticket` | Event ticket sold on this line |
| `event_registration_ids` | One2many `event.registration` | Reverse of `pos_order_line_id` |

**Methods:**
- `_load_pos_data_fields(config_id)` -> adds `event_ticket_id`, `event_registration_ids`

---

## Security / Data

**ir.model.access.csv:** (from security/ir.model.access.csv)
Standard PO S user/manager access for all event models used in POS. Specific access is managed by the `event` module.

**Data files:**
- `data/event_product_data.xml`: Event product data (demo tickets)
- `data/event_product_demo.xml`: Event demo data
- `data/point_of_sale_data.xml`: POS event data
- `data/point_of_sale_demo.xml`: POS event demo data

---

## Critical Notes

1. **Seat broadcast:** `_update_available_seat` uses `sudo()` and broadcasts to ALL open POS sessions (not just the session that triggered the update). This ensures real-time seat availability is synced across all POS terminals, even for website/bookings outside POS.

2. **Registration creation flow:** `event.registration` records are created when `pos.order` is processed. The `pos.order.line` stores `event_ticket_id` and the registration is linked via `pos_order_line_id`. The base `event` module handles the actual registration creation logic (triggered by POS order line write).

3. **Refund/cancel logic:** In `_process_order`, when a line is refunded (has `refunded_orderline_id`), the module finds proportional event registrations to cancel. This prevents ghost registrations from refunded tickets.

4. **`pos.load.mixin` everywhere:** All event models that need to be loaded into POS inherit `pos.load.mixin`, which provides `_load_pos_data_domain` and `_load_pos_data_fields` used by `pos.session._load_pos_data`.

5. **`compute=False` on relations:** The `_load_pos_data_relations` override prevents the frontend from sending back modified email/phone/name/company_name data when syncing — these fields are protected from client-side changes for event registrations.