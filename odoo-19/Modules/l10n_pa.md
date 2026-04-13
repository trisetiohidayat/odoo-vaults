---
type: module
module: l10n_pa
tags: [odoo, odoo19, l10n, localization]
created: 2026-04-06
---

# Panama Localization (`l10n_pa`)

## Overview
- **Name:** Panama - Accounting
- **Country:** Panama (PA)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 1.0
- **Author:** Cubic ERP
- **License:** LGPL-3
- **Dependencies:** `account`
- **Auto-installs:** `account`
- **Countries:** `pa`

## Description

Panamanian accounting chart and tax localization based on current regulations.

**Plan Contable Panameno** with accounting nomenclature and taxes aligned with Panamanian regulations. Developed in collaboration with AHMNET CORP (http://www.ahmnet.com).

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/Account](modules/account.md) | Core accounting module |

## Key Models

### account.chart.template (Inherit)
Inherits `account.chart.template`:

- **Template `pa`:**
  - Code digits: 7
  - Account fiscal country: `base.pa`
  - Receivable account: `121`
  - Payable account: `211`
  - Bank prefix: `111.`, Cash prefix: `113.`, Transfer prefix: `112.`
  - POS receivable account: `121_01`
  - Default sale tax: ITAX 19 (`ITAX_19`)
  - Default purchase tax: OTAX 19 (`OTAX_19`)
  - Income account: `411_01`, Expense account: `62_01`
  - Currency exchange gain: `gain81_01`, Currency exchange loss: `loss81_01`

## Panamanian Tax Structure

### ITBMS (Impuesto de Transferencia de Bienes Muebles y Servicios)
- **Standard rate:** 7%
- Panama's value-added tax applied to the transfer of movable goods and services
- Some provinces (Comarcas) may have different rates or exemptions

### IRPJ (Impuesto sobre la Renta de Personas Juridicas)
- Corporate income tax applicable to Panamanian companies
- Income sourced in Panama or from Panamanian activities

### Income Tax (Panama has territorial taxation)
- Panama follows a territorial tax system — only income sourced within Panama is taxed
- This is a key distinction from many other Latin American countries

### ISR (Instalacion de Servicios de Recognocimiento)
- Installation fee for certain services

### Additional Notes
- Panama uses the US Dollar (USD) as its official currency — no currency exchange issues for USD transactions
- Bookkeeping can be maintained in USD directly

## Account Code Structure
- 7-digit account codes following Panamanian conventions
- Dotted notation for account hierarchy
- Example: `121` = Receivable, `211` = Payable

## Related Modules
- [Modules/l10n_pa](modules/l10n_pa.md) - Core accounting (this module)
- [Modules/account](modules/account.md) - Core accounting
