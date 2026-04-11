---
type: module
module: l10n_pk
tags: [odoo, odoo19, l10n, localization, pakistan]
created: 2026-04-06
---

# Pakistan Localization (l10n_pk)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Pakistan - Accounting |
| **Technical** | `l10n_pk` |
| **Category** | Localization / Account Charts |
| **Country** | Pakistan |
| **Author** | Odoo S.A. |
| **Version** | 1.1 |
| **License** | LGPL-3 |
| **Countries** | Pakistan (PK) |

## Description

Pakistan accounting localization providing a chart of accounts, tax templates, and tax reporting structures for businesses operating in Pakistan. The module includes support for Pakistan's General Sales Tax (GST) system, withholding tax reporting, and FBR (Federal Board of Revenue) compliance.

Pakistan uses a combination of federal GST and provincial sales taxes that need to be properly tracked and reported.

## Dependencies

| Module | Purpose |
|--------|---------|
| [[Modules/account]] | Core accounting |

## Key Models

### `account.chart.template` (template_pk.py)
Extends chart of accounts with Pakistan-specific template:
- Pakistan Chart of Accounts structure
- Federal and provincial tax accounts
- Withholding accounts

## Country-Specific Features

### Tax Structure
- **Federal GST (Goods and Services Tax)**: Standard rate on supplies
- **Provincial Sales Tax (PST)**: Varies by province (Sindh, Punjab, Khyber Pakhtunkhwa, Balochistan)
- **Withholding Tax (WHT)**: Various rates for payments to residents
- Advance income tax on banking transactions

### Tax Reporting
- **Sales Tax Report**: Federal GST monthly/annual returns
- **Withholding Tax Report**: Statement of withholding taxes (Form annual/quarterly)
- Provincial sales tax reporting
- STNA (Sales Tax Notification for Agriculture) support

### NTN (National Tax Number)
- 7-digit business NTN format
- Required on all tax invoices
- CNIC (Computerized National Identity Card) for individuals

### FBR Compliance
- GST invoice requirements per FBR specifications
- Tax withheld at source tracking
- Monthly sales tax return (STR) preparation

## Data Files

- `data/account_tax_vat_report.xml` - VAT/Sales Tax report templates
- `data/account_tax_wh_report.xml` - Withholding tax report templates
- `demo/res_partner_demo.xml` - Demo partner data
- `demo/demo_company.xml` - Demo company data

## Related

- [[Modules/account]] - Core accounting module
- [FBR Pakistan](https://www.fbr.gov.pk)
