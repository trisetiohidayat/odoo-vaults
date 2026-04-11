---
Module: l10n_ve
Version: 18.0
Type: l10n/venezuela
Tags: #odoo18 #l10n #accounting #venezuela
---

# l10n_ven — Venezuela Accounting

## Overview
Venezuelan accounting localization providing a basic chart of accounts aligned with Venezuelan best practices. Venezuela has no legally mandated chart of accounts. Maintained by Vauxoo. Tested as the base for over 1000 companies. Recommends `account_anglo_saxon` for inventory valuation per Venezuelan accounting standards.

## Country/Region
Venezuela (country code: VE)

## Dependencies
- account

## Key Models
No custom Python model classes. Template loader in `models/template_ve.py` loads the Venezuelan chart of accounts.

## Chart of Accounts
Venezuelan chart of accounts via `template_ve.py`. Based on a mixture of most common accounting software in the Venezuelan market, providing an comfortable starting point. Complies with Venezuelan accepted best practices.

## Tax Structure
Basic Venezuelan taxes configured via template. Venezuela uses:
- **IVA** (Impuesto al Valor Agregado): 16% (standard rate)
- **ISLR** (Impuesto Sobre la Renta): Income tax
- **Municipal taxes**

Note: Venezuela has experienced significant economic volatility; tax rates and regulations change frequently due to macroeconomic conditions.

## Data Files
- `demo/demo_company.xml`: Demo company

## Installation
Install with accounting. On installation with Custom chart, a basic chart is proposed; account defaults for taxes must be set manually.

## Historical Notes
Venezuela does not have a legally mandated chart of accounts, making this a best-practice recommendation rather than a legal compliance module. The country has been through significant currency controls and inflation (using USD accounting increasingly). The recommendation to use `account_anglo_saxon` for inventory valuation reflects Venezuelan practice of valuing stock at invoice cost rather than at delivery note. The module has been used as the accounting foundation for over 1000 companies in Venezuela.
