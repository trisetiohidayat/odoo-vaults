---
Module: l10n_do
Version: 18.0
Type: l10n/dominican-republic
Tags: #odoo18 #l10n #accounting #dominican-republic
---

# l10n_do — Dominican Republic Accounting

## Overview
Dominican Republic localization providing the complete chart of accounts (aligned to DGII/NIIF), taxes, and NCF (Numero de Comprobante Fiscal) sequences. Authored by Gustavo Valverde / Consultores de Odoo. Aligns with DGII (Direccion General de Impuestos Internos) regulations and NIIF standards.

## Country/Region
Dominican Republic (country code: DO)

## Dependencies
- account
- base_iban

## Key Models
No custom Python model classes. Template loader in `models/template_do.py` loads the Dominican chart of accounts and tax templates.

## Chart of Accounts
6-digit account coding structure:
- **1xxx**: Assets (1-Current, 2-Fixed)
- **2xxx**: Liabilities (Current/Long-term)
- **3xxx**: Equity (Capital Contable)
- **4xxx**: Revenue and Gains
- **5xxx**: Costs, Expenses, Losses
- **6xxx**: Liquidation accounts (Cuentas Liquidadoras de Resultados)

8-digit accounts for sub-accounts; 6-digit for first-level sub-accounts.

## Tax Structure
- **ITBIS** (Impuesto a la Transferencia de Bienes Muebles y a la Servicios): 18% VAT equivalent
- **ITBIS Retentions**: Telecom, Construction Materials, Service Providers, etc.
- **ISR Retentions**: Income tax withholding
- Tax groups preconfigured for:
  - Telecommunications providers
  - Construction material suppliers
  - Service providers (physical persons)
  - Government entities

## NCF Sequences
Preconfigured sequences for all NCF types:
- Facturas con Valor Fiscal (sales with fiscal value)
- Facturas para Consumidores Finales (end consumer invoices)
- Notas de Debito y Credito
- Registro de Proveedores Informales
- Registro de Ingreso Unico
- Registro de Gastos Menores
- Gubernamentales

## Fiscal Positions
- Sales to the State: exempt from ITBIS
- Services from abroad: ITBIS retention
- General: tax mappings for all scenarios

## Data Files
- `data/account_tax_report_data.xml`: Tax report configuration
- `demo/demo_company.xml`: Demo company

## Installation
Install with accounting. NCF sequences require third-party module or development for DGII reporting integration.

## Historical Notes
Version 2.0 in Odoo 18. The module provides all NCF sequences and fiscal positions required by DGII, but actual electronic submission requires additional community modules or custom development. Important note in description: NCF sequences cannot be used without third-party module or additional development.
