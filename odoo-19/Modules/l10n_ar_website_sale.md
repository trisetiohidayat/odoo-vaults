# Argentinean eCommerce (`l10n_ar_website_sale`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Argentinean eCommerce |
| **Technical** | `l10n_ar_website_sale` |
| **Category** | Accounting/Localizations/eCommerce |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `website_sale`, `l10n_ar` |

## Description
Bridge module between Website Sale and Argentinean accounting localization. Forces tax-included pricing display on the eCommerce portal and provides a configurable toggle to show prices with and without national taxes (IIBB and other provincial taxes) separately.

## Dependencies
| Module | Purpose |
|--------|---------|
| `website_sale` | Base eCommerce module |
| `l10n_ar` | Core Argentinean accounting |

## Technical Notes
- Country code: `ar` (Argentina)
- Localization type: eCommerce integration
- Key concern: Argentine tax display on public website

## Models

### `website` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `l10n_ar_website_sale_show_both_prices` | Boolean | Toggle to display prices without national taxes separately on the website. Compute-backed; auto-enabled when `company_id.account_fiscal_country_id.code == 'AR'` |

**Compute methods:**
- `_compute_l10n_ar_website_sale_show_both_prices()` — Sets to True for Argentine companies
- `_compute_show_line_subtotals_tax_selection()` — EXTENDS `website_sale`. For Argentine companies, forces `show_line_subtotals_tax_selection = 'tax_included'` — all prices displayed on the website include tax

### `product.template` (Extended)
Adds Argentine-specific product fiscal data relevant to website display (e.g., tax category).

### `res.config.settings` (Extended)
Allows configuration of the "show both prices" toggle from company settings.

## Pricing Display Logic
When enabled, the website shows two prices:
1. **With all taxes** — standard price including VAT
2. **Without national taxes** — excludes IIBB (gross income tax) and other provincial taxes

## Related
- [Modules/l10n_ar](modules/l10n_ar.md) — Core Argentinean accounting
- [Modules/website_sale](modules/website_sale.md) — Base eCommerce module
- [Modules/l10n_ar_pos](modules/l10n_ar_pos.md) — Argentine POS
- [Modules/l10n_ar_withholding](modules/l10n_ar_withholding.md) — Argentine withholding tax
