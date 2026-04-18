# Portugal - Accounting (`l10n_pt`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Portugal - Accounting |
| **Technical** | `l10n_pt` |
| **Category** | Accounting/Localizations |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `base`, `account`, `base_vat`, `account_edi_ubl_cii` |

## Description
Portuguese accounting localization with chart of accounts, tax definitions, and tax rounding configuration. Forces tax-included rounding mode (`mode='included'`) for Portuguese companies to comply with local tax calculation regulations.

## Technical Notes
- Country code: `pt` (Portugal)
- Localization type: chart template + tax data + model extensions
- Tax rounding: Forced `included` mode (tax-inclusive) for all tax calculations

## Models

### `account.tax` (Extended)
**`_round_tax_details_tax_amounts()`** — EXTENDS `account`. For Portuguese companies (`account_fiscal_country_id.code == 'PT'`), forces `mode='included'` before calling the parent method

**`_round_tax_details_base_lines()`** — EXTENDS `account`. For Portuguese companies, forces `mode='included'` before calling the parent method

These overrides ensure Portuguese tax reports and invoice line calculations use tax-inclusive rounding as required by local tax rules (PRT).

## Related
- [Modules/Account](Modules/Account.md) — Core accounting
