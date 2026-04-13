---
type: module
module: l10n_cr
tags: [odoo, odoo19, l10n, localization]
created: 2026-04-06
---

# Costa Rica Localization (`l10n_cr`)

## Overview
- **Name:** Costa Rica - Accounting
- **Country:** Costa Rica (CR)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 1.0
- **Author:** ClearCorp S.A.
- **License:** LGPL-3
- **Dependencies:** `account`
- **Auto-installs:** `account`
- **Countries:** `cr`
- **URL:** https://github.com/CLEARCORP/odoo-costa-rica

## Description

Chart of accounts for Costa Rica. Includes account templates, tax templates, and chart template pre-configured for Costa Rican accounting standards.

All data is in English with Spanish translations. Contributions welcome via Launchpad Translations.

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/Account](Account.md) | Core accounting module |

## Key Models

### account.chart.template (Inherit)
Inherits `account.chart.template`:

- **Template `cr`:**
  - Receivable account: `account_account_template_0_112001`
  - Payable account: `account_account_template_0_211001`
  - Bank prefix: `0.1112`, Cash prefix: `0.1111`, Transfer prefix: `0.1114`
  - POS receivable account: `account_account_template_0_112011`
  - Default sale tax: IVA (`account_tax_template_IV_0`)
  - Default purchase tax: IVA (`account_tax_template_IV_1`)
  - Income account: `account_account_template_0_410001`
  - Expense account: `account_account_template_0_511301`
  - Currency exchange gain: `account_account_template_0_450001`
  - Currency exchange loss: `account_account_template_0_530004`
  - Stock valuation account: `account_account_template_0_113101`
  - Stock variation account: `account_account_template_0_520001`
  - Stock expense account: `account_account_template_0_511302`

## Costa Rican Tax Structure

### IVA (Impuesto al Valor Agregado)
- **Standard rate:** 13%
- Applied to the sale of goods and services in Costa Rica
- Also known as "Impuesto de Ventas" in older legislation

### Selective Consumption Tax (Impuesto Selectivo de Consumo)
- Applied to specific goods such as alcoholic beverages, tobacco products, and luxury items

## Account Code Structure
- Follows Costa Rican accounting plan conventions
- Code structure organized by account type (1xxx=Assets, 2xxx=Liabilities, 4xxx=Income, 5xxx=Expenses)
- 13% IVA tax template pre-configured for sales and purchases

## Related Modules
- [Modules/l10n_cr](l10n_cr.md) - Core accounting (this module)
- [Modules/l10n_latam_base](l10n_latam_base.md) - Latin America base localization
- [Modules/account](Account.md) - Core accounting
