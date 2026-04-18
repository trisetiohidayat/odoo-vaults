---
type: module
module: l10n_ve
tags: [odoo, odoo19, l10n, localization]
created: 2026-04-06
---

# Venezuela Localization (`l10n_ve`)

## Overview
- **Name:** Venezuela - Accounting
- **Country:** Venezuela (VE)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 1.0
- **Author:** Odoo S.A., Vauxoo
- **License:** LGPL-3
- **Dependencies:** `account`
- **Auto-installs:** `account`
- **Countries:** `ve`

## Description

Chart of Account for Venezuela.

Venezuela does not have a legally mandated chart of accounts by law. The default proposed in Odoo complies with accepted best practices in Venezuela and is based on a mixture of the most common software used in the Venezuelan market.

This module provides the minimum requirements to start a company in Venezuela with Odoo. It has been tested as the base for over 1,000 companies.

## Limitations

- This module does NOT pretend to be the total localization for Venezuela
- Electronic invoicing (SENIAT/Comprobantes Fiscales) requires third-party modules or additional development
- The module provides basic tax data and chart of accounts to start quickly

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/Account](Modules/Account.md) | Core accounting module |

## Key Models

### account.chart.template (Inherit)
Inherits `account.chart.template`:

- **Template `ve`:**
  - Code digits: 7
  - Account fiscal country: `base.ve`
  - Receivable account: `account_activa_account_1122001`
  - Payable account: `account_activa_account_2122001`
  - Bank prefix: `1113`, Cash prefix: `1111`, Transfer prefix: `1129003`
  - POS receivable account: `account_activa_account_1122003`
  - Default sale tax: `tax3sale`
  - Default purchase tax: `tax3purchase`
  - Income account: `account_activa_account_5111001`
  - Expense account: `account_activa_account_7151001`
  - Currency exchange gain: `account_activa_account_9212003`
  - Currency exchange loss: `account_activa_account_9113006`
  - Stock valuation account: `account_activa_account_1131002`
  - Stock variation account: `account_activa_account_6121000`

## Venezuelan Tax Structure

### IVA (Impuesto al Valor Agregado)
- **Standard rate:** 16%
- Applied to sale of goods and services in Venezuela
- Subject to frequent changes due to economic conditions

### ISLR (Impuesto Sobre la Renta)
- Income tax applicable to companies and individuals
- Progressive rates for individuals, corporate rate varies

### Additional Notes
- Venezuela has a complex currency situation with multiple exchange rate systems (DICOM, DIPRO)
- Consider installing `account_anglo_saxon` for inventory valuation as practiced in Venezuela

## Account Code Structure
- 7-digit account codes following Venezuelan conventions
- Uses `account_activa_account_` prefix for template accounts
- Based on commonly used Venezuelan accounting software patterns

## Related Modules
- [Modules/l10n_ve](Modules/l10n_ve.md) - Core accounting (this module)
- [Modules/account](Modules/Account.md) - Core accounting
- [Modules/account_accountant](Modules/account_accountant.md) - Recommended for stock valuation in Venezuela
