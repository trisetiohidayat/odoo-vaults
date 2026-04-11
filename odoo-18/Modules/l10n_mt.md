---
Module: l10n_mt
Version: 18.0
Type: l10n/mt
Tags: #odoo18 #l10n #accounting
---

# l10n_mt

## Overview
Malta accounting localization. Provides the chart of accounts, taxes, and tax reports required for Malta-compliant bookkeeping.

## Country
[[Modules/Account|Malta]] 🇲🇹

## Dependencies
- [[Core/BaseModel|account]]
- base_vat

## Key Models

No custom model classes in `models/`. Uses standard Odoo chart-of-accounts loading via `AccountChartTemplate` template methods.

### AccountChartTemplate
- `_get_mt_template_data()` — sets code_digits=6, receivable/payable/income/expense account defaults for Malta
- `_get_mt_res_company()` — sets fiscal country to Malta, configures bank/cash prefixes, assigns default sale/purchase VAT taxes

## Data Files
- `data/menuitem_data.xml` — menu entries for Malta fiscal reporting
- `data/account_tax_report_data.xml` — Malta VAT tax report structure (VAT Return)
- `data/template/` — chart of accounts CSV data

## Chart of Accounts
6-digit account codes following Maltese account structure.

| Account | Code | Purpose |
|---|---|---|
| Receivable | mt_2050 | Customer receivables |
| Payable | mt_3100 | Supplier payables |
| Income | mt_5000 | Default sales revenue |
| Expense | mt_5550 | Default cost of goods sold |
| Bank | prefix 2150 | Bank accounts |
| Cash | prefix 2155 | Cash accounts |
| Transfer | 2300 | Internal transfer |

### Rounding Accounts
- `mt_5400` — income currency exchange
- `mt_5540` — expense currency exchange

## Tax Structure

Default tax assignments for Malta:
- `VAT_S_IN_MT_18_G` — Standard rate sales VAT (18%)
- `VAT_P_IN_MT_18_G` — Standard rate purchase VAT (18%)

Tax report: Malta VAT Return based on `account_tax_report_data.xml`.

## Fiscal Positions
No explicit fiscal position records defined in this module.

## EDI/Fiscal Reporting
No EDI module. Tax reporting via standard `account.tax.report`.

## Installation
Install as any l10n module. `auto_install: ['account']` — installs with account.

Post-init hook: none.

## Historical Notes

**Odoo 17 → 18 changes:**
- Module version bumped from ~1.0 to 1.0. No major structural changes.
- Chart template format consistent with Odoo 18 standard.

Author: Onestein (original), community maintained.