---
tags: [odoo, odoo17, module, l10n, localization, chart-of-accounts]
research_depth: medium
---

# L10N Generic COA — Generic Chart of Accounts Template

**Source:** `addons/l10n_generic_coa/`

## Overview

A minimal, multi-country chart of accounts template used as a starting point when no country-specific localization is available. When installed, it provides a standard set of account templates (`account.account.template` and `account.tax.template`) that can be loaded into a company via the fiscal year configuration wizard. It is the fallback localization module — country-specific `l10n_XX` modules extend or replace it.

## Account Template Structure

The module defines a standard set of accounts covering all major accounting categories:

| Category | Account Types |
|----------|--------------|
| Assets | Bank, Cash, Receivable (Current/Long-term), Prepayments, Inventory |
| Liabilities | Accounts Payable, Credit Card, Taxes Payable |
| Equity | Equity, Retained Earnings, Current Year Earnings |
| Revenue | Sales Revenue, Other Revenue |
| Expenses | Cost of Goods Sold, Operating Expenses, Depreciation |

## How It Works

### Installation Flow

1. Install `l10n_generic_coa`
2. Navigate to **Settings → Accounting → Fiscal Year**
3. Click **Configure** → a wizard appears with chart of accounts options
4. Select "Generic Chart of Accounts" template
5. Click **Create** → `account.account.template` records are used to generate actual `account.account` records for the company

### `account.chart.template` Architecture

The chart of accounts system is driven by:

- `account.chart.template` — abstract model defining how to create accounts from template XML data
- `account.account.template` — template records in XML data files (per-company or shared)
- `account.tax.template` — tax template records mapped to tax accounts
- Wizard: `account.update.currency.rate` or `wizard.multi.currency.check` — loads the chart

The `@template('l10n_generic_coa', 'res.company')` decorator in `chart_template.py` maps template data to `res.company` fields (chart, bank accounts, journals, taxes) when the chart is installed.

### Data Files

XML data files under `data/` contain the template account definitions with:
- `account.account.template` records: `code`, `name`, `user_type_id`, `reconcile`, `chart_template_id`
- `account.tax.template` records: tax rates and tax accounts
- Noupdate="1" flags for template data that should not be overwritten on upgrade

## Template Selection in Odoo

When installing accounting for a new company, Odoo presents available chart templates:
- Country-specific templates (e.g., `de_skr03`, `de_skr04`, `l10n_fr`) are shown first
- `l10n_generic_coa` appears as "Generic" or "Chart of Accounts — Generic"

The `account.chart.template` model has `visible` fields and country matching to show the right template per company.

## Country-Specific l10n Modules

Each country module extends or replaces the generic COA:

| Module | Country | Special Features |
|--------|---------|-----------------|
| `l10n_us` | United States | ABA routing, US GAAP accounts |
| `l10n_de` | Germany | SKR03/SKR04, DATEV, DIN 5008 layout |
| `l10n_fr` | France | PCG accounts, FEC export, French tax numbers |
| `l10n_es` | Spain | Spanish tax agencies, SII reporting |
| `l10n_it` | Italy | Italian tax system, FatturaPA e-invoicing |
| `l10n_mx` | Mexico | Mexican SAT accounts, CFDI |
| `l10n_br` | Brazil | Brazilian chart, SPED, NFS-e |
| `l10n_in` | India | Indian GST chart, e-waybill integration |
| `l10n_uk` | United Kingdom | UK GAAP accounts, VAT return |
| `l10n_au` | Australia | BAS reporting, Australian tax tags |

All country modules are located under `addons/l10n_*/`.

## Installing a Country Module

```
Settings → Activate Developer Mode
Apps → Update Apps List
Search: l10n_{country_code}
Install: l10n_{country_code}
```

The country module will replace or update the chart of accounts for companies in that country.

## See Also

- [Modules/account](modules/account.md) — accounting framework and chart template system
- [Modules/l10n_us](modules/l10n_us.md) — US localization example
- [Modules/l10n_de](modules/l10n_de.md) — German localization (SKR03/SKR04)