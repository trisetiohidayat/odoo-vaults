---
type: module
module: l10n_do
tags: [odoo, odoo19, l10n, localization]
created: 2026-04-06
---

# Dominican Republic Localization (`l10n_do`)

## Overview
- **Name:** Dominican Republic - Accounting
- **Country:** Dominican Republic (DO)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 2.0
- **Author:** Gustavo Valverde - iterativo | Consultores de Odoo
- **License:** LGPL-3
- **Dependencies:** `account`, `base_iban`
- **Auto-installs:** `account`
- **Countries:** `do`

## Description

Catalogo de Cuentas e Impuestos para Republica Dominicana, compatible with internationalization using NIIF (NIIF/IFRS) and aligned with the regulations of the Direccion General de Impuestos Internos (DGII).

## Features

### Chart of Accounts
- Standard account catalog aligned with DGII and NIIF
- 8-digit account codes following Dominican Republic conventions

### Pre-configured Taxes
- **ITBIS** (Impuesto a la Transferencia de Bienes Muebles Servicios y a la Venta de Bienes Muebles) for sales and purchases
- **ITBIS Retentions** for withholding agents
- **ISR Retentions** (Impuesto Sobre la Renta) for income tax withholding
- **Tax groups** for:
  - Telecommunications
  - Construction Material Suppliers
  - Self-employed Service Providers
  - Other taxes

### Pre-configured Sequences for NCF (Numeracion de Comprobantes Fiscales)
- Facturas con Valor Fiscal (for Sales)
- Facturas para Consumidores Finales
- Notas de Debito y Credito
- Registro de Proveedores Informales
- Registro de Ingreso Unico
- Registro de Gastos Menores
- Gubernamentales

### Fiscal Positions
- Automation of taxes and withholdings
- Switch taxes to exemptions (e.g., Sales to the State)
- Switch taxes to withholdings (e.g., Foreign Service Purchases)

## Account Code Structure

| Level | Digits | Example | Description |
|-------|--------|---------|-------------|
| 1 digit | 1 | `1` | Category (1=Activo, 2=Pasivo, 3=Capital, 4=Ingresos, 5=Gastos, 6=Liquidadora) |
| 2 digits | 11- | `11` | Grouping category (11=Activo Corriente, 21=Pasivo Corriente) |
| 4 digits | 1101- | `1101` | Main accounts / first-order accounts |
| 6 digits | 110101- | `110101` | Sub-accounts / second-order accounts |
| 8 digits | 11010101 | `11010101` | Third-order accounts (displayed in Odoo) |

Example breakdown:
- `1101` = Efectivo y Equivalentes de Efectivo
- `110101` = Caja
- `11010101` = Caja General

## Dominican Tax Structure

### ITBIS (Tax on Transfers of Goods and Services)
- **Standard rate:** 18%
- Applied to the transfer of movable goods and rendering of services
- May be reduced to 0% for exempt items or 13% in some special regimes

### ISR (Income Tax)
- Corporate income tax: 27% for companies
- Progressive rates for individuals

### Withholding Agents
- Businesses registered as withholding agents must withhold ITBIS and/or ISR on payments to suppliers

## Key Models

### account.chart.template (Inherit)
Inherits `account.chart.template` - provides template data and company configuration for Dominican Republic.

## Data Files
- `data/account_tax_report_data.xml` - Dominican tax report configuration
- `demo/demo_company.xml` - Demo company data

## Related Modules
- [Modules/l10n_do](odoo-18/Modules/l10n_do.md) - Core accounting (this module)
- [Modules/account](odoo-18/Modules/account.md) - Core accounting
- [Modules/l10n_latam_base](odoo-18/Modules/l10n_latam_base.md) - Latin America base localization
- [Modules/l10n_latam_invoice_document](odoo-18/Modules/l10n_latam_invoice_document.md) - LATAM document types
