---
type: module
module: l10n_ca
tags: [odoo, odoo19, localization, canada]
created: 2026-04-06
---

# Canada - Canadian Accounting

## Overview
| Property | Value |
|----------|-------|
| **Name** | Canada - Accounting |
| **Technical** | `l10n_ca` |
| **Category** | Localization |
| **Country** | Canada |

## Description
Canadian accounting module providing HST/GST+PST tax structures per province. Supports fiscal positions based on delivery province, and provincial tax configurations for BC, MB, QC, SK, ON, NB, NL, NS, and PE.

## Dependencies
- `account`
- `base_iban`

## Key Models

### `account.chart.template` (template_ca.py)
Extends `account.chart.template` with Canadian template data.

**Template data** (`_get_ca_template_data`):
- `property_account_receivable_id`: `l10n_ca_112110`
- `property_account_payable_id`: `l10n_ca_221110`
- `property_stock_valuation_account_id`: `l10n_ca_121120`

**Company defaults** (`_get_ca_res_company`):
- `anglo_saxon_accounting`: True
- `account_fiscal_country_id`: `base.ca`
- Provincial default taxes based on company state code:
  - BC: GST 5% + PST 7% (`gstpst_sale_tax_12_bc`)
  - MB: GST 5% + PST 7% (`gstpst_sale_tax_12_mb`)
  - QC: GST 5% + QST 9.975% (`gstqst_sale_tax_14975`)
  - SK: GST 5% + PST 6% (`gstpst_sale_tax_11`)
  - ON: HST 13% (`hst_sale_tax_13`)
  - NB/NL: HST 15% (`hst_sale_tax_15`)
  - NS: HST 14% (`hst_sale_tax_14`)
  - PE: HST 15% (`hst_sale_tax_15`)
  - Other: GST 5% default

## Account Charts
- Chart of Accounts: Canadian chart
- Tax Templates: GST, HST, PST, QST per province

## Related
- [[Modules/account]]
