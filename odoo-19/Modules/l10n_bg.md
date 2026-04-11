---
type: module
module: l10n_bg
tags: [odoo, odoo19, l10n, localization, bulgaria, accounting]
created: 2026-04-06
---

# Bulgaria Accounting Localization (`l10n_bg`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Bulgaria - Accounting |
| **Technical** | `l10n_bg` |
| **Category** | Accounting/Localizations/Account Charts |
| **Country** | Bulgaria (BG) |
| **Currency** | BGN (Bulgarian Lev) |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |

## Description

Bulgarian accounting chart and tax localization module. Provides the chart of accounts, tax structure, and fiscal positions required for Bulgarian compliance.

## Dependencies

| Module | Purpose |
|--------|---------|
| [[Modules/Account]] | Core accounting framework |
| [[Modules/base_vat]] | Bulgarian BULSTAT/EGN validation |

## Auto-Install

Auto-installs with `account` when the company's country is set to Bulgaria.

## Key Components

### Chart of Accounts

Bulgarian accounting follows the National Chart of Accounts:
- Full account hierarchy per Bulgarian regulations
- Class 1-8 structure
- Mandatory VAT-synchronized accounts

### Tax Structure

Bulgarian VAT (ДДС - Данък добавена стойност) rates:
- **20%** - Standard rate
- **9%** - Reduced rate (accommodation, restaurant services)
- **0%** - Zero rate / exempt

### Fiscal Positions

Pre-configured for:
- Domestic B2B with VAT
- EU intra-community (reverse charge)
- Export outside EU
- B2C

## Data File

`data/tax_report.xml` - Bulgarian tax reporting structure for VAT returns.

## Bulgarian-Specific Fields

### BULSTAT / EGN

Bulgarian business registration number:
- **BULSTAT**: 9-digit unified identification code
- **EGN**: Personal identity number for individuals
- Validated via [[Modules/base_vat]]

## Related Modules

| Module | Relationship |
|--------|-------------|
| [[Modules/l10n_bg_ledger]] | Bulgarian ledger / extended reporting |

## Configuration

1. Install the module via Apps
2. Set company country to Bulgaria
3. Configure Bulgarian VAT (DDS) number in company settings
4. Set up Bulgarian BULSTAT in company details

## Technical Notes

- Bulgaria uses BGN (Lev) with 2 decimal places
- BULSTAT is the primary business identifier
- EU member since 2007 - follows EU VAT rules
- No dedicated EDI module in Odoo 19 standard distribution
- See [[Modules/l10n_bg_ledger]] for extended Bulgarian ledger features

## See Also

- [[Modules/l10n_bg_ledger]] - Bulgarian ledger reporting
- [[Modules/Account]] - Core accounting
