---
title: "Website Sale Slides"
module: website_sale_slides
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Website Sale Slides

## Overview

Module `website_sale_slides` — auto-generated from source code.

**Source:** `addons/website_sale_slides/`
**Models:** 5
**Fields:** 6
**Methods:** 4

## Models

### product.product (`product.product`)

Override to allow published course related products to the cart regardless of product's rules.

**File:** `product_product.py` | Class: `ProductProduct`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `channel_ids` | `One2many` | — | — | Y | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `get_product_multiline_description_sale` | |


### product.template (`product.template`)

—

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

If the product of an order line is a 'course', we add the client of the sale_order
        as a member of the channel(s) on which this product is configured (see slide.channel.product_id).

**File:** `sale_order.py` | Class: `SaleOrder`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### sale.order.line (`sale.order.line`)

—

**File:** `sale_order_line.py` | Class: `SaleOrderLine`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### slide.channel (`slide.channel`)

Ensure that when publishing a course that its linked product is also published
        If all courses linked to a product are unpublished, we also unpublished the product

**File:** `slide_channel.py` | Class: `SlideChannel`

#### Fields (4)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `enroll` | `Selection` | — | — | — | — | — |
| `product_id` | `Many2one` | Y | — | — | — | — |
| `product_sale_revenues` | `Monetary` | Y | — | Y | — | — |
| `currency_id` | `Many2one` | Y | — | Y | — | Y |


#### Methods (3)

| Method | Description |
|--------|-------------|
| `create` | |
| `write` | |
| `action_view_sales` | |




## Related

- [[Modules/Base]]
- [[Modules/Website]]
