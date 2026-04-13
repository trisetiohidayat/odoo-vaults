# Ireland - Accounting (`l10n_ie`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Ireland - Accounting |
| **Technical** | `l10n_ie` |
| **Category** | Accounting/Localizations |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `account`, `base_iban`, `base_vat`, `account_edi_ubl_cii` |

## Description
Irish accounting localization with chart of accounts, tax definitions, and special handling for Irish financial reports. Ensures that newly created liquidity bank accounts are tagged for Irish Balance Sheet and Profit & Loss reports.

## Technical Notes
- Country code: `ie` (Ireland)
- Localization type: chart template + tax data + model extensions
- Special tag: `l10n_ie_account_tag_cash_bank_hand` for cash/bank/hand reporting

## Models

### `account.journal` (Extended)
**Key methods:**
- `_prepare_liquidity_account_vals()` — OVERRIDES `account`. For Irish companies, adds the `l10n_ie_account_tag_cash_bank_hand` tag to newly created liquidity accounts (bank, cash, suspense) so they appear correctly in Irish BS/PL tag reports

### `account.chart.template` (Extended)
**Key methods:**
- `_post_load_data()` — EXTENDS `account`. After loading the Irish chart template (`ie`), automatically tags the company's suspense account and transfer account with `l10n_ie_account_tag_cash_bank_hand`

## Related
- [Modules/Account](Modules/account.md) — Core accounting
