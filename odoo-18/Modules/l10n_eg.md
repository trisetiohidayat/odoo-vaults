---
Module: l10n_eg
Version: 18.0
Type: l10n/egypt
Tags: #odoo18 #l10n #accounting #egypt
---

# l10n_eg

## Overview
Egypt accounting localization — provides the base chart of accounts, VAT tax structure, withholding tax report, scheduled tax report, other taxes report, and fiscal position mappings for Egyptian companies. This is the prerequisite module for `l10n_eg_edi_eta` (e-Invoicing).

## Country
Egypt (Arab Republic of Egypt) — country code `eg`

## Dependencies
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template` via `_inherit`. Provides `_get_eg_template_data()` and `_get_eg_res_company()` using template prefix `'eg'`.

### `AccountTax` (`account.tax`)
Inherits `account.tax`. Adds `l10n_eg_eta_code` — a `Selection` field mapping Egyptian tax types to ETA (Egyptian Tax Authority) codes used in e-invoicing (see `l10n_eg_edi_eta`).

ETA codes cover:
- T1: Exempt / non-taxable goods and services (V001–V010)
- T2: Table tax percentage
- T3: Table tax fixed amount
- T4: Withholding taxes — contracting, supplies, purchases, services, commissions, professional fees, royalties, customs, etc. (W001–W016)
- T5/T6: Stamping tax percentage/fixed
- T7: Entertainment tax rate/amount
- T8: Resource development fee rate/amount
- T9: Service charges rate/amount
- T10: Municipality fees rate/amount
- T11: Medical insurance fee rate/amount
- T12: Other fees rate/amount
- T13–T20: Additional rate/amount variants

## Data Files
- `data/account_tax_report_data.xml` — account report definitions (VAT return, withholding tax report, scheduled tax report, other taxes report)
- `data/template/` — chart of accounts template data
- `views/account_tax.xml` — tax view extensions (adds ETA code field to tax form)
- `demo/demo_company.xml` — demo company data
- `demo/demo_partner.xml` — demo partner data

## Chart of Accounts
Egyptian chart of accounts with `eg` prefix, structured per Egyptian accounting standards (Egyptian Accounting Standards — EAS, aligned with IFRS where applicable). No public-sector chart included.

## Tax Structure
VAT at 14% standard rate (also 0% zero-rated and exempt). Withholding taxes (T4 series) for specific professional services, contracts, and commissions. Additional municipal and environmental levies may apply. Tax codes map to ETA e-invoicing schema.

## Fiscal Positions
Defined in `data/account_tax_report_data.xml`.

## EDI/Fiscal Reporting
No EDI format defined in this module. EDI is provided by [[Modules/l10n_eg_edi_eta]] which depends on this module.

## Installation
Install as a standard localization module. `auto_install: ['account']` — automatically installed when account is installed if Egypt is selected.

## Historical Notes
- Version 1.0 in Odoo 18
- The `l10n_eg_eta_code` Selection field was added in Odoo 17 / early 18 to support e-Invoicing integration
- Egypt's VAT rate is 14% (not 15% like many GCC countries)
