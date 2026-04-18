---
type: module
module: l10n_jp
tags: [odoo, odoo19, l10n, localization, japan]
created: 2026-04-06
---

# Japan Localization (l10n_jp)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Japan - Accounting |
| **Technical** | `l10n_jp` |
| **Category** | Localization / Account Charts |
| **Country** | Japan |
| **Author** | Quartile Limited (https://www.quartile.co/) |
| **Version** | 2.3 |
| **License** | LGPL-3 |
| **Countries** | Japan (JP) |

## Description

Japanese accounting localization providing a chart of accounts and tax templates for companies operating in Japan. The module is maintained by Quartile Limited and includes fiscal positions for handling Japan's complex consumption tax system.

Japan uses a consumption tax system (類似税, resembling VAT/GST) at a standard rate of 10% (with a reduced 8% rate for certain essential goods).

**Note**: Fiscal positions "内税" (included tax) and "外税" (excluded tax) are included to handle special requirements from POS implementation.

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/account](Modules/Account.md) | Core accounting |

## Key Models

This is primarily a data-only localization module. The chart of accounts and tax templates are loaded through data files.

## Country-Specific Features

### Japan Consumption Tax (消費税)
- **Standard Rate**: 10% (since October 2019)
- **Reduced Rate**: 8% for qualifying essential goods (foods, beverages, newspapers - until September 2026)
- Consumption tax is not included in displayed prices (外税 / excluded tax)
- Can be handled as included tax (内税 / included tax) for POS

### Tax Reporting
- 消費税率 (consumption tax) reporting
- Invoice-compliant tax rates for reduced rate supplies
- Simplified tax calculation for small businesses

### Japan Account Structure
- Chart of accounts following Japanese accounting conventions
- Consumption tax accounts (仮受消費税, 仮払消費税)
- Supporting the 2-tier reduced rate system

### Fiscal Positions
- **内税 (Included Tax)**: Prices include consumption tax
- **外税 (Excluded Tax)**: Prices exclude consumption tax (standard)
- Used primarily for POS implementations

### Business Registration Number
- 法人番号 (Houjin Bangou): 13-digit corporate number
- TID (Tax Office ID): Used for e-invoice metadata

## Data Files

- `data/account_tax_report_data.xml` - Japanese tax report structures
- `demo/demo_company.xml` - Demo company data

## Related

- [Modules/account](Modules/Account.md) - Core accounting module
- [National Tax Agency Japan](https://www.nta.go.jp)
