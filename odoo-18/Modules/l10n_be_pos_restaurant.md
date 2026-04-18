---
Module: l10n_be_pos_restaurant
Version: 18.0
Type: l10n/be
Tags: #odoo18 #l10n #pos #restaurant
---

# l10n_be_pos_restaurant

## Overview
Belgian POS restaurant localization. Extends `pos_restaurant` and `l10n_be` to add Belgian-specific POS restaurant configuration: automatic takeaway fiscal position (21% → 6% VAT reduction), alcohol tax on luxury goods for cocktail categories, and Belgian restaurant floor configuration. Auto-installed for Belgian companies using the restaurant POS onboarding.

## Country
[Belgium](Modules/account.md) 🇧🇪

## Dependencies
- pos_restaurant
- [l10n_be](Modules/account.md)

## Key Models

### PosConfig
`models/pos_config.py` — extends `pos.config`
- `_create_takeaway_fiscal_position()` — creates a Belgian takeaway fiscal position mapping: VAT 21% → 6%, VAT 12% → 6% (Belgium's reduced rate for takeaway). Writes `takeaway=True` and `takeaway_fp_id` on config.
- `load_onboarding_bar_scenario()` — override: for companies with Belgian chart, sets `tax_alcohol_luxury` on all products in `pos_category_cocktails` (Belgium's luxury alcohol classification for cocktail sales)
- `load_onboarding_restaurant_scenario()` — override: for companies with Belgian chart, calls `_create_takeaway_fiscal_position()` on the main restaurant config

### AccountChartTemplate
`models/template_be.py` — extends `account.chart.template`
- `_get_be_pos_restaurant_account_tax()` — creates Belgian restaurant-specific taxes: luxury alcohol tax (other goods category), via `_parse_csv` loading from module's own CSV (not l10n_be's). Filters out taxes that already exist to avoid duplicates.

## Data Files
- `data/template/` — Belgian restaurant-specific tax definitions (luxury goods alcohol tax)

## Chart of Accounts
Inherits from [l10n_be](Modules/account.md) (Belgian full chart).

## Tax Structure
Belgian restaurant taxes + takeaway fiscal position (21% → 6%):
- Standard: 21% VAT (sale)
- Takeaway: 6% VAT (reduced rate for food to go)
- Luxury alcohol: separate classification via `tax_alcohol_luxury`

## Fiscal Positions
**Takeaway fiscal position** (created on POS config init):
- 21% → 6% on food/beverage products
- 12% → 6% on reduced-rate items
Belgium distinguishes between eat-in and takeaway for VAT rate purposes.

## EDI/Fiscal Reporting
Not applicable (POS module).

## Installation
`auto_install: True` — auto-installed for Belgian POS restaurant use cases.

Post-init hook: `post_init_hook` — for companies with Belgian chart: calls `_get_be_pos_restaurant_account_tax()` to ensure luxury alcohol tax is loaded.

## Historical Notes

**Odoo 17 → 18 changes:**
- Version 1.0; Belgian restaurant POS localization is a newer feature
- Takeaway fiscal position automation is helpful — previously required manual fiscal position creation
- Alcohol tax product classification addresses Belgium's specific food/beverage tax rules

**Performance Notes:**
- Fiscal position creation is idempotent (checks for existing before creating)
- Tax CSV loading only creates missing taxes; existing taxes are filtered out