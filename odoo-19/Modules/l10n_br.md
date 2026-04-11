# l10n_br - Brazil Accounting

## Overview
- **Name:** Brazilian - Accounting
- **Country:** Brazil (BR)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 1.1
- **Author:** Akretion, Odoo Brasil
- **License:** LGPL-3
- **Dependencies:** `account`, `account_qr_code_emv`, `base_address_extended`, `l10n_latam_base`, `l10n_latam_invoice_document`
- **Auto-installs:** `account`

## Description
Base module for Brazilian localization. Provides:
- Generic Brazilian chart of accounts (6-digit codes)
- Brazilian taxes: IPI, ICMS, PIS, COFINS, ISS, IR, CSLL
- Document types: NFC-e, NFS-e, etc.
- Identification documents: CNPJ and CPF

## Models

### account.chart.template (AbstractModel)
Inherits `account.chart.template`:
- **Template `br`:**
  - Receivable: `account_template_101010401`, Payable: `account_template_201010301`
  - Code digits: 6
  - Bank prefix: `1.01.01.02.00`, Cash prefix: `1.01.01.01.00`, Transfer: `1.01.01.12.00`
  - POS receivable: `account_template_101010402`
  - Default sale tax: ICMS 17% (`tax_template_out_icms_interno17`)
  - Default purchase tax: ICMS 17%
  - Inventory valuation accounts
- **Journals:** Sets sale journal `l10n_br_invoice_serial` to '1', disables refund sequence

### account.tax (Inherit)
Extends `account.tax` with Brazilian tax fields:
- **tax_discount:** Boolean — discounts this tax from the price (used for ICMS, PIS, etc.)
- **base_reduction:** Float — decimal percentage (0-1) for tax base reduction (e.g., MVA-adjusted base)
- **amount_mva:** Float — MVA (Margem de Valor Agregado) percentage for ST (Substituicao Tributaria)

### account.fiscal.position (Inherit)
Extends `account.fiscal.position`:
- **l10n_br_fp_type:** Selection — `internal`, `ss_nnm` (South/Southeast selling to North/Northeast/Midwest), `interstate`
- **_get_fiscal_position():** Auto-detects fiscal position based on company and partner state. Interstate ICMS rates differ depending on trade corridor (South/Southeast vs. other routes).

### res.city (Inherit)
Extends `res.city`:
- **l10n_br_zip_range_ids:** One2many to `l10n_br.zip.range` — maps city to zip code ranges
- **l10n_br_zip_ranges:** Computed Char — formatted zip ranges for frontend display

### l10n_br.zip.range (Standalone Model)
- **city_id:** Many2one to `res.city`
- **start / end:** ZIP code range (format: `XXXXX-XXX`)
- **_check_range():** Validates format (5 digits - 3 digits) and that start < end
- Constraints: unique start, unique end

### res.partner.bank (Inherit)
Extends `res.partner.bank` with Pix payment support:
- **proxy_type:** Adds `email`, `mobile`, `br_cpf_cnpj`, `br_random` (Random Key) for Pix
- **_check_br_proxy():** Validates proxy values (email format, CPF/CNPJ checksum, mobile +55 format, UUID format)
- **_compute_country_proxy_keys():** Shows BR proxy keys for Brazilian banks
- **_compute_display_qr_setting():** Always shows QR setting for BR
- **_get_additional_data_field():** Serializes comment for Pix spec
- **_get_qr_code_vals_list():** Formats QR code for Brazilian Pix — forces 2-decimal amount, uppercase merchant name/city
- **_get_merchant_account_info():** Returns Pix URI (`br.gov.bcb.pix`) with proxy key
- **_get_error_messages_for_qr():** Enforces BRL currency for Pix QR codes
- **_check_for_qr_code_errors():** Requires valid proxy type for Pix

## Data Files
- `data/account_tax_report_data.xml` — Brazilian tax report
- `data/res_country_data.xml` — Country data
- `data/res.city.csv` — Brazilian cities
- `data/l10n_br.zip.range.csv` — Zip code ranges
- `data/l10n_latam.identification.type.csv` — CNPJ/CPF identification types
- `data/l10n_latam.document.type.csv` — Document types (NFC-e, NFS-e, etc.)
- Views for: partner, account, fiscal position, company, journal, bank
- Frontend assets for interactive features

## Related Modules
- **l10n_br_pix** — Pix payment integration
- **l10n_br_website_sale** — Brazilian e-commerce
- **l10n_br_avatax** — Avatax Brazil tax calculation
- **l10n_br_avatax_sale** — Avatax on Sales Orders
- **l10n_br_edi** — Electronic invoicing via Avatax
