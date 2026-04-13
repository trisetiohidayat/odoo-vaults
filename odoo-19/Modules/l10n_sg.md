---
type: module
module: l10n_sg
tags: [odoo, odoo19, l10n, localization, singapore]
created: 2026-04-06
---

# Singapore Localization (l10n_sg)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Singapore - Accounting |
| **Technical** | `l10n_sg` |
| **Category** | Localization / Account Charts |
| **Country** | Singapore |
| **Author** | Tech Receptives |
| **Version** | 2.2 |
| **License** | LGPL-3 |
| **Countries** | Singapore (SG) |

## Description

Singapore accounting localization providing a comprehensive chart of accounts and tax templates. The module adds Singapore-specific fields including UEN (Unique Entity Number) for companies and partners, supports GST (Goods and Services Tax) configuration, and integrates EMV QR code payments.

Singapore uses a self-assessment tax system, and the module supports GST reporting required by IRAS (Inland Revenue Authority of Singapore).

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/account](Account.md) | Core accounting |
| [Modules/account_qr_code_emv](account_qr_code_emv.md) | EMV QR code for Singapore QR payments (PayNow) |

## Key Models

### `account.chart.template` (data/l10n_sg_chart_data.xml)
Singapore-specific chart of accounts template:
- Singapore Standard Chart of Accounts
- GST-related accounts
- Proper account code structure for Singapore businesses

### `res.partner` (views/res_partner_view.xml)
Extends partner with Singapore-specific fields:
- **UEN** (Unique Entity Number): 9-10 digit business registration number assigned by ACRA
- UEN type classification (e.g., LL, LP, FC, PF)
- Address formatting per Singapore standards

### `res.company` (views/res_company_view.xml)
Extends company with:
- UEN field for Singapore company registration
- GST registration number field

### `account.move` (views/account_invoice_view.xml)
Extends invoice with:
- **PermitNo**: Permit number for customs/international trade
- **PermitNoDate**: Date of permit issuance
- GST-exclusive invoice fields

### `res.bank` (views/res_bank_views.xml)
Singapore bank configuration with SWIFT/BIC codes.

## Country-Specific Features

### GST (Goods and Services Tax)
- Standard rate: 9% (as of current)
- Zero-rated supplies (0%)
- Exempt supplies
- Out-of-scope supplies
- GST return report (Form F5/F8) configuration

### UEN (Unique Entity Number)
- Every Singapore entity has a unique UEN
- UEN formats:
  - Businesses (RO): 9 digits (e.g., 123456789A)
  - Local Companies (LC): 10 digits (e.g., 123456789A)
  - Others: Various formats
- Required on all invoices for B2B transactions

### QR Code Payments
- PayNow QR code integration
- EMV QR standard for Singapore
- UEN-based payment identification

### Tax Reporting
- IRAS-compliant GST return report (Form F5/F8)
- GST67B support (for approved invoicing)
- File preparation for myTax filing

## Data Files

- `data/l10n_sg_chart_data.xml` - Singapore chart of accounts
- `data/account_tax_report_data.xml` - GST return report (Form F5/F8)
- `views/account_invoice_view.xml` - Invoice view with UEN/permit fields
- `views/res_bank_views.xml` - Bank configuration
- `views/res_company_view.xml` - Company form with UEN
- `views/res_partner_view.xml` - Partner form with UEN
- `demo/demo_company.xml` - Demo company data

## Post-Init Hook

- `_preserve_tag_on_taxes`: Preserves account tags on taxes after installation

## Related

- [Modules/account](Account.md) - Core accounting module
- [Modules/account_qr_code_emv](account_qr_code_emv.md) - QR code generation (PayNow)
- [Modules/l10n_sg_ubl_pint](l10n_sg_ubl_pint.md) - Singapore UBL PINT format for Peppol e-invoicing
