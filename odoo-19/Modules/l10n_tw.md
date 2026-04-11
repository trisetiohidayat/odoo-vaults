---
type: module
module: l10n_tw
tags: [odoo, odoo19, l10n, localization, taiwan]
created: 2026-04-06
---

# Taiwan Localization (l10n_tw)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Taiwan - Accounting |
| **Technical** | `l10n_tw` |
| **Category** | Localization / Account Charts |
| **Country** | Taiwan |
| **Author** | Odoo PS |
| **Version** | 1.0 |
| **License** | LGPL-3 |
| **Countries** | Taiwan (TW) |

## Description

Base accounting localization for Taiwan providing a chart of accounts, tax templates, and Taiwan-specific configurations for businesses operating in Taiwan. The module also activates regional currencies and provides address formatting for Taiwan.

Taiwan uses a business tax system similar to VAT/GST, and the module supports the tax reporting requirements for businesses registered in Taiwan.

## Dependencies

| Module | Purpose |
|--------|---------|
| [[Modules/account]] | Core accounting |
| [[Modules/base_address_extended]] | Extended address formatting with city/county fields |

## Key Models

### `account.chart.template` (template_tw.py)
Extends chart of accounts with Taiwan-specific template:
- Taiwan chart of accounts structure
- Business tax accounts
- Profit tax accounts

## Country-Specific Features

### Taiwan Tax System
- **Business Tax (營業稅)**: Similar to VAT, collected on sales
- **Corporate Income Tax**: 17% for Taiwan enterprises (subject to changes)
- **Withholding Tax**: Various rates for different payment types

### Taiwan Address Format
- Full address fields compatible with Taiwan's address system
- City/county and district/section formatting
- Support for Chinese and English address display

### Currency
- TWD (New Taiwan Dollar) configuration
- Regional currency data activation

### Tax Reporting
- Business tax returns (Form 401, 403, 404)
- Electronic invoice support through [[Modules/l10n_tw_edi_ecpay]]

## Data Files

- `data/res_currency_data.xml` - Taiwan Dollar (TWD) currency configuration
- `data/res_country_data.xml` - Taiwan country data
- `data/res.city.csv` - Taiwan cities and districts data
- `data/tax_report_401.xml` - Business tax return (General)
- `data/tax_report_403.xml` - Business tax return (Specific)
- `data/tax_report_404.xml` - Business tax return (Mixed)
- `demo/demo_company.xml` - Demo company data

## Related

- [[Modules/account]] - Core accounting module
- [[Modules/base_address_extended]] - Extended address support
- [[Modules/l10n_tw_edi_ecpay]] - E-invoicing via ECPay
- [[Modules/l10n_tw_edi_ecpay_website_sale]] - E-commerce e-invoice bridge
