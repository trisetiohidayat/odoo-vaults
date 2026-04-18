---
title: "Sale Gelato"
module: sale_gelato
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Sale Gelato

## Overview

Module `sale_gelato` — auto-generated from source code.

**Source:** `addons/sale_gelato/`
**Models:** 8
**Fields:** 10
**Methods:** 7

## Models

### delivery.carrier (`delivery.carrier`)

Override of `delivery` to exclude regular delivery methods from Gelato orders and Gelato
        delivery methods from non-Gelato orders.

        :param sale.order order: The current order.
        :

**File:** `delivery_carrier.py` | Class: `ProviderGelato`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `delivery_type` | `Selection` | — | — | — | — | — |
| `gelato_shipping_service_type` | `Selection` | — | — | — | — | Y |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `available_carriers` | |
| `gelato_rate_shipment` | |


### product.document (`product.document`)

Create the payload for a single file of an 'orders' request.

        :return: The file payload.
        :rtype: dict

**File:** `product_document.py` | Class: `ProductDocument`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `is_gelato` | `Boolean` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### product.product (`product.product`)

—

**File:** `product_product.py` | Class: `ProductProduct`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `gelato_product_uid` | `Char` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### product.document (`product.document`)

Fetch the template information from Gelato and update the product template accordingly.

        :return: The action to display a toast notification to the user.
        :rtype: dict

**File:** `product_template.py` | Class: `ProductTemplate`

#### Fields (4)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `gelato_template_ref` | `Char` | Y | — | — | — | — |
| `gelato_product_uid` | `Char` | Y | — | — | — | — |
| `gelato_image_ids` | `One2many` | — | — | — | — | — |
| `gelato_missing_images` | `Boolean` | Y | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_sync_gelato_template_info` | |


### res.company (`res.company`)

—

**File:** `res_company.py` | Class: `ResCompany`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `gelato_api_key` | `Char` | — | — | — | — | — |
| `gelato_webhook_secret` | `Char` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### res.partner (`res.partner`)

Trim address fields according to maximum length allowed by Gelato.

**File:** `res_partner.py` | Class: `ResPartner`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### sale.order (`sale.order`)

Ensure that the order lines don't mix Gelato and non-Gelato products.

        This method is not a constraint and is called from the `create` and `write` methods of
        `sale.order.line` to cover

**File:** `sale_order.py` | Class: `SaleOrder`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `action_open_delivery_wizard` | |
| `action_confirm` | |


### sale.order.line (`sale.order.line`)

—

**File:** `sale_order_line.py` | Class: `SaleOrderLine`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `create` | |
| `write` | |




## Related

- [[Modules/Base]]
- [[Modules/Sale]]
