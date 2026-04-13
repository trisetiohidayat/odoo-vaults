# Brazil - Website Sale (`l10n_br_website_sale`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Brazil - Website Sale |
| **Technical** | `l10n_br_website_sale` |
| **Category** | Accounting/Localizations/eCommerce |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `l10n_br`, `website_sale` |

## Description
Brazilian eCommerce pricing configuration. Auto-enables tax-included pricing display (`show_line_subtotals_tax_selection = 'tax_included'`) for any new website created with a Brazilian company, matching Brazilian consumer expectations.

## Technical Notes
- Country code: `br` (Brazil)

## Models

### `website` (Extended)
**`create()`** — OVERRIDES `website`. For new websites associated with a Brazilian company, automatically sets `show_line_subtotals_tax_selection` to `'tax_included'` so all prices on the eCommerce site include Brazilian taxes (ICMS, PIS, COFINS, etc.)

## Related
- [Modules/l10n_br](modules/l10n_br.md) — Core Brazilian accounting
- [Modules/website_sale](modules/website_sale.md) — Base eCommerce module
