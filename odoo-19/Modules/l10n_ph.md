---
type: module
module: l10n_ph
tags: [odoo, odoo19, l10n, localization, philippines]
created: 2026-04-06
---

# Philippines Localization (l10n_ph)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Philippines - Accounting |
| **Technical** | `l10n_ph` |
| **Category** | Localization / Account Charts |
| **Country** | Philippines |
| **Author** | Odoo PS |
| **Version** | 1.1 |
| **License** | LGPL-3 |
| **Countries** | Philippines (PH) |

## Description

Philippine accounting localization providing a chart of accounts, tax templates, withholding tax structures, and BIR (Bureau of Internal Revenue) compliance features for businesses operating in the Philippines.

The module integrates with [Modules/l10n_account_withholding_tax](l10n_account_withholding_tax.md) to support Philippine withholding tax requirements including the BIR Form 2307 (Certificate of Final Tax Withheld at Source) for expanded withholding tax and creditable withholding tax.

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/account](Account.md) | Core accounting |
| [Modules/base_vat](base_vat.md) | VAT number validation |
| [Modules/l10n_account_withholding_tax](l10n_account_withholding_tax.md) | Withholding tax support (BIR Form 2307) |

## Key Models

### `account.chart.template` (template_ph.py)
Extends chart of accounts with Philippine-specific template:
- Philippine Chart of Accounts aligned with PFRS
- Tax accounts for VAT, withholding taxes
- Expanded/Creditable withholding tax accounts

### `account.tax` (account_tax.py)
Extends tax model with Philippine-specific fields:
- BIR tax type classification
- ATC (Alphanumeric Tax Code) references
- EWT (Expanded Withholding Tax) / CWT (Creditable Withholding Tax) configuration

### `account.move` (account_move.py)
Extends `account.move` with Philippine fields:
- BIR invoice type
- Place of rendering/service fields
- TIN (Taxpayer Identification Number) display

### `account.payment` (account_payment.py)
Extends payment model:
- Withholding tax application
- BIR payment forms integration

### `res.partner` (res_partner.py)
Extends partner with Philippine fields:
- **TIN** (Tax Identification Number): 12-digit BIR tax number
- **BIR Form Type**: Classification for BIR reporting
- **RDO Code**: Revenue District Office code

### `res.company` (res_company.py)
Company-level Philippine fields:
- TIN and branch code
- BIR registration details
- RDO assignment

## Country-Specific Features

### Philippine Tax Structure
- **VAT (Value Added Tax)**: Standard 12%
- **EWT (Expanded Withholding Tax)**: Various rates per ATC code
- **CWT (Creditable Withholding Tax)**: Various rates for professional fees, rentals, etc.
- **Final Withholding Tax**: For certain payments
- Withholding tax rates based on BIR regulation

### BIR Forms and Reports
- **BIR Form 2307**: Certificate of Final Tax Withheld at Source
- **BIR Form 2550M/Q**: Monthly/Quarterly VAT Declaration
- Withholding tax schedule reports
- 0619 ESPD (Electronic Statement of Payee)

### Withholding Tax Computation
The module supports the generation of BIR Form 2307 (Certificate of Creditable/Expanded Withholding Tax Withheld):
- Automatic computation of withholding amounts
- Tax type and ATC code assignment per supplier
- BIR-formatted certificate generation

### TIN Format
- 12-digit format: XXX-XXX-XXX-XXX
- First 9 digits: BIR TIN
- Last 3 digits: Branch code

## Data Files

- `data/account_tax_report_data.xml` - Philippine tax report structures
- `wizard/generate_2307_wizard_views.xml` - BIR Form 2307 generation wizard
- `views/account_move_views.xml` - Invoice form customization
- `views/account_payment_views.xml` - Payment form updates
- `views/account_tax_views.xml` - Tax form updates
- `views/res_company_views.xml` - Company configuration
- `views/res_partner_views.xml` - Partner configuration
- `views/report_disbursement_voucher_template.xml` - Disbursement voucher report
- `views/account_report.xml` - Account report menus
- `views/report_templates.xml` - Report templates
- `security/ir.model.access.csv` - Access rights
- `demo/demo_company.xml` - Demo company data

## Related

- [Modules/account](Account.md) - Core accounting module
- [Modules/l10n_account_withholding_tax](l10n_account_withholding_tax.md) - Withholding tax support
- [Modules/base_vat](base_vat.md) - Tax ID validation
