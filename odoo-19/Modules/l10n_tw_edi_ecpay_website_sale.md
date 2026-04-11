---
type: module
module: l10n_tw_edi_ecpay_website_sale
tags: [odoo, odoo19, l10n, localization, taiwan, edi, einvoice, ecommerce, website_sale]
created: 2026-04-06
---

# Taiwan EDI ECPay Website Sale - E-commerce E-invoice Bridge (l10n_tw_edi_ecpay_website_sale)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Taiwan - E-invoicing Ecommerce |
| **Technical** | `l10n_tw_edi_ecpay_website_sale` |
| **Category** | Localization / EDI / Website Sale |
| **Country** | Taiwan |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |
| **License** | LGPL-3 |
| **Countries** | Taiwan (TW) |
| **Auto-install** | Yes |

## Description

Bridge module connecting [[Modules/website_sale]] with [[Modules/l10n_tw_edi_ecpay]] to enable e-invoice issuance for e-commerce transactions in Taiwan. This module allows customers to provide their e-invoice carrier information (爱心码/捐贈碼) during the checkout process and automatically issues e-invoices through ECPay.

In Taiwan, B2C e-invoices require either a carrier binding (爱心码) for lottery donations or a mobile barcode (載具條碼). This module captures this information during the online shopping checkout.

## Dependencies

| Module | Purpose |
|--------|---------|
| [[Modules/website_sale]] | Odoo e-commerce / website shop |
| [[Modules/l10n_tw_edi_ecpay]] | ECPay e-invoicing base |

## Key Models

### `sale.order` (sale_order.py)
Extends `sale.order` with ECPay e-invoice fields:
- **l10n_tw EDI Carrier Type**: Type of carrier (mobile barcode, donation code, etc.)
- **l10n_tw EDI Carrier ID**: The carrier ID / donation code
- E-invoice status synced from the linked invoice

### `res.partner` (res_partner.py)
Extends partner with fields for e-invoice carrier:
- Carrier ID stored on partner for repeat customers
- Automatic population during checkout

## Country-Specific Features

### E-invoice Carrier Options (Taiwan)
1. **捐贈碼 (Donation Code)**: 3-7 digit code for charitable donations (lottery ticket donation)
2. **手機條碼 (Mobile Barcode)**: Barcode linked to mobile phone for invoice collection
3. **自然人憑證 (Citizen Digital Certificate)**: Personal identification for e-invoice

### Checkout Integration
- Customer selects carrier type during checkout
- Input field for carrier ID / donation code
- Option to donate to specific charity organization
- Stored on partner for future orders

### E-invoice Workflow for E-commerce
1. Customer places order on website and provides carrier info
2. Order confirmed and invoice generated in Odoo
3. ECPay e-invoice issued with carrier binding
4. Invoice available to customer (via email/portal)
5. Monthly lottery number included (for donation codes)

## Data Files

- `data/data.xml` - Carrier type configuration data
- `views/sale_order_views.xml` - Sale order form updates
- `views/templates.xml` - Website checkout templates
- `static/src/**/*` - Frontend JavaScript for carrier input

## Assets

- `web.assets_frontend`: Frontend assets for checkout carrier input
- `web.assets_tests`: Test assets

## Post-Init Hook

- `_post_init_hook`: Migrates existing partner carrier data

## Related

- [[Modules/l10n_tw_edi_ecpay]] - Core ECPay e-invoicing
- [[Modules/l10n_tw]] - Base Taiwanese accounting
- [[Modules/website_sale]] - E-commerce module
