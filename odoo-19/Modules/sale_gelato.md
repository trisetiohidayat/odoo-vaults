# sale_gelato

Odoo 19 Sales/e-Commerce Module

## Overview

`sale_gelato` integrates Odoo with **Gelato** (print-on-demand platform). Products are synchronized from Gelato as product templates/variants with print image areas. When sale orders are confirmed, they are automatically sent to Gelato for printing and fulfillment.

## Module Details

- **Category**: Sales/Sales
- **Depends**: Core sale, delivery, product document modules
- **Version**: 1.0
- **Author**: Odoo S.A.
- **License**: LGPL-3

## Key Concepts

### Gelato Print-on-Demand

Gelato is a global print-on-demand network. Products (e.g., personalized books, calendars, photo products) are designed in Gelato and synchronized into Odoo. When a customer orders, Odoo sends the order to Gelato which prints and ships directly.

## Key Components

### Company Configuration

#### `res.company` (Inherited)

| Field | Type | Description |
|---|---|---|
| `gelato_api_key` | Char | Gelato API key (system admin only) |
| `gelato_webhook_secret` | Char | Gelato webhook secret |

### Product Models

#### `product.template` (Inherited)

| Field | Type | Description |
|---|---|---|
| `gelato_template_ref` | Char | Gelato template reference ID |
| `gelato_product_uid` | Char | Gelato product UID (from variant) |
| `gelato_image_ids` | One2many | Print image documents (res_model=product.template) |
| `gelato_missing_images` | Boolean | Some print images are not set |

**Key Methods:**
- `action_sync_gelato_template_info()` — Fetches template from Gelato API and creates variants + print image records.
- `_create_attributes_from_gelato_info()` — Creates product attributes/variants from Gelato variant data. Sets `description_ecommerce`.
- `_create_print_images_from_gelato_info()` — Creates `product.document` records with `is_gelato=True` for print areas.
- `_get_product_document_domain()` — Excludes Gelato print images from regular document list.

#### `product.product` (Inherited)

| Field | Type | Description |
|---|---|---|
| `gelato_product_uid` | Char | Gelato product UID for this variant (readonly) |

### Product Documents

#### `product.document` (Inherited)

| Field | Type | Description |
|---|---|---|
| `is_gelato` | Boolean | Marks document as a Gelato print image (readonly) |

`_gelato_prepare_file_payload()` — Converts the print image attachment to a Gelato API file payload with signed URL.

### Sale Order

#### `sale.order` (Inherited)

`_prevent_mixing_gelato_and_non_gelato_products()` — Constraint: Gelato and non-Gelato products cannot be in the same order.

**Delivery:**
- `action_open_delivery_wizard()` — Pre-selects Gelato delivery method when order contains Gelato products.
- `action_confirm()` — Sends Gelato order to Gelato API after SO confirmation.

**_create_order_on_gelato()`** — Main integration method:
- Builds order payload with items (Gelato product UIDs + print images + quantities).
- Adds shipping address and shipment method.
- Creates order as `draft` type on Gelato, with post-commit hooks to confirm or delete.
- Posts chatter notification on success.

**_confirm_order_on_gelato()`** — Post-commit PATCH to Gelato to confirm the draft order.

**_delete_order_on_gelato()`** — Post-commit DELETE on Gelato if Odoo transaction rolls back.

#### `sale.order.line` (Inherited)

`_gelato_prepare_items_payload()` — Serializes sale order lines to Gelato items API format.

### Delivery

#### `delivery.carrier` (Inherited)

| Field | Type | Description |
|---|---|---|
| `delivery_type` | Selection | Adds `'gelato'` option |
| `gelato_shipping_service_type` | Selection | `'normal'` (Standard) or `'express'` (Express Delivery) |

**_is_available_for_order()** — Excludes non-Gelato delivery methods from Gelato orders and vice versa.

`available_carriers()` — Filters delivery methods based on Gelato/non-Gelato order type.

`gelato_rate_shipment()` — Fetches shipping rates from Gelato API based on order items and shipping address.

### Partner

#### `res.partner` (Inherited)

`_gelato_prepare_address_payload()` — Formats partner address for Gelato API with field length limits (street 35 chars, city 30 chars, etc.), splitting long addresses into addressLine1/2.

## Business Rules

1. **No mixing**: Gelato and non-Gelato products cannot coexist in one sale order.
2. **Complete address required**: Partner address must have name, street, city, country, email, and zip (if required).
3. **Print images required**: Products must have print images before they can be published.
4. **No stock pickings**: Gelato products do not trigger standard stock procurement (handled by `sale_gelato_stock`).
