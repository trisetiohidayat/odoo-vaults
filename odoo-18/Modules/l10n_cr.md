---
Module: l10n_cr
Version: 18.0
Type: l10n/costa-rica
Tags: #odoo18 #l10n #accounting #costa-rica
---

# l10n_cr — Costa Rica Accounting

## Overview
Costa Rica accounting localization providing the Costa Rican chart of accounts and tax templates. Maintained by ClearCorp S.A. All content is available in English with Spanish translation.

## Country/Region
Costa Rica (country code: CR)

## Dependencies
- account

## Key Models
No custom Python model classes. Template loader in `models/template_cr.py` loads chart of accounts.

## Chart of Accounts
Costa Rican chart of accounts via `template_cr.py`. Includes:
- `account.account.template`: Chart of accounts
- `account.tax.template`: Tax templates
- `account.chart.template`: Root chart template

## Tax Structure
Basic Costa Rican tax templates: IVA (Impuesto al Valor Agregado) at 13%.

## Data Files
- `data/l10n_cr_res_partner_title.xml`: Costa Rican partner titles
- `demo/demo_company.xml`: Demo company

## Installation
Install with accounting. No demo data by default.

## Historical Notes
Version follows Odoo standard. ClearCorp maintains the module. Costa Rica uses USD as official currency (alongside CRC). Tax system is relatively simple with IVA as the main consumption tax.
