# l10n_pe - Peru Accounting

## Overview
- **Name:** Peru - Accounting
- **Country:** Peru (PE)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 3.1
- **Author:** Vauxoo, Odoo S.A.
- **License:** LGPL-3
- **Dependencies:** `base_vat`, `base_address_extended`, `l10n_latam_base`, `l10n_latam_invoice_document`, `account_debit_note`, `account`
- **Auto-installs:** `account`

## Description
Peruvian accounting localization with chart of accounts, tax configuration (IGV, ISC), document types (Factura Electronica, Boleta, Nota de Credito, Nota de Debito), and SUNAT compliance.

## Models

### account.chart.template (AbstractModel)
Inherits `account.chart.template`:
- **Template `pe`:**
  - Receivable: `chart1213`, Payable: `chart4212`
  - Code digits: 7
  - Stock valuation: `chart20111`
  - Bank prefix: `1041`, Cash: `1031`, Transfer: `1051`
  - Default sale/purchase tax: IGV 18% (`sale_tax_igv_18`, `purchase_tax_igv_18`)
  - Inventory journal and valuation accounts

### account.move (Inherit)
Extends `account.move`:
- **_get_l10n_latam_documents_domain():** Filters to document codes `01, 03, 07, 08, 20, 40` for sales. For non-RUC partners on sales, restricts to codes `08b, 02, 07b` (simplified/fiscal receipt types)
- **_inverse_l10n_latam_document_number():** Pads the numeric portion of document numbers to 8 digits (e.g., `F01-32` -> `F01-00000032`) and syncs the `name` field accordingly

### res.city (Standalone)
- Adds Peruvian city/district data

### res.city.district (Standalone)
- District-level data linked to cities

## Data Files
- `data/l10n_latam_document_type_data.xml` — Document types (01 Factura, 03 Boleta, 07 Nota de Credito, 08 Nota de Debito, etc.)
- `data/res.city.csv` — Peruvian cities
- `data/l10n_pe.res.city.district.csv` — District data
- `data/res_country_data.xml` — Country data
- `data/l10n_latam_identification_type_data.xml` — Identification types (RUC, DNI, CE, etc.)
- `data/res.bank.csv` — Peruvian banks
- Frontend interaction assets for web

## SUNAT Document Codes
- `01` — Factura Electronica
- `03` — Boleta de Venta Electronica
- `07` — Nota de Credito
- `08` — Nota de Debito
- `20` — Factura Rectificatoria
- `40` — Guia de Remision Electronica
