---
type: module
module: l10n_lk
tags: [odoo, odoo19, l10n, localization, srilanka]
created: 2026-04-06
---

# Sri Lanka Localization (l10n_lk)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Sri Lanka - Accounting |
| **Technical** | `l10n_lk` |
| **Category** | Localization / Account Charts |
| **Country** | Sri Lanka |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |
| **License** | LGPL-3 |
| **Countries** | Sri Lanka (LK) |

## Description

Sri Lanka accounting localization providing a chart of accounts, tax templates, fiscal positions, and tax forms for businesses operating in Sri Lanka. The module supports VAT and Withholding Tax (WHT) reporting as required by the Sri Lankan tax authority (IRD - Inland Revenue Department).

Sri Lanka transitioned from the GST-type VAT system to an Income Tax-based system but VAT remains applicable for certain transactions.

## Dependencies

| Module | Purpose |
|--------|---------|
| [[Modules/account]] | Core accounting |
| [[Modules/l10n_account_withholding_tax]] | Withholding tax support |

## Key Models

### `account.chart.template` (template_lk.py)
Extends chart of accounts with Sri Lanka-specific template:
- Sri Lankan account code structure
- Tax accounts for VAT and withholding tax
- Withholding tax suspense accounts

## Country-Specific Features

### Sri Lanka Tax Structure
- **VAT (Value Added Tax)**: Standard 15% rate
- **Withholding Tax (WHT)**: Various rates on payments to residents
- **Corporate Income Tax**: 24% (for companies), progressive for individuals
- **Economic Service Charge (ESC)**: 0.5% on turnover
- **Debit Tax**: On certain payments
- **Stamp Duty**: On legal documents

### Tax Forms
- **VAT001**: VAT Return form
- **WHT001**: Withholding Tax Certificate

### Withholding Tax Rates
- Dividends: 14%
- Interest: 5%
- Royalties, management fees, technical services: 15%
- Rent, payments for public transport, tolls: 5%

### TIN Format
- 10-digit or 12-digit format
- Required on all tax invoices

### Fiscal Positions
- VAT-registered supplier position
- Non-VAT-registered supplier position
- Withholding tax applicability positions

## Data Files

- `data/form_vat001.xml` - VAT Return form (VAT001)
- `data/form_wht001.xml` - Withholding Tax form (WHT001)
- `demo/demo_company.xml` - Demo company data

## Related

- [[Modules/account]] - Core accounting module
- [[Modules/l10n_account_withholding_tax]] - Withholding tax support
- [IRD Sri Lanka](https://www.ird.gov.lk)
