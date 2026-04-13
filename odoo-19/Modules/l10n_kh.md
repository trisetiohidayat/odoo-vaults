---
type: module
module: l10n_kh
tags: [odoo, odoo19, l10n, localization, cambodia]
created: 2026-04-06
---

# Cambodia Localization (l10n_kh)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Cambodia - Accounting |
| **Technical** | `l10n_kh` |
| **Category** | Localization / Account Charts |
| **Country** | Cambodia |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |
| **License** | LGPL-3 |
| **Countries** | Cambodia (KH) |

## Description

Cambodia accounting localization providing a chart of accounts and tax structures for businesses operating in Cambodia. The module includes support for Cambodia's tax reporting requirements including the monthly tax declaration (Form T1) and withholding tax reporting.

Cambodia uses a Self-Assessment Tax System and requires monthly and annual tax declarations.

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/account](Account.md) | Core accounting |
| [Modules/account_qr_code_emv](account_qr_code_emv.md) | EMV QR code generation |
| [Modules/l10n_account_withholding_tax](l10n_account_withholding_tax.md) | Withholding tax support |

## Key Models

### `account.chart.template` (template_kh.py)
Extends chart of accounts with Cambodia-specific template:
- Cambodian account code structure
- Tax accounts for PIT, VAT, and other taxes
- Salary and withholding tax accounts

### `res.bank` (res_bank.py)
Extends bank model with Cambodia-specific fields:
- Cambodia bank identification
- Banking system codes

## Country-Specific Features

### Cambodia Tax Structure
- **Salary Tax (PIT)**: Progressive tax on employment income
- **Fringe Benefit Tax**: Tax on non-cash benefits
- **Withholding Tax**: On various payments (royalties, services, rentals, etc.)
- **Tax on Profit**: Corporate income tax (20% standard rate)
- **VAT**: 10% standard rate

### Tax Forms
- **T1 (Monthly Tax Declaration)**: Combined monthly tax form
- **WT003**: Withholding tax certificate
- **T2-T8**: Various specific tax declarations

### Withholding Tax Rates (Common)
- Royalties: 15%
- Services: 15%
- Rental: 10%
- Salary: Progressive rates
- Import: 0% or exemption

### TIN (Tax Identification Number)
- 9-digit format: XXX-XXX-XXXX
- Required for all registered taxpayers

## Data Files

- `data/form_t7001.xml` - Cambodia tax form templates
- `data/form_wt003.xml` - Withholding tax form (WT003)
- `views/res_bank_views.xml` - Bank configuration
- `demo/demo_company.xml` - Demo company data

## Related

- [Modules/account](Account.md) - Core accounting module
- [Modules/account_qr_code_emv](account_qr_code_emv.md) - QR code generation
- [Modules/l10n_account_withholding_tax](l10n_account_withholding_tax.md) - Withholding tax support
