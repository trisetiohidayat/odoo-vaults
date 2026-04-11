---
Module: product_images
Version: 18.0.0
Type: addon
Tags: #odoo18 #product #images #google #iap
---

## Overview

Fetches product images from Google Images based on product barcode via the Google Custom Search API. The wizard immediately processes the first 10 products; remaining products are delegated to a background cron job that self-schedules in batches.

**Depends:** `product`, `google_custom_search`

**Key Behavior:** API key and Search Engine ID must be configured in General Settings. Only products with a barcode and no existing image are processed. The `ir_cron_fetch_image` trigger is constrained to max 2 concurrent triggers to manage rate limits.

---

## Models

### `product.product` (Inherited)

**Inherited from:** `product.product`

| Field | Type | Note |
|-------|------|------|
| `image_fetch_pending` | Boolean | Flag indicating image fetch is pending (set by wizard) |

| Method | Returns | Note |
|--------|---------|------|
| `action_open_quants()` | Action | Injects `hide_removal_date=True` context if no products use expiration |

### `ir.cron.trigger` (Inherited)

**Inherited from:** `ir.cron.trigger`

| Method | Returns | Note |
|--------|---------|------|
| `_check_image_cron_is_not_already_triggered()` | — | Constraint: max 1 trigger (or 2 if auto-triggered) for `ir_cron_fetch_image` |

### `product.fetch.image.wizard` (Transient)

**Model:** `product.fetch.image.wizard`
**Inherit:** `False`

| Field | Type | Note |
|-------|------|------|
| `nb_products_selected` | Integer (readonly) | Total products selected |
| `products_to_process` | Many2many `product.product` | Products with barcode and no image |
| `nb_products_to_process` | Integer (readonly) | Count to process |
| `nb_products_unable_to_process` | Integer (readonly) | Count already having images or no barcode |

| Method | Returns | Note |
|--------|---------|------|
| `default_get(fields_list)` | dict | Validates cron exists and not already triggered; checks API keys |
| `action_fetch_image()` | Client Action | Processes 10 images immediately, triggers cron for remainder |
| `_cron_fetch_image()` | — | Processes 100 products at a time; reschedules if more remain |
| `_get_products_to_process(limit)` | recordset | Returns pending products filtered by barcode + no image |
| `_process_products(products)` | int | Fetches image URLs from Google; returns count of successful fetches |
| `_fetch_image_urls_from_google(barcode)` | Response | Calls Google Custom Search API v1 |
| `_get_image_from_url(url)` | bytes | Downloads image; returns base64-encoded bytes |
| `_trigger_fetch_images_cron(at)` | — | Creates `ir.cron.trigger` for `ir_cron_fetch_image`; commits immediately |

**Error Handling:**
- `403 Forbidden` → API not enabled in Google Cloud
- `429 Too Many Requests` → Reschedule cron for next day
- `503 Service Unavailable` (>3 times) → Reschedule cron for 1 hour
- `400 Bad Request` → Incorrect API key or Search Engine ID
- Connection timeout (>3 times) → Reschedule cron for 1 hour
