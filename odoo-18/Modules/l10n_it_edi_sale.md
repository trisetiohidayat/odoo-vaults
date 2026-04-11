---
Module: l10n_it_edi_sale
Version: 18.0
Type: l10n/it/edi/sale
Tags: #odoo18 #l10n #edi #italy #sale
---

# l10n_it_edi_sale

## Overview
Extends `l10n_it_edi` with fields required on `sale.order` for Italian e-invoicing (FatturaPA / SdI). When a sale order is confirmed and converted to an invoice, the SdI needs the origin document reference (CIG, CUP, origin document type/number/date) to properly route and validate the invoice.

## Dependencies
- `l10n_it_edi` (Italian EDI base)
- `sale`

## Key Models

| Class | _name | _inherit | Purpose |
|---|---|---|---|
| `SaleOrder` | `sale.order` | `sale.order` | Adds CIG, CUP, origin document type/name/date fields used in FatturaPA XML |

## Data Files
- `views/sale_order_views.xml` — Sale order form with origin document fields

## How It Works
On sale order confirmation, the origin document fields (CIG code, CUP project code, and origin document reference) are transferred to the generated invoice. SdI uses these fields particularly for:
- **CIG** (Codice Identificativo Gara): Mandatory for public contract invoices
- **CUP** (Codice Unico di Progetto): Required for public investment project invoices
- Origin document reference: Links the invoice to the underlying purchase order, contract, or agreement

## Installation
Auto-installs with `l10n_it_edi` and `sale` loaded. No separate installation needed.

## Historical Notes
- **Odoo 18**: Sale-level EDI fields are new. In earlier versions, CIG/CUP fields existed on `account.move` directly; in Odoo 18 they are set earlier at the sale order stage for traceability.