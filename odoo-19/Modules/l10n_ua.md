---
type: module
module: l10n_ua
tags: [odoo, odoo19, l10n, localization, ukraine, accounting]
created: 2026-04-06
---

# Ukraine Accounting Localization (`l10n_ua`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Ukraine - Accounting |
| **Technical** | `l10n_ua` |
| **Category** | Accounting/Localizations/Account Charts |
| **Country** | Ukraine (UA) |
| **Currency** | UAH (Ukrainian Hryvnia) |
| **License** | LGPL-3 |
| **Author** | ERP Ukraine (https://erp.co.ua) |
| **Version** | 1.4 |

## Description

Ukrainian accounting chart of accounts module. Provides the accounting structure required for Ukrainian compliance.

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/Account](odoo-18/Modules/account.md) | Core accounting framework |

## Auto-Install

Auto-installs with `account` when the company's country is set to Ukraine.

## Key Components

### Chart of Accounts (PSBO)

The module implements the Ukrainian Chart of Accounts based on the National Accounting Regulations (П(С)БО):
- Class 0-9 account structure
- Fixed assets classification
- Inventory accounts
- Third-party accounts (receivables, payables)
- Equity and liability accounts

### Data File

`data/account_account_tag_data.xml` - Account tags for Ukrainian tax reporting and classification.

## Models

### Template: `template_ua_psbo`

Loads Ukrainian-specific:
- Chart of accounts data (PSBO-based)
- Account tags for Ukrainian reporting
- Analytic account structure

## Ukrainian-Specific Considerations

### Currency

- Ukrainian Hryvnia (UAH)
- Standard accounting in whole Hryvnia units (no kopeks stored)

### VAT (PDV - Податок на додану вартість)

Standard Ukrainian VAT rate:
- **20%** - Standard rate
- **14%** - Reduced rate for certain goods
- **0%** - Zero rate / exempt

### Tax ID (EDRPOU)

Ukrainian Unified State Register of Enterprises and Organizations (ЄДРПОУ):
- 8-digit registration number
- Used for B2G transactions
- Separate from individual tax number (ІПН)

## Configuration

1. Install the module via Apps
2. Set company country to Ukraine
3. Configure Ukrainian registration numbers in company settings
4. Set up Ukrainian bank accounts (MFO/IBAN format)

## Technical Notes

- Version 1.4 maintained by ERP Ukraine community
- Does not include EDI/e-invoicing (no dedicated l10n_ua_edi module in Odoo 19)
- PSBO-based chart of accounts
- Cyrillic support in company and partner names

## Related Modules

This module is standalone. There is no dedicated EDI module for Ukraine in the standard Odoo 19 distribution.

## See Also

- [Modules/Account](odoo-18/Modules/account.md) - Core accounting
