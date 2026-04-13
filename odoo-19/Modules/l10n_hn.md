---
type: module
module: l10n_hn
tags: [odoo, odoo19, l10n, localization]
created: 2026-04-06
---

# Honduras Localization (`l10n_hn`)

## Overview
- **Name:** Honduras - Accounting
- **Country:** Honduras (HN)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 0.2
- **Author:** Salvatore Josue Trimarchi Pinto
- **License:** LGPL-3
- **Dependencies:** `base`, `account`
- **Auto-installs:** `account`
- **Countries:** `hn`

## Description

Base module providing the accounting chart of accounts for Honduras. Adds the accounting nomenclature for Honduras, including taxes and the **Lempira (HNL)** currency.

Designed to meet minimum requirements for operating a business in Honduras in compliance with Honduran tax regulations.

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/Account](odoo-18/Modules/account.md) | Core accounting module |
| `base` | Base module |

## Key Models

### account.chart.template (Inherit)
Inherits `account.chart.template`:

- **Template `hn`:**
  - Code digits: 9
  - Account fiscal country: `base.hn`
  - Receivable account: `cta110201`
  - Payable account: `cta210101`
  - Bank prefix: `1.1.01.`, Cash prefix: `1.1.01.`, Transfer prefix: `1.1.01.00`
  - POS receivable account: `cta110205`
  - Default sale tax: ISV por pagar (`impuestos_plantilla_isv_por_pagar`)
  - Default purchase tax: ISV por cobrar (`impuestos_plantilla_isv_por_cobrar`)
  - Income account: `cta410101`, Expense account: `cta510101`
  - Currency exchange gain: `cta410103`, Currency exchange loss: `cta710101`
  - Early payment discount gain: `cta420102`, Early payment discount loss: `cta620202`
  - Stock valuation account: `cta130601`
  - Stock variation account: `cta620201`
  - Stock expense account: `cta510101`

## Honduran Tax Structure

### ISV (Impuesto Sobre Ventas)
- **Standard rate:** 15%
- Honduras' value-added tax applied to the sale of goods and services
- Also known as "Sales Tax" in some contexts

### ISIC (Impuesto Sobre Industrias y Comercio)
- Commerce and industry tax applicable to businesses operating in Honduras
- Rates vary by activity type and municipality

### ISR (Impuesto Sobre la Renta)
- Income tax for Honduras
- Companies typically subject to corporate income tax rates

### Advance Payments (Anticipos)
- Monthly advance tax payments based on estimated income

## Account Code Structure
- 9-digit account codes following Honduran conventions
- Dotted notation: `{class}.{group}.{account}.{subaccount}`
- Example: `1.1.01.` = Asset class, group 01
- `cta` prefix for template accounts

## Currency
- **Lempira (HNL)** - Official currency of Honduras, named after the indigenous leader Lempira

## Related Modules
- [Modules/l10n_hn](odoo-18/Modules/l10n_hn.md) - Core accounting (this module)
- [Modules/account](odoo-18/Modules/account.md) - Core accounting
