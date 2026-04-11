---
Module: website_sale_collect
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_sale_collect #ecommerce #click-and-collect
---

## Overview

**Module:** `website_sale_collect`
**Depends:** `website_sale`, `website_sale_stock`, `delivery`
**Location:** `~/odoo/odoo18/odoo/addons/website_sale_collect/`
**Purpose:** Implements "Click & Collect" (in-store pickup) for eCommerce — adds `in_store` delivery type, store selection, opening hours, stock per warehouse, and on-site payment.

## Models

### `website` (website_sale_collect/models/website.py)

Inherits: `website`

| Field | Type | Description |
|---|---|---|
| `in_store_dm_id` | Many2one (`delivery.carrier`) | Computed: finds published `in_store` delivery carrier matching website/company |

| Method | Decorator | Description |
|---|---|---|
| `_compute_in_store_dm_id()` | `@api.depends` | Searches published `in_store` carriers filtered by website and company; assigns first match |
| `_get_product_available_qty(product, **kwargs)` | public | Overrides `website_sale_stock`; adds in-store warehouse max qty to available stock |
| `_get_max_in_store_product_available_qty(product)` | private | Returns max `free_qty` across all in-store warehouse IDs |

### `stock.warehouse` (website_sale_collect/models/stock_warehouse.py)

Inherits: `stock.warehouse`

| Field | Type | Description |
|---|---|---|
| `opening_hours` | Many2one (`resource.calendar`) | Opening hours calendar for click & collect store display |

### `delivery.carrier` (website_sale_collect/models/delivery_carrier.py)

Inherits: `delivery.carrier`

| Field | Type | Description |
|---|---|---|
| `delivery_type` | Selection | Extended: adds `'in_store'` ("Pick up in store") — ondelete: `'set default'` |
| `warehouse_ids` | Many2many (`stock.warehouse`) | Stores available for in-store pickup |

| Method | Decorator | Description |
|---|---|---|
| `_check_in_store_dm_has_warehouses_when_published()` | `@api.constrains` | Validates that published `in_store` carriers have at least one warehouse |
| `_check_warehouses_have_same_company()` | `@api.constrains` | Ensures in-store warehouses share same company as the carrier |
| `create()` | `@api.model_create_multi` | Auto-sets `integration_level = 'rate'` for `in_store` carriers |
| `write()` | regular | Auto-sets `integration_level = 'rate'` for `in_store` carriers |
| `_in_store_get_close_locations(partner_address, product_id=None)` | business | Returns sorted pickup locations with distance, hours, stock data |
| `in_store_rate_shipment()` | business | Returns fixed price from `product_id.list_price` for in-store rate |

### `payment.provider` (website_sale_collect/models/payment_provider.py)

Inherits: `payment.provider`

| Field | Type | Description |
|---|---|---|
| `custom_mode` | Selection | Extended: adds `'on_site'` ("Pay on site") |

| Method | Decorator | Description |
|---|---|---|
| `_get_compatible_providers()` | `@api.model` | Hides `on_site` providers unless in-store delivery selected and cart has consumable products; adds to availability report with reason |
| `_get_default_payment_method_codes()` | override | Returns `DEFAULT_PAYMENT_METHOD_CODES` for `on_site` mode |

### `payment.transaction` (website_sale_collect/models/payment_transaction.py)

Inherits: `payment.transaction`

| Method | Decorator | Description |
|---|---|---|
| `_post_process()` | override | If tx `custom_mode == 'on_site'` and state is `pending`, auto-confirms the draft sale order |

### `sale.order` (website_sale_collect/models/sale_order.py)

Inherits: `sale.order`

| Method | Decorator | Description |
|---|---|---|
| `_compute_warehouse_id()` | override | Bypasses `website_sale_stock` warehouse compute for `in_store` orders that have `pickup_location_data` |
| `_set_delivery_method(delivery_method, rate=None)` | override | Recomputes warehouse and fiscal position when switching FROM in-store to another delivery type |
| `_set_pickup_location(pickup_location_data)` | override | Sets `pickup_location_data` from JSON, warehouse, and fiscal position based on pickup store |
| `_get_pickup_locations(zip_code=None, country=None, **kwargs)` | override | Ensures country is found from GeoIP when zip code provided; clears zip if country unknown |
| `_get_cart_and_free_qty(product, line=None)` | override | Returns warehouse-specific `free_qty` for `in_store` delivery |
| `_check_cart_is_ready_to_be_paid()` | override | Raises `ValidationError` if any storable product is out of stock at selected store |
| `_is_in_stock(wh_id)` | private | Returns `bool`; checks if all storable cart products are in stock at warehouse |
| `_get_unavailable_order_lines(wh_id)` | private | Returns `sale.order.line` recordset; sets `shop_warning` on unavailable lines |
| `_verify_updated_quantity()` | override | Skips quantity verification when click & collect active (verified later at checkout) |

## Security / Data

No `ir.model.access.csv`. Data files:

- `delivery_carrier_data.xml` — demo in_store delivery carrier
- `payment_provider_data.xml` — demo on_site payment provider
- `payment_method_data.xml` — demo payment method
- `product_product_data.xml` — demo products
- `demo.xml` — demo data

## Critical Notes

- v17→v18: This module is new in v18, replacing the legacy `website_sale_delivery` in-store concept.
- `in_store` delivery type is a site-wide configuration — only one published in-store carrier per website is used.
- On-site payment auto-confirms draft orders at `_post_process` (not at payment capture).
- Warehouse opening hours display on the store selector widget.
- Fiscal position is recalculated when pickup location changes to handle tax jurisdiction of the store.