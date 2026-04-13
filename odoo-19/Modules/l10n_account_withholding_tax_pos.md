# Withholding Tax on Payment - PoS (`l10n_account_withholding_tax_pos`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Withholding Tax on Payment - PoS |
| **Technical** | `l10n_account_withholding_tax_pos` |
| **Category** | Sales/Point Of Sale |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `l10n_account_withholding_tax`, `point_of_sale` |

## Description
Enables withholding tax on payment for POS transactions. Loads the `is_withholding_tax_on_payment` field into POS session data so that POS tax computation respects withholding tax settings configured on account tax records.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_account_withholding_tax` | Core withholding tax framework |
| `point_of_sale` | Base POS module |

## Models

### `account.tax` (Extended)
**`_load_pos_data_fields()`** — EXTENDS `account`. Adds `is_withholding_tax_on_payment` to the POS session data fields, enabling the POS frontend to determine which taxes require withholding during payment processing.

## Related
- [Modules/l10n_account_withholding_tax](Modules/l10n_account_withholding_tax.md) — Core withholding tax framework
- [Modules/point_of_sale](Modules/point_of_sale.md) — Base POS module
