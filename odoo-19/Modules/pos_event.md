# POS Event

## Overview
- **Name:** POS - Event
- **Category:** Technical
- **Depends:** `point_of_sale`, `event_product`
- **Auto-install:** True
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Description
Link module between Point of Sale and Event management. Enables selling event tickets at POS and creating event registrations from POS orders. Supports attendee management and badge printing.

## Models

### `pos.order` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `attendee_count` | Integer | Computed from `lines.event_registration_ids` |

### `pos.order.line` (Extended via event_product)
| Field | Type | Description |
|-------|------|-------------|
| `event_registration_ids` | One2many | Event registrations from this line |
| `event_ticket_id` | Many2one | Event ticket product |

## Key Features
- Sell event tickets at POS (product type: event ticket)
- Auto-create event registrations on order payment
- Refund processing cancels corresponding registrations
- Attendee count on POS orders
- Print event tickets and badges from POS

## Key Methods
- `read_pos_data()` — Load event registration data for paid orders; send badge emails
- `_process_order()` — Cancel event registrations on refund
- `print_event_tickets()` — Report action for ticket printing
- `print_event_badges()` — Report action for badge printing
- `action_view_attendee_list()` — Action to view linked registrations

## Data Files
- `security/ir.model.access.csv` — Access control
- `data/point_of_sale_data.xml` — POS event configuration
- `data/event_product_data.xml` — Event product data
- `views/event_registration_views.xml` — Registration views
- `views/event_event_views.xml` — Event views
- `views/pos_order_views.xml` — POS order views

## Demo Data
- `data/event_product_demo.xml` — Demo event ticket products
- `data/point_of_sale_demo.xml` — Demo POS configuration

## Related
- [Modules/point_of_sale](odoo-18/Modules/point_of_sale.md) — Base POS module
- [Modules/event](odoo-18/Modules/event.md) — Event management
- [Modules/pos_event_sale](odoo-18/Modules/pos_event_sale.md) — POS Event + Sale
