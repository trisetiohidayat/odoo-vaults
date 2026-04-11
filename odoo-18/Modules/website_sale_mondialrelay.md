---
Module: website_sale_mondialrelay
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_sale_mondialrelay #ecommerce #delivery
---

## Overview

**Module:** `website_sale_mondialrelay`
**Depends:** `delivery_mondialrelay`, `website_sale`
**Location:** `~/odoo/odoo18/odoo/addons/website_sale_mondialrelay/`
**Purpose:** Integrates Mondial Relay delivery (point relais) with eCommerce — validates that the shipping address is a Mondial Relay Point Relais when using the Mondial Relay carrier, and vice versa.

## Models

### `sale.order` (website_sale_mondialrelay/models/sale_order.py)

Inherits: `sale.order`

| Method | Decorator | Description |
|---|---|---|
| `_check_cart_is_ready_to_be_paid()` | override | Raises `ValidationError` if: (1) shipping address is a Point Relais but carrier is not Mondial Relay; (2) carrier is Mondial Relay but shipping address is not a Point Relais |
| `_compute_partner_shipping_id()` | override | If the saved shipping address is a Point Relais but carrier is not Mondial Relay, resets shipping to the base partner address (drops the relay point) |

### `res.partner` (website_sale_mondialrelay/models/res_partner.py)

Inherits: `res.partner`

| Method | Decorator | Description |
|---|---|---|
| `_can_be_edited_by_current_customer()` | override | Returns `False` for `is_mondialrelay` partners (relay points cannot be edited by customers) |

## Security / Data

No `ir.model.access.csv`. No data XML files.

## Critical Notes

- v17→v18: No breaking changes.
- The key constraint: Point Relais delivery and Mondial Relay carrier must be used together.
- When switching carriers away from Mondial Relay, the shipping address is automatically reset to the customer's standard address (dropping the relay point selection).
- `is_mondialrelay` is a field on `res.partner` set by the `delivery_mondialrelay` base module.