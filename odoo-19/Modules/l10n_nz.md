---
type: module
module: l10n_nz
tags: [odoo, odoo19, l10n, localization, newzealand]
created: 2026-04-06
---

# New Zealand Localization (l10n_nz)

## Overview

| Property | Value |
|----------|-------|
| **Name** | New Zealand - Accounting |
| **Technical** | `l10n_nz` |
| **Category** | Localization / Account Charts |
| **Country** | New Zealand |
| **Author** | Odoo S.A., Richard deMeester - Willow IT |
| **Version** | 1.2 |
| **License** | LGPL-3 |
| **Countries** | New Zealand (NZ) |

## Description

New Zealand accounting localization providing a chart of accounts and tax templates for businesses operating in New Zealand. The module activates regional currencies, sets up New Zealand Goods and Services Tax (GST), and includes tax reporting structures.

New Zealand operates a broad-based GST system at a single rate, with no state or provincial taxes.

## Dependencies

| Module | Purpose |
|--------|---------|
| [[Modules/account]] | Core accounting |

## Key Models

### `account.chart.template` (template_nz.py)
Extends chart of accounts with New Zealand-specific template:
- New Zealand chart of accounts structure
- GST-related accounts
- IRD (Inland Revenue Department) reporting accounts

### `account.move` (account_move.py)
Extends `account.move` with New Zealand fields:
- GST reporting classifications
- Invoice type for GST purposes

### `account.payment` (account_payment.py)
Extends payment model with New Zealand-specific fields.

### `res.partner` (res_partner.py)
Extends partner with New Zealand fields:
- **GST Number**: New Zealand Business Number (NZBN) or GST registration number
- Address formatting for New Zealand

### `res.company` (res_company.py)
Extends company with:
- GST registration number
- IRD number

## Country-Specific Features

### New Zealand GST (Goods and Services Tax)
- **Standard Rate**: 15%
- **Zero-rated**: 0% for exported goods and services
- **Exempt**: Financial services, residential accommodation
- GST is included in the price (price-exclusive method also available)

### Tax Reporting
- GST Return preparation
- IR10 financial report requirements
- Monthly, 2-monthly, or 6-monthly filing options
- IRIS (Inland Revenue Information System) compatible

### NZBN (New Zealand Business Number)
- 13-digit unique identifier for all NZ businesses
- Required on GST invoices
- Linked to IRD number

### IRD Number
- 8-digit Inland Revenue Department number
- 9-digit format for individuals
- Required for payroll and tax purposes

## Data Files

- `data/account_tax_report_data.xml` - New Zealand tax report structures
- `data/res_currency_data.xml` - NZD (New Zealand Dollar) currency
- `views/report_invoice.xml` - Invoice report customization
- `views/res_company_views.xml` - Company configuration
- `views/res_partner_views.xml` - Partner configuration
- `demo/demo_company.xml` - Demo company data

## Related

- [[Modules/account]] - Core accounting module
- [[Modules/l10n_anz_ubl_pint]] - ANZ UBL PINT format for e-invoicing
- [IRD New Zealand](https://www.ird.govt.nz)
- [NZBN Registry](https://www.nzbn.govt.nz)
