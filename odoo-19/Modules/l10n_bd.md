---
type: module
module: l10n_bd
tags: [odoo, odoo19, l10n, localization, bangladesh]
created: 2026-04-06
---

# Bangladesh Localization (l10n_bd)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Bangladesh - Accounting |
| **Technical** | `l10n_bd` |
| **Category** | Localization / Account Charts |
| **Country** | Bangladesh |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |
| **License** | LGPL-3 |
| **Countries** | Bangladesh (BD) |

## Description

Bangladesh accounting localization providing a chart of accounts, tax templates, and tax reporting structures for businesses operating in Bangladesh. The module supports Bangladesh's VAT (Value Added Tax) system under the VAT Act, 1991 and subsequent amendments.

Bangladesh has a comprehensive VAT system administered by the NBR (National Board of Revenue).

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/account](Modules/Account.md) | Core accounting |

## Key Models

### `account.chart.template` (template_bd.py)
Extends chart of accounts with Bangladesh-specific template:
- Bangladesh chart of accounts structure
- VAT accounts
- Tax suspense accounts

## Country-Specific Features

### Bangladesh Tax Structure
- **VAT (Value Added Tax)**: Standard 15% rate (with various reduced rates)
- **Supplementary Duty**: Additional duty on specific luxury goods
- **Income Tax**: Corporate tax rates (varies by entity type)
- **Withholding Tax**: Various rates on payments to residents

### VAT Rates in Bangladesh
- Standard Rate: 15%
- Reduced Rate: 5%, 7.5%
- Zero-rated: 0%
- Exempt supplies

### Tax Reporting
- Monthly VAT Return (VAT-3.1 / 3.2 / 3.3)
- Annual VAT Return
- Supplementary Duty reporting
- Withholding tax schedule

### TIN (Tax Identification Number)
- 10-digit or 12-digit format
- Required for VAT registration
- Required on all VAT invoices

### VAT Invoice Requirements
- TIN of supplier and buyer
- Invoice number and date
- Description, quantity, and value of goods/services
- VAT amount and rate
- Total amount including VAT

## Data Files

- `data/account.account.tag.csv` - Account tags for tax classification
- `data/account_tax_report_data.xml` - Bangladesh tax report structures
- `views/menu_items.xml` - Navigation menu additions
- `demo/demo_company.xml` - Demo company data

## Related

- [Modules/account](Modules/Account.md) - Core accounting module
- [NBR Bangladesh](https://www.nbr.gov.bd)
