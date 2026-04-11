---
type: module
module: l10n_hk
tags: [odoo, odoo19, l10n, localization, hongkong]
created: 2026-04-06
---

# Hong Kong Localization (l10n_hk)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Hong Kong - Accounting |
| **Technical** | `l10n_hk` |
| **Category** | Localization / Account Charts |
| **Country** | Hong Kong SAR |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |
| **License** | LGPL-3 |
| **Countries** | Hong Kong (HK) |

## Description

Hong Kong accounting localization providing a chart of accounts for companies operating in Hong Kong. The module includes Hong Kong bank information and supports EMV QR code payments for the Faster Payment System (FPS) through [[Modules/account_qr_code_emv]].

Hong Kong does not have a broad-based GST or VAT, but businesses must comply with the IRD (Inland Revenue Department) requirements for profits tax.

## Dependencies

| Module | Purpose |
|--------|---------|
| [[Modules/account]] | Core accounting |
| [[Modules/account_qr_code_emv]] | EMV QR code for FPS (Faster Payment System) QR payments |

## Key Models

### `account.chart.template` (template_hk.py)
Extends chart of accounts with Hong Kong-specific template:
- Hong Kong chart of accounts
- Profits tax accounts
- IRD reporting-related account structures

### `res.bank` (res_bank.py)
Extends bank model with Hong Kong-specific fields:
- Hong Kong bank codes (3-digit bank codes)
- FPS (Faster Payment System) identifier
- SWIFT/BIC codes for international transfers

## Country-Specific Features

### Hong Kong Tax System
- **Profits Tax**: Main business tax (16.5% for corporations, 15% for unincorporated businesses)
- **Salaries Tax**: Employee income tax withholding
- **Property Tax**: Rental income tax
- No GST/VAT in Hong Kong

### FPS QR Payments
- Faster Payment System QR code generation
- FPS Identifier (FPS ID) or mobile number linking
- HKD currency support for FPS transactions
- EMV QR standard for Hong Kong

### Business Registration
- BR Number (Business Registration Number): 8-digit format
- Required on all invoices and receipts
- CIR (Company Incorporation Number) for companies

### Record Keeping
- 7-year record retention requirement per IRD
- Bilingual documentation support (English/Chinese)

## Data Files

- `data/account_chart_template_data.xml` - Hong Kong chart of accounts
- `views/res_bank_views.xml` - Bank configuration views
- `demo/demo_company.xml` - Demo company data

## Related

- [[Modules/account]] - Core accounting module
- [[Modules/account_qr_code_emv]] - FPS QR code generation
- [IRD Hong Kong](https://www.ird.gov.hk)
