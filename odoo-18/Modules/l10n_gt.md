---
Module: l10n_gt
Version: 18.0
Type: l10n/guatemala
Tags: #odoo18 #l10n #accounting #guatemala
---

# l10n_gt — Guatemala Accounting

## Overview
Guatemala accounting localization providing the chart of accounts and tax templates for Guatemala. Authored by Jose Rodrigo Fernandez Menegazzo. Includes GTQ (Quetzal) currency.

## Country/Region
Guatemala (country code: GT)

## Dependencies
- base
- account

## Key Models
No custom Python model classes. Template loader in `models/template_gt.py` loads the Guatemalan chart of accounts.

## Chart of Accounts
Guatemalan chart of accounts via `template_gt.py`. K Structure following Guatemala's accounting standards.

## Tax Structure
- **IVA**: Impuesto al Valor Agregado, 12%
- Basic tax templates for Guatemala

## Data Files
- `demo/demo_company.xml`: Demo company with GTQ currency

## Installation
Install with accounting. No demo data by default.

## Historical Notes
Version 3.0 in Odoo 18. Guatemala's SAT (Superintendencia de Administracion Tributaria) governs tax compliance. IVA is the main tax. GTQ currency configured.
