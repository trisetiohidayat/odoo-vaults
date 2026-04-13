---
type: module
module: l10n_bo
tags: [odoo, odoo19, l10n, localization]
created: 2026-04-06
---

# Bolivia Localization (`l10n_bo`)

## Overview
- **Name:** Bolivia - Accounting
- **Country:** Bolivia (BO)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 2.0
- **Author:** Odoo / Cubic ERP
- **License:** LGPL-3
- **Dependencies:** `account`
- **Auto-installs:** `account`
- **Countries:** `bo`

## Description

Bolivian accounting chart and tax localization based on current regulations.

Provides the **Plan Contable Boliviano** (Bolivian Accounting Plan) aligned with Bolivian tax requirements, including the IT (Impuesto a las Transacciones) and ICE (Impuesto al Consumo Especifico) tax structures.

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/Account](Account.md) | Core accounting module |

## Key Models

### account.chart.template (Inherit)
Inherits `account.chart.template`:

- **Template `bo`:**
  - Code digits: 6
  - Anglo-Saxon accounting: enabled
  - Receivable account: `l10n_bo_1121`
  - Payable account: `l10n_bo_2121`
  - Stock valuation account: `l10n_bo_1131`
  - Default sale tax: IVA 13% (`l10n_bo_iva_13_sale`)
  - Default purchase tax: IVA 13% (`l10n_bo_iva_13_purchase`)
  - Bank prefix: `11130`, Cash prefix: `11110`, Transfer prefix: `11110`
  - Income account: `l10n_bo_4101`, Expense account: `l10n_bo_53008`
  - Currency exchange gain: `l10n_bo_4303`, Currency exchange loss: `l10n_bo_5602`
  - POS receivable account: `l10n_bo_11211`
  - Cash difference income: `l10n_bo_4301`, Cash difference expense: `l10n_bo_5601`
  - Early payment discount gain: `l10n_bo_4102`, Early payment discount loss: `l10n_bo_5104`
  - Inventory journal configured for stock valuation

### res.company (Inherit)
Extends `res.company` with Bolivian-specific defaults via chart template.

## Data Files
- `data/account_tax_report_data.xml` - Bolivian tax report configuration
- `demo/demo_company.xml` - Demo company data

## Bolivian Tax Structure

### IVA (Impuesto al Valor Agregado)
- **Standard rate:** 13% (called "Credito Fiscal" / "Debito Fiscal")
- IVA is applied to most sales and purchases of goods and services

### IT (Impuesto a las Transacciones)
- A transactions tax that applies in addition to or instead of IVA in certain cases
- Rate varies based on activity type

### ICE (Impuesto al Consumo Especifico)
- Excise tax on specific goods (beverages, tobacco, hydrocarbons, etc.)

## Account Code Structure
- 6-digit account codes following the Plan de Cuentas Boliviano
- First digit indicates account class (1=Activo, 2=Pasivo, 3=Patrimonio, 4=Ingresos, 5=Gastos/Costos, 6=Cuentas de结果ado)
- Dotted notation for sub-accounts

## Related Modules
- [Modules/l10n_bo](l10n_bo.md) - Core accounting (this module)
- [Modules/l10n_latam_base](l10n_latam_base.md) - Latin America base localization
- [Modules/l10n_latam_invoice_document](l10n_latam_invoice_document.md) - LATAM document types
