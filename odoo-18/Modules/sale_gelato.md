---
Module: sale_gelato
Version: 18.0
Type: addon
Tags: #sale #gelato #print-on-demand #delivery
---

# sale_gelato — Gelato Print-on-Demand Integration

**Summary:** Place orders through Gelato's print-on-demand service.

**Depends:** `sale_management`, `delivery`
**Category:** Sales/Sales
**License:** LGPL-3
**Source:** `~/odoo/odoo18/odoo/addons/sale_gelato/`

## Overview

`sale_gelato` integrates Odoo with [Gelato](https://www.gelato.com/), a global print-on-demand platform. It allows creating personalized print products (business cards, canvases, apparel) directly from sales orders. Gelato products are synchronized via template reference IDs, and orders are pushed to Gelato's API on SO confirmation.

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/delivery_carrier.py` | `delivery.carrier` | Gelato delivery type, shipping service type, rate shipment |
| `models/product_document.py` | `product.document` | Gelato print image flag and file payload |
| `models/product_product.py` | `product.product` | Per-variant Gelato UID |
| `models/product_template.py` | `product.template` | Template sync, variant creation, image management |
| `models/res_company.py` | `res.company` | Gelato API key and webhook secret |
| `models/res_partner.py` | `res.partner` | Gelato address payload preparation |
| `models/sale_order.py` | `sale.order` | Order creation, confirmation, deletion hooks |
| `models/sale_order_line.py` | `sale.order.line` | Gelato/non-Gelato mix prevention |

---

## Models

### `delivery.carrier` — `ProviderGelato`

**File:** `models/delivery_carrier.py` (lines 10–107)

| Field | Type | Notes |
|-------|------|-------|
| `delivery_type` | Selection | Added `gelato` option; `ondelete='gelato': 'cascade'` |
| `gelato_shipping_service_type` | Selection | `normal` (Standard) or `express` (Express Delivery); default `normal` |

**Key Methods:**

- `_is_available_for_order(order)` (line 26) — Excludes regular delivery methods from Gelato orders, and Gelato delivery methods from non-Gelato orders.
- `available_carriers(partner, order)` (line 39) — Filters carrier list based on whether the order contains Gelato products.
- `gelato_rate_shipment(order)` (line 53) — Fetches delivery price from Gelato API. Validates address completeness, builds product payload, sends quote request, sums matching shipment method prices. Returns `success`, `price`, `error_message`.
- `_ensure_partner_address_is_complete(partner)` (line 88) — Validates required address fields (`city`, `country_id`, `street`, optionally `zip`). Returns translated error string or `None`.

---

### `product.document` — Gelato print image storage

**File:** `models/product_document.py` (lines 10–30)

Inherits `product.document`.

| Field | Type | Notes |
|-------|------|-------|
| `is_gelato` | Boolean (readonly) | Distinguishes Gelato print images from other documents |

**Key Methods:**

- `_gelato_prepare_file_payload()` (line 15) — Generates per-file payload for Gelato API requests: `type` (lowercased doc name) and signed `url` (with access token). Raises `UserError` if `datas` is missing.

---

### `res.company`

**File:** `models/res_company.py`

| Field | Type | Notes |
|-------|------|-------|
| `gelato_api_key` | Char | Gelato API key |
| `gelato_webhook_secret` | Char | Webhook secret for inbound events |

---

### `res.partner`

**File:** `models/res_partner.py` (lines 10–28)

**Key Methods:**

- `_gelato_prepare_address_payload()` (line 12) — Builds the address dictionary for Gelato API. Uses `payment_utils.split_partner_name()` to split the partner name into first/last. Returns `companyName`, `firstName`, `lastName`, `addressLine1/2`, `state`, `city`, `postCode`, `country`, `email`, `phone`.

---

### `product.template`

**File:** `models/product_template.py` (lines 10–142)

| Field | Type | Notes |
|-------|------|-------|
| `gelato_template_ref` | Char | Gelato template ID; used to fetch/sync variants from Gelato |
| `gelato_product_uid` | Char (computed/inversed) | UID from Gelato per variant; synced down from variants |
| `gelato_image_ids` | One2many → `product.document` | Filtered to `is_gelato = True`; stored on template |
| `gelato_missing_images` | Boolean (computed) | True if any Gelato image has no binary data |

**Key Methods:**

- `_compute_gelato_product_uid()` (inherited from variant) — Computes `gelato_product_uid` from the first product variant.
- `_inverse_gelato_product_uid()` — Writes `gelato_product_uid` back to variants.
- `_compute_gelato_missing_images()` — Checks if any Gelato image lacks binary data.
- `action_sync_gelato_template_info()` (line 40) — Action method; fetches template info from Gelato API, creates product variants and print image records. Shows success/error notification with `soft_reload`.
- `_create_attributes_from_gelato_info(template_info)` (line 66) — Parses `variants` from Gelato, creates `product.attribute` and `product.attribute.value` records if missing, creates PTALs, sets `gelato_product_uid` on matching variants, deletes variants not in Gelato.
- `_create_print_images_from_gelato_info(template_info)` (line 109) — Creates `product.document` records for each `imagePlaceholders` entry. Normalizes print area names to `'default'`.
- `_get_related_fields_variant_template()` (line 133) — Adds `gelato_product_uid` to related fields.
- `_get_product_document_domain()` (line 137) — Overrides to exclude Gelato images from regular document list (filters `is_gelato = False`).

---

### `product.product`

**File:** `models/product_product.py`

| Field | Type | Notes |
|-------|------|-------|
| `gelato_product_uid` | Char (readonly) | Per-variant Gelato UID |

---

### `sale.order`

**File:** `models/sale_order.py` (lines 10–159)

**Key Methods:**

- `_prevent_mixing_gelato_and_non_gelato_products()` (line 19) — Validates that a SO does not contain both Gelato and non-Gelato products (excluding sections and non-deliverable products). Called from SOL create/write.
- `action_open_delivery_wizard()` (line 45) — Overrides `delivery`; auto-selects a Gelato delivery method if the order has Gelato products.
- `action_confirm()` (line 55) — Extends parent; calls `_create_order_on_gelato()` for orders containing Gelato products.
- `_create_order_on_gelato()` (line 60) — Sends order creation request to Gelato API. Sets up post-commit hooks to `_confirm_order_on_gelato` and post-rollback hooks to `_delete_order_on_gelato`. Posts chatter message on success.
- `_gelato_prepare_items_payload()` (line 92) — Builds the `items` list for the Gelato API request: `itemReferenceId`, `productUid`, `files` (from gelato image documents), and `quantity`.
- `_confirm_order_on_gelato(gelato_order_id)` (line 111) — `@post_commit` hook; sends PATCH request to confirm the Gelato order (draft → order).
- `_delete_order_on_gelato(gelato_order_id)` (line 130) — `@post_commit` hook; sends DELETE request to cancel the Gelato order if the Odoo transaction rolls back.

**Critical Flow:**
```
action_confirm()
  → _create_order_on_gelato()
    → Gelato API: POST /orders (draft)
    → post-commit: _confirm_order_on_gelato() → PATCH /orders/{id} (confirm)
    → post-rollback: _delete_order_on_gelato() → DELETE /orders/{id}
```

---

### `sale.order.line`

**File:** `models/sale_order_line.py` (lines 10–18)

**Key Methods:**

- `_action_launch_stock_rule(**kwargs)` (line 11) — Overrides `sale_stock`; filters out Gelato product lines before calling parent, preventing Gelato products from triggering stock picking creation.

---

## Data Files

| File | Purpose |
|------|---------|
| `data/product_data.xml` | Product data (e.g., delivery product codes `normal`, `express`) |
| `data/delivery_carrier_data.xml` | Gelato delivery carrier definitions |
| `data/mail_template_data.xml` | Mail templates for Gelato order notifications |

---

## Views (XML)

- `views/delivery_carrier_views.xml` — Form view for Gelato carrier
- `views/product_document_views.xml` — Product document kanban/list
- `views/product_product_views.xml` — Product variant form (shows `gelato_product_uid`)
- `views/product_template_views.xml` — Template form (sync button, Gelato fields)
- `views/res_config_settings_views.xml` — Settings wizard (API key field)

---

## Relations

```
product.template.gelato_template_ref → Gelato API
                              ↓
                    product.product (variants)
                              ↓
                    product.document (is_gelato=True) → Gelato API (file payload)
                              ↓
sale.order.action_confirm() → Gelato API orders endpoint → Gelato production/shipping
```

---

## Related Modules

- `sale_gelato_stock` — Stock bridge (prevents pickings for Gelato products)
- `website_sale_gelato` — Website e-commerce bridge
