---
Module: l10n_co
Version: 18.0
Type: l10n/colombia
Tags: #odoo18 #l10n #accounting #colombia
---

# l10n_co — Colombia Accounting

## Overview
Colombian accounting localization providing the chart of accounts, taxes, and DIAN (Direccion de Impuestos y Aduanas Nacionales) document types. Authored by David Arnold (XOE Solutions). Requires [Modules/l10n_latam_base](Modules/l10n_latam_base.md) and `account_debit_note`.

## Country/Region
Colombia (country code: CO)

## Dependencies
- account_debit_note
- l10n_latam_base
- account

## Key Models

### `l10n_latam.identification.type` (Extended)
Inherits: `l10n_latam.identification.type`
Identification types specific to Colombia defined in `data/l10n_latam_identification_type_data.xml` (CSV): NIT (tax ID), CC (Cedula Ciudadania), CE (Cedula Extranjeria), PAS (Pasaporte), NIP, RUT, NIT-O.

### `res.partner` (Extended via Template)
Inherits: `res.partner`
Chart template loader in `models/template_co.py` loads Colombian chart of accounts.

## Chart of Accounts
Colombian chart of accounts based on NIIF (Normas de Informacion Financiera) and NIF (Normas Colombianas). 4-digit account structure. Colombian accounting follows PUC (Plan Unico de Cuentas) for some sectors.

## Tax Structure
- IVA 19% (general rate)
- IVA 5% (reduced rate)
- IVA 0% (exempt)
- ICA (Impuesto de Industria y Comercio) withholding
- Retefuente (Income tax withholding on payments)
- ReteIVA (VAT withholding)
- Taxes defined via `account_chart_template_data.xml`

## Fiscal Positions
Fiscal positions for Colombia: responsible (responsible VAT payer), independent, non-VAT responsible, foreign.

## Data Files
- `data/account_chart_template_data.xml`: Colombian chart template and taxes
- `data/l10n_latam_identification_type_data.xml`: NIT, CC, CE identification types
- `demo/demo_company.xml`: Demo "CO Company"

## Installation
Install with accounting. Chart template is loaded via data.

## Historical Notes
Odoo 18 v1.0. Colombia's DIAN has been progressively mandating electronic invoicing (DIAN electronic invoice). The module provides the base for electronic invoicing integration; community modules extend it for e-invoicing via the DIAN web services.
