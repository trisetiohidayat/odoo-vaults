---
type: module
module: l10n_gt
tags: [odoo, odoo19, l10n, localization]
created: 2026-04-06
---

# Guatemala Localization (`l10n_gt`)

## Overview
- **Name:** Guatemala - Accounting
- **Country:** Guatemala (GT)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 3.0
- **Author:** Jose Rodrigo Fernandez Menegazzo
- **License:** LGPL-3
- **Dependencies:** `base`, `account`
- **Auto-installs:** `account`
- **Countries:** `gt`

## Description

Base module providing the accounting chart of accounts for Guatemala. Includes account templates, tax templates, and chart template pre-configured for Guatemalan accounting standards.

Also includes the **Quetzal (GTQ)** currency configuration.

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/Account](Modules/Account.md) | Core accounting module |
| `base` | Base module |

## Key Models

### account.chart.template (Inherit)
Inherits `account.chart.template`:

- **Template `gt`:**
  - Code digits: 9
  - Receivable account: `cta110201`
  - Payable account: `cta210101`
  - Account fiscal country: `base.gt`
  - Bank prefix: `1.0.01.0`, Cash prefix: `1.0.02.0`, Transfer prefix: `1.0.03.01`
  - POS receivable account: `cta110205`
  - Default sale tax: IVA por pagar (`impuestos_plantilla_iva_por_pagar`)
  - Default purchase tax: IVA por cobrar (`impuestos_plantilla_iva_por_cobrar`)
  - Income account: `cta410101`, Expense account: `cta510101`
  - Currency exchange gain: `cta410103`, Currency exchange loss: `cta710101`
  - Stock valuation account: `cta140101`
  - Stock variation account: `cta640101`
  - Stock expense account: `cta510101`

## Guatemalan Tax Structure

### IVA (Impuesto al Valor Agregado)
- **Standard rate:** 12%
- Applied to sale of goods and services within Guatemala
- Also known as "IVA" or "Impuesto de Ventas"

### ISC (Impuesto Sobre Circulacion de Vehiculos)
- Annual vehicle circulation tax for motor vehicles

### ISR (Impuesto Sobre la Renta)
- Income tax applicable to businesses and individuals
- Progressive rates for individuals, flat rate for companies

### IEMA (Impuesto Empresarial a Tasa Unica)
- A single-rate business tax that has been subject to regulatory changes

## Account Code Structure
- 9-digit account codes following Guatemalan conventions
- Uses dotted notation: `{class}.{group}.{account}.{subaccount}`
- Example: `1.0.01.0` = Asset, group 01, account 01, subaccount 0
- `cta` prefix used for template account codes

## Currency
- **Quetzal (GTQ)** - Official currency of Guatemala

## Related Modules
- [Modules/l10n_gt](Modules/l10n_gt.md) - Core accounting (this module)
- [Modules/account](Modules/account.md) - Core accounting
