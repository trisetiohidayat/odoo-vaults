---
type: module
module: l10n_hr_kuna
tags: [odoo, odoo19, l10n, localization, croatia, currency, historical]
created: 2026-04-06
---

# Croatia Kuna Currency (`l10n_hr_kuna`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Croatia - Accounting (Kuna) |
| **Technical** | `l10n_hr_kuna` |
| **Category** | Accounting/Localizations/Account Charts |
| **Country** | Croatia (HR) |
| **Currency** | HRK (Croatian Kuna) - **DEPRECATED** |
| **License** | LGPL-3 |
| **Author** | OpenERP Croatian Community (Goran Kliska, Slobodni programi d.o.o.) |
| **Version** | 13.0 |

## Description

This module provides the Croatian Chart of Accounts based on the **RRIF 2012** standard, designed for use with the Croatian Kuna (HRK) currency. It is a **legacy module** maintained for historical reference only.

Croatia transitioned from the Kuna (HRK) to the Euro (EUR) on **January 1, 2023**. New implementations should use [Modules/l10n_hr](modules/l10n_hr.md) which is designed for EUR.

### Account Structure (RRIF 2012)

The chart of accounts follows RRIF (Računovodstvo, revizija, financije i kontroling) standards:
- Account types matching Croatian legal requirements
- Tax groups for Croatian VAT return reporting
- Core fiscal positions

### Original Contributors

- **Goran Kliska**, Slobodni programi d.o.o., Zagreb
- **Tomislav Bošnjaković**, Storm Computers (account types)
- **Ivan Vađić**, Slobodni programi (account types)

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/Account](modules/account.md) | Core accounting framework |

## Auto-Install

Does **not** auto-install - must be installed manually.

## Chart of Accounts

The RRIF 2012 chart includes:
- **Class 0**: Non-current assets
- **Class 1**: Non-current assets (pending)
- **Class 2**: Current assets
- **Class 3**: Liabilities (payables)
- **Class 4**: Revenues
- **Class 5**: Operating expenses
- **Class 6**: Financial expenses
- **Class 7**: Other expenses
- **Class 8**: Other income
- **Class 9**: Off-balance sheet

## VAT Structure

Croatian VAT rates (2012 structure):
- **25%** - Standard rate
- **10%** - Reduced rate (pre-2013 structure)
- **0%** - Zero rate / exempt

## Related Modules

| Module | Relationship |
|--------|-------------|
| [Modules/l10n_hr](modules/l10n_hr.md) | **Recommended** - EUR-based current module |
| [Modules/l10n_hr_edi](modules/l10n_hr_edi.md) | E-invoicing for current Croatian compliance |

## Migration Path

For companies still using Kuna:
1. Migrate to [Modules/l10n_hr](modules/l10n_hr.md) (EUR version)
2. Convert HRK balances to EUR using official conversion rate
3. Install [Modules/l10n_hr_edi](modules/l10n_hr_edi.md) for full compliance

## Technical Notes

- Version 13.0 - no longer actively maintained for new features
- Uses RRIF 2012 account codes (not the 2021 update)
- No EDI/e-invoicing integration
- No Euro currency support
- Tax structure may not reflect current rates

## See Also

- [Modules/l10n_hr](modules/l10n_hr.md) - Current Croatian accounting with EUR
- [Modules/l10n_hr_edi](modules/l10n_hr_edi.md) - Croatian e-invoicing
