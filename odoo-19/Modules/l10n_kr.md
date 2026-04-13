---
type: module
module: l10n_kr
tags: [odoo, odoo19, l10n, localization, korea, southkorea]
created: 2026-04-06
---

# Korea (South Korea) Localization (l10n_kr)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Republic of Korea - Accounting |
| **Technical** | `l10n_kr` |
| **Category** | Localization / Account Charts |
| **Country** | South Korea |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |
| **License** | LGPL-3 |
| **Countries** | South Korea (KR) |

## Description

South Korean accounting localization providing a base chart of accounts and tax templates for companies operating in Korea. The module includes templates for general tax reporting including corporate income tax and VAT (Value Added Tax) in Korea's self-assessment tax system.

Korea has a comprehensive VAT system administered by the NTS (National Tax Service).

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/account](Modules/account.md) | Core accounting |

## Key Models

This is primarily a data-only localization module. The chart of accounts and tax templates are loaded through data files.

## Country-Specific Features

### Korea Tax Structure
- **VAT (Value Added Tax / 부가가치세)**: Standard 10% rate
- **Corporate Income Tax (법인세)**: Progressive rates (10-25% for companies)
- **Local Income Tax (지방소득세)**: 10% of corporate income tax
- **Withholding Tax (원천세)**: Various rates on payments to non-residents
- **Acquisition / Registration Tax**: On property transactions

### VAT in Korea
- Standard rate: 10%
- Zero-rated supplies (0%): Exports, international transportation
- Exempt supplies: Financial services, medical, educational
- Quarterly or monthly filing depending on company size

### Tax Reporting
- 부가가치세 신고서 (VAT Return)
- 일반부가가치세 신고서 (General VAT Return)
- 간이부가가치세 신고서 (Simplified VAT Return)
- 원천징수 intermediary reporting

### Business Registration Number
- 사업자등록번호 (Business Registration Number): 10 digits
- Required on all tax invoices
- Format: XXX-XX-XXXXX
- Linked to NTS registry

### Invoice Requirements (Korea)
- 사업자등록번호 of both parties
- Tax invoice number
- Date of supply
- Description and quantity
- Unit price and total
- VAT amount
- Classification (과세/면세/영세)

## Data Files

- `data/res_country_data.xml` - Korea country data
- `data/general_tax_report.xml` - General tax report template
- `data/simplified_tax_report.xml` - Simplified tax report template
- `demo/demo_company.xml` - Demo company data

## Related

- [Modules/account](Modules/account.md) - Core accounting module
- [NTS Korea](https://www.nts.go.kr)
