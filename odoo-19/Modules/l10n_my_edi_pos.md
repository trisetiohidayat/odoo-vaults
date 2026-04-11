---
type: module
module: l10n_my_edi_pos
tags: [odoo, odoo19, l10n, localization, malaysia, edi, einvoice, pos]
created: 2026-04-06
---

# Malaysia EDI POS - MyInvois for Point of Sale (l10n_my_edi_pos)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Malaysia - E-invoicing (POS) |
| **Technical** | `l10n_my_edi_pos` |
| **Category** | Localization / EDI |
| **Country** | Malaysia |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |
| **License** | LGPL-3 |
| **Countries** | Malaysia (MY) |
| **Auto-install** | Yes |

## Description

POS-specific extension for Malaysian e-invoicing through MyInvois. This module enables retail businesses using Odoo POS to submit consolidated e-invoices to the Malaysian LHDN MyInvois system.

In retail/POS environments, individual line item invoices are impractical. This module allows POS orders to be consolidated into a single e-invoice submission, which aligns with how retail transactions are typically handled under the Malaysian e-invoicing mandate.

## Dependencies

| Module | Purpose |
|--------|---------|
| [[Modules/l10n_my_edi]] | MyInvois e-invoicing base |
| [[Modules/point_of_sale]] | Point of Sale module |

## Key Models

### `myinvois.document.pos` (myinvois_document_pos.py)
Extends the MyInvois document model for POS-specific consolidated invoicing:
- Consolidation of multiple POS orders into a single e-invoice
- POS-specific transaction handling
- Retail transaction classification

### `pos.order` (pos_order.py)
Extends `pos.order` with MyInvois fields:
- E-invoice submission status
- MyInvois document reference
- POS transaction linking to e-invoice

### `product.product` (product.py)
Extends product for POS with e-invoice classification:
- HS code for POS products
- Product category for MyInvois

### `res.partner` (res_partner.py)
Extends partner with POS-specific e-invoice fields:
- Simplified buyer identification for retail
- TIN/IC number for consumer identification

## Country-Specific Features

### Consolidated Invoicing
In POS environments, multiple transactions are grouped into daily or session-based consolidated e-invoices:
- Groups POS orders by session or defined period
- Combines all line items under single invoice
- Maintains line item detail for LHDN compliance

### POS-Specific Handling
- Cash sales without buyer identification
- Simplified buyer fields for retail consumers
- QR code generation for invoice verification
- Receipt-level tracking linked to e-invoice

## Data Files

- `data/res_partner.xml` - Partner data for POS defaults
- `views/myinvois_document_pos_views.xml` - POS document views
- `views/pos_order_views.xml` - POS order form updates
- `views/product_view.xml` - Product configuration for POS

## Related

- [[Modules/l10n_my_edi]] - Core MyInvois e-invoicing
- [[Modules/l10n_my]] - Base Malaysian accounting
- [[Modules/point_of_sale]] - Point of Sale module
