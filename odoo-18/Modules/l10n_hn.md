---
Module: l10n_hn
Version: 18.0
Type: l10n/honduras
Tags: #odoo18 #l10n #accounting #honduras
---

# l10n_hn — Honduras Accounting

## Overview
Honduran accounting localization providing the chart of accounts and tax templates. Includes the Lempira (HNL) currency. Authored by Salvatore Josue Trimarchi Pinto.

## Country/Region
Honduras (country code: HN)

## Dependencies
- base
- account

## Key Models
No custom Python model classes. Template loader in `models/template_hn.py` loads the Honduran chart of accounts.

## Chart of Accounts
Honduran chart of accounts via `template_hn.py`.

## Tax Structure
Basic Honduras tax templates including Honduras sales tax.

## Data Files
- `demo/demo_company.xml`: Demo company with HNL currency

## Installation
Install with accounting. No demo data by default.

## Historical Notes
Version 0.2 in Odoo 18. Honduras is one of the smaller LATAM localizations in Odoo. The Honduran quetzal uses a floating exchange rate. The country is in the process of modernizing its tax administration.
