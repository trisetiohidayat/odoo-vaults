---
type: module
module: l10n_ec_stock
tags: [odoo, odoo19, l10n, localization]
created: 2026-04-06
---

# Ecuador Stock Localization (`l10n_ec_stock`)

## Overview
- **Name:** Ecuador - Stock
- **Country:** Ecuador (EC)
- **Category:** Accounting/Localizations
- **Version:** 1.0
- **Author:** Odoo S.A.
- **License:** LGPL-3
- **Dependencies:** `l10n_ec`, `stock`
- **Auto-installs:** Yes (auto_installs on its dependencies)
- **Countries:** `ec`

## Description

Ecuador Stock module extends the base Ecuadorian accounting localization (`l10n_ec`) with stock/inventory-specific configurations. Integrates Ecuadorian chart of accounts with [Modules/Stock](Modules/Stock.md) module inventory valuation.

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/l10n_ec](Modules/l10n_ec.md) | Ecuadorian accounting base |
| [Modules/Stock](Modules/Stock.md) | Inventory management module |

## Key Components

### account.chart.template (Inherit)
Extends `account.chart.template` for Ecuadorian stock accounting:

- **Template `ec`:**
  - Code digits: 4
  - Receivable account: `ec1102050101`
  - Payable account: `ec210301`
  - Stock valuation account: `ec110306`
  - Journal expense category: `ec52022816`
  - Loss stock valuation: `ec510112`
  - Production stock valuation: `ec110302`
  - Bank prefix: `11010201`, Cash prefix: `1101010`, Transfer prefix: `1101030`
  - POS receivable account: `ec1102050103`
  - Default sale tax: VAT 15% (`tax_vat_15_411_goods`)
  - Default purchase tax: VAT 15% (`tax_vat_15_510_sup_01`)
  - Income account: `ec410101`, Expense account: `ec110307`
  - Currency exchange gain: `ec430501`, Currency exchange loss: `ec520304`
  - Stock journal: `inventory_valuation`
  - Cash difference income: `ec_income_cash_difference`, Cash difference expense: `ec_expense_cash_difference`
  - Early payment discount gain/loss accounts
  - Tax calculation rounding: `round_per_line`

### Stock Valuation Accounts
| Account Code | Purpose |
|-------------|---------|
| `ec110306` | Stock valuation main account |
| `ec510106` | Stock expense account |
| `ec110310` | Stock variation account |
| `ec110302` | Production stock valuation |

### Sale Journal Configuration
Automatically configures the sale journal with SRI emission details:

- Journal name: `001-001 Facturas de cliente`
- SRI Entity: `001`
- SRI Emission point: `001`
- Emission address: Company partner address

## Ecuadorian Stock/Inventory Notes

- Ecuador uses FIFO (First In, First Out) method commonly for inventory valuation
- Tax treatment of inventory movements follows SRI guidelines
- Stock picking operations must be properly documented for SRI compliance

## Post-Init Hook
`_post_load_data()` - After loading template data, sets the default account on purchase journal based on expense category template data.

## Related Modules
- [Modules/l10n_ec](Modules/l10n_ec.md) - Core Ecuadorian accounting
- [Modules/l10n_ec_sale](Modules/l10n_ec_sale.md) - Ecuador sale extensions
- [Modules/l10n_ec_stock](Modules/l10n_ec_stock.md) - Ecuador stock (this module)
- [Modules/Stock](Modules/Stock.md) - Inventory management
- [Modules/Account](Modules/Account.md) - Core accounting
