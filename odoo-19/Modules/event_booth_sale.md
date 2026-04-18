---
title: "Event Booth Sale"
module: event_booth_sale
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Event Booth Sale

## Overview

Module `event_booth_sale` — auto-generated from source code.

**Source:** `addons/event_booth_sale/`
**Models:** 9
**Fields:** 29
**Methods:** 5

## Models

### account.move (`account.move`)

When an invoice linked to a sales order selling registrations is
        paid, update booths accordingly as they are booked when invoice is paid.

**File:** `account_move.py` | Class: `AccountMove`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### event.booth (`event.booth`)

—

**File:** `event_booth.py` | Class: `EventBooth`

#### Fields (5)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `event_booth_registration_ids` | `One2many` | — | — | — | — | — |
| `sale_order_line_registration_ids` | `Many2many` | — | — | — | — | — |
| `sale_order_line_id` | `Many2one` | — | — | Y | — | — |
| `sale_order_id` | `Many2one` | — | — | Y | Y | — |
| `is_paid` | `Boolean` | — | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `action_set_paid` | |
| `action_view_sale_order` | |


### event.booth.category (`event.booth.category`)

By default price comes from category but can be changed by event
        people as product may be shared across various categories.

**File:** `event_booth_category.py` | Class: `EventBoothCategory`

#### Fields (7)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `product_id` | `Many2one` | Y | — | — | — | Y |
| `price` | `Float` | Y | — | — | Y | — |
| `price_incl` | `Float` | Y | — | Y | — | — |
| `currency_id` | `Many2one` | Y | — | Y | — | — |
| `price_reduce` | `Float` | Y | — | — | — | — |
| `price_reduce_taxinc` | `Float` | Y | — | — | Y | — |
| `image_1920` | `Image` | Y | — | — | Y | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### event.booth.registration (`event.booth.registration`)

event.booth.registrations are used to allow multiple partners to book the same booth.
    Whenever a partner has paid their registration all the others linked to the booth will be deleted.

**File:** `event_booth_registration.py` | Class: `EventBoothRegistration`

#### Fields (7)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `sale_order_line_id` | `Many2one` | — | — | Y | — | Y |
| `event_booth_id` | `Many2one` | Y | — | Y | Y | Y |
| `partner_id` | `Many2one` | Y | — | Y | Y | — |
| `contact_name` | `Char` | Y | — | — | Y | — |
| `contact_email` | `Char` | Y | — | — | Y | — |
| `contact_phone` | `Char` | Y | — | — | Y | — |
| `body` | `Markup` | — | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_confirm` | |


### event.type.booth (`event.type.booth`)

—

**File:** `event_type_booth.py` | Class: `EventTypeBooth`

#### Fields (3)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `product_id` | `Many2one` | — | — | Y | Y | — |
| `price` | `Float` | — | — | Y | Y | — |
| `currency_id` | `Many2one` | — | — | Y | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### product.product (`product.product`)

—

**File:** `product_product.py` | Class: `ProductProduct`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### product.template (`product.template`)

Prevent changing the service_tracking field if the product template or any of its variants
        is linked to an Event Booth Category.

**File:** `product_template.py` | Class: `ProductTemplate`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `service_tracking` | `Selection` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### sale.order (`sale.order`)

—

**File:** `sale_order.py` | Class: `SaleOrder`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `event_booth_ids` | `One2many` | Y | — | — | — | — |
| `event_booth_count` | `Integer` | Y | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `action_confirm` | |
| `action_view_booth_list` | |


### sale.order.line (`sale.order.line`)

This method will take care of creating the event.booth.registrations based on selected booths.
        It will also unlink ones that are de-selected.

**File:** `sale_order_line.py` | Class: `SaleOrderLine`

#### Fields (4)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `event_booth_category_id` | `Many2one` | Y | — | — | — | — |
| `event_booth_pending_ids` | `Many2many` | Y | — | — | — | — |
| `event_booth_registration_ids` | `One2many` | — | — | — | — | — |
| `event_booth_ids` | `One2many` | Y | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [Modules/Base](base.md)
- [Modules/Base](base.md)
