---
title: website_sale_product_configurator
draft: false
tags:
  - #odoo
  - #odoo19
  - #modules
  - #website
  - #e-commerce
  - #product-configurator
  - #optional-products
created: 2026-04-11
description: Bridge module connecting website_sale with sale_product_configurator to enable optional product selection on the e-commerce storefront.
---

# website_sale_product_configurator

> **Display Name:** Website Sale Product Configurator  
> **Summary:** Bridge module for website_sale / sale_product_configurator  
> **Category:** Hidden  
> **License:** LGPL-3  
> **Author:** Odoo S.A.  
> **Module Path:** `odoo/addons/website_sale_product_configurator/` (Odoo 17; merged into core in Odoo 18+)  
> **Auto-install:** Yes

## Overview

`website_sale_product_configurator` adalah **bridge module** yang menghubungkan `website_sale` dengan `sale_product_configurator`. Modul ini memungkinkan customer memilih **optional/upsell products** saat menambahkan produk utama ke keranjang belanja di halaman e-commerce.

Modul ini berfungsi sebagai integrator -- ia tidak berdiri sendiri melainkan menyatukan dua modul lain agar bekerja bersama di front-end website.

> **Note on Odoo Version:** Di Odoo 18+, fitur ini sudah di-merge ke dalam core `website_sale`. Modul bridge ini tidak ada di Odoo 19 karena fungsionalitas `add_to_cart_action='force_dialog'` dan optional product selection sudah menjadi bagian dari `website_sale` itu sendiri.

---

## Dependencies

```python
'depends': ['website_sale', 'sale_product_configurator']
```

| Dependency | Purpose |
|------------|---------|
| `website_sale` | E-commerce front-end |
| `sale_product_configurator` | Optional product logic di sales |

**Auto-install:** Yes  
**Demo data:** Yes (`data/demo.xml`)

---

## Module Structure

```
website_sale_product_configurator/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── sale_order.py       # Override _cart_find_product_line
│   └── website.py          # Add 'force_dialog' to add_to_cart_action
├── controllers/
│   ├── __init__.py
│   └── main.py             # (may include modal controller)
├── views/
│   └── templates.xml       # Modal dialog & optional product table
├── static/src/
│   ├── js/
│   │   ├── sale_product_configurator_modal.js
│   │   └── website_sale_options.js
│   └── scss/
│       └── website_sale_options.scss
├── tests/
│   └── ...                 # Integration tests
└── data/
    └── demo.xml
```

---

## Models

### 1. `sale.order` (Extended)

**File:** `models/sale_order.py`

Modul ini mengoverride `_cart_find_product_line` untuk menangani **optional products** dalam konteks website cart.

```python
class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _cart_find_product_line(
        self, product_id=None, line_id=None,
        linked_line_id=False, optional_product_ids=None, **kwargs
    ):
        lines = super()._cart_find_product_line(product_id, line_id, **kwargs)
        if line_id:
            return lines  # Exact line requested, skip filtering

        # Match linked_line_id
        lines = lines.filtered(lambda line: line.linked_line_id.id == linked_line_id)

        if optional_product_ids:
            # Only match lines with the same chosen optional products
            lines = lines.filtered(
                lambda line: optional_product_ids == set(line.option_line_ids.product_id.id)
            )
        else:
            # Only match lines with no optional products
            lines = lines.filtered(lambda line: not line.option_line_ids)

        return lines
```

**Purpose:** Ketika customer menambahkan produk dengan optional products, sistem perlu menemukan line yang tepat di cart berdasarkan:
- `linked_line_id`: Line utama yang связано dengan optional
- `optional_product_ids`: Set product ID dari optional products yang dipilih

Tanpa override ini, cart tidak bisa membedakan antara "produk A saja" vs "produk A + optional B".

### 2. `website` (Extended)

**File:** `models/website.py`

Menambahkan opsi baru `force_dialog` ke field `add_to_cart_action`.

```python
class Website(models.Model):
    _inherit = 'website'

    add_to_cart_action = fields.Selection(
        selection_add=[('force_dialog', "Let the user decide (dialog)")],
        ondelete={'force_dialog': 'set default'}
    )
```

> **Odoo 19 Note:** Di Odoo 19, `add_to_cart_action` hanya memiliki dua opsi: `stay` dan `go_to_cart`. Opsi `force_dialog` sudah dihapus karena dialog configurator sekarang selalu digunakan jika produk punya optional products.

---

## View Templates

### Modal Dialog (`optional_products_modal`)

```xml
<template id="optional_products_modal" name="Optional Products">
    <main class="modal-body">
        <t t-call="website_sale_product_configurator.configure_optional_products" />
    </main>
</template>
```

Wrapper modal Bootstrap yang memanggil template utama untuk rendering configurator.

### Main Configurator (`configure_optional_products`)

Template utama yang menampilkan:

**Header row:**
| Product | Name | Quantity | Price |
|---------|------|----------|-------|

**Main product row:**
- Hidden inputs: `product_template_id`, `product_id`
- Product image
- Product name + variant info + description_sale
- Variant selector (`website_sale.variants`)
- Quantity input
- Price display

**Total row:** Calculated total (price x qty)

**Optional products section:**
- "Available Options:" header
- Loop melalui `product.optional_product_ids`
- For each optional product: image, name, variants, price, "Add" button

### Quantity Config (`product_quantity_config`)

```xml
<template id="product_quantity_config">
    <!-- Show +/- buttons if product_quantity view is active -->
    <!-- Otherwise hidden input -->
</template>
```

---

## User Flow

```
1. Customer di product page, pilih variant, klik "Add to Cart"
   ↓
2. Jika produk punya optional products:
   → Dialog configurator muncul (force_dialog mode)
   ↓
3. Customer dapat:
   a. Pilih variant untuk main product
   b. Pilih optional products dari list
   c. Adjust quantity
   d. Klik "Add to Cart" di modal
   ↓
4. sale_order._cart_find_product_line() dipanggil dengan:
   - product_id (main product)
   - optional_product_ids (set of optional product IDs)
   ↓
5. Cart line ditemukan/dibuat dengan:
   - linked_line_id → main line
   - option_line_ids → optional product lines
```

---

## Bridge Module Pattern

Modul ini adalah contoh klasik **bridge/connector pattern** di Odoo:

```
sale_product_configurator (sale)
       ↑
       │ (reuses product variant logic)
       │
website_sale_product_configurator (bridge)
       │
       ↓
website_sale (website)
```

Bridge module berfungsi:
1. Import JS assets dengan ordering yang tepat
2. Override model untuk adaptasi cross-module
3. Menyediakan view templates untuk integrasi UI
4. Menghandle edge cases yang hanya muncul saat dua modul digunakan bersamaan

---

## Odoo 19 Status

**Modul ini TIDAK ada di Odoo 19.**

Di Odoo 18, fungsionalitas configurator di-merge ke dalam `website_sale`:
- `add_to_cart_action` sekarang hanya `stay` atau `go_to_cart`
- Dialog configurator tetap muncul jika produk punya optional products
- Logic di-merge ke `sale.order` dan `website_sale` itu sendiri

**Di Odoo 19:**
- `website_sale` sudah menangani configurator flow secara native
- Tidak perlu bridge module
- Test file ada di: `website_sale/tests/test_website_sale_product_configurator.py`

---

## Key Concepts

- **Bridge module**: Menghubungkan dua modul yang sudah ada
- **Optional products**: Produk upsell yang terkait dengan produk utama via `optional_product_ids` pada `product.template`
- **Cart line matching**: Algoritma menemukan line yang tepat di cart berdasarkan main product + optional products
- **force_dialog mode**: Mode yang selalu menampilkan configurator dialog sebelum add to cart
- **Cross-module inheritance**: Override method dari satu modul yang digunakan oleh modul lain

## Tags

#odoo #odoo19 #modules #website #e-commerce #product-configurator #optional-products
