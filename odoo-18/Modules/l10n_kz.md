---
Module: l10n_kz
Version: 18.0
Type: l10n/kazakhstan
Tags: #odoo18 #l10n #accounting #vat #kz
---

# l10n_kz — Kazakhstan Accounting

## Overview
The Kazakhstan localization module provides a base chart of accounts and the statutory VAT Report (Form 300.00) as required by the Kazakh tax authorities. Kazakhstan uses a standard 12% VAT rate. The module also sets up journal defaults (cash and bank accounts) for a complete accounting setup.

## Country
Kazakhstan (`KZ`)

## Dependencies
- [account](modules/account.md)

## Key Models

### template_kz.py
```python
class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('kz')
    def _get_kz_template_data(self): ...

    @template('kz', 'res.company')
    def _get_kz_res_company(self): ...

    @template('kz', 'account.journal')
    def _get_kz_account_journal(self): ...
```
`kz` chart template with three template handlers:

**`_get_kz_template_data`** — key account mappings:
| Property | Account Code |
|---|---|
| Receivable | `kz1210` |
| Payable | `kz3310` |
| Income | `kz6010` |
| Expense | `kz7010` |

- `code_digits`: 4

**`_get_kz_res_company`** — company defaults:
- `account_fiscal_country_id`: `base.kz`
- Bank prefix: `103` | Cash: `101` | Transfer: `102`
- Default sales tax: `l10n_kz_tax_vat_12_sale` (12% VAT)
- Default purchase tax: `l10n_kz_tax_vat_12_purchase`
- Currency exchange gain: `kz6250` | loss: `kz7430`
- Early pay discount gain: `kz6291` | loss: `kz7481`
- Cash difference income: `kz6210` | expense: `kz7410`

**`_get_kz_account_journal`** — journal defaults:
- `cash` journal: `kz1010`
- `bank` journal: `kz1030`

## Data Files
- `data/tax_report.xml` — **VAT Report — Form 300.00**, rooted at `account.generic_tax_report`, country `base.kz`. A detailed multi-line report with two columns (net + tax) and a hierarchical line structure covering:
  - VAT accrual section with lines 300.00.001 (sales turnover with VAT, split by invoices issued / POS / export)
  - Purchases sections (lines 300.00.002, 300.00.003, etc.)
  - Adjustments
  - VAT payable / recoverable calculations
  - Code pattern: `L10N_KZ_300_00_*`
- `demo/demo_company.xml` — Demo company "KZ Company" in Shymkent, loads `kz` chart template.

## Chart of Accounts
Kazakhstan uses a 4-digit account code structure aligned with the national accounting chart (НСБУ / National Accounting Standards) and IFRS. The codes follow the standard Russian/CIS numbering: 1xxx = assets, 2xxx = liabilities, 3xxx = equity, 4xxx/5xxx/6xxx = income/expenses, 7xxx = other. Storno accounting is not enabled.

## Tax Structure
Kazakhstan's VAT rate is **12%** (reduced from 14% in prior years). The system tracks output VAT on sales and input VAT on purchases. The Form 300.00 report is filed monthly and covers:
- Sales turnover (with and without VAT)
- VAT collected on sales
- Purchases (domestic, imports, without VAT)
- VAT recoverable
- Net VAT payable/recoverable

## Installation
Auto-installs with `account`. Standard installation.

## Historical Notes
- **Odoo 17 → 18:** Version bumped from initial release. No major structural changes.
- The 12% VAT rate reflects Kazakhstan's post-2022 VAT rate. Earlier versions of Odoo may have had 12% as well, but Form 300.00 has been updated to match current filing requirements.
- This module is a base chart. Enterprise-level Kazakhstan localization may include additional tax types (excise, property tax) handled separately.
