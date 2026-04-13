---
Module: l10n_nl
Version: 18.0
Type: l10n/nl
Tags: #odoo18 #l10n #accounting
---

# l10n_nl

## Overview
Netherlands accounting localization. Provides Dutch chart of accounts, XBRL taxonomy tags, tax report, and company-specific rounding difference accounts for Dutch GAAP compliance. Authored by Onestein.

## Country
[Netherlands](odoo-18/Modules/account.md) 🇳🇱

## Dependencies
- base_iban
- base_vat
- [account](odoo-18/Core/BaseModel.md)

## Key Models

### AccountChartTemplate
`models/account_chart_template.py`
- `_get_nl_template_data()` — 6-digit codes, mapping to Dutch account codes (recv, pay, 7001, 8001, stock accounts)
- `_get_nl_res_company()` — sets `anglo_saxon_accounting=True`, fiscal country NL, bank prefix 103, cash 101, assigns default VAT taxes (`btw_21`), deferred expense/revenue accounts, rounding difference accounts

### ResCompany
`models/res_company.py` — extends `res.company`
- `l10n_nl_rounding_difference_loss_account_id` (Many2one `account.account`) — loss account for currency/tax rounding differences
- `l10n_nl_rounding_difference_profit_account_id` (Many2one `account.account`) — profit account for rounding differences

### AccountJournal
`models/account_journal.py`
- `_prepare_liquidity_account_vals()` — override: if company fiscal country is NL, auto-tags new liquidity accounts with `l10n_nl.account_tag_25` (Dutch financial report inclusion)

### AccountChartTemplate (post-load)
`models/account_chart_template.py`
- `_post_load_data('nl')` — after chart install: tags suspense account and transfer account with `account_tag_25`; tags unaffected earnings account with `account_tag_undist_profit`

## Data Files
- `data/account_account_tag.xml` — Dutch XBRL taxonomy tags (`account_tag_25`, `account_tag_undist_profit`)
- `data/account_tax_report_data.xml` — Dutch BTW (VAT) report structure
- `data/views/res_config_settings_view.xml` — company settings view for rounding accounts
- `data/template/` — chart of accounts CSV
- `demo/demo_company.xml` — demo company

## Chart of Accounts
6-digit Dutch BAS-style account codes.

| Account | Code | Purpose |
|---|---|---|
| Receivable | recv | Customer AR |
| Payable | pay | Supplier AP |
| Income | 8001 | Sales revenue |
| Expense | 7001 | COGS |
| Stock Input | 1450 | Materials inventory |
| Stock Output | 1250 | Finished goods |
| Stock Valuation | 3200 | Inventory valuation |
| Deferred Expense | 1205 | Prepaid expenses |
| Deferred Revenue | 1405 | Deferred income |
| FX Gain | 8920 | Currency gains |
| FX Loss | 4920 | Currency losses |
| Early Pay Discount Loss | 7065 | Discount given |
| Early Pay Discount Gain | 8065 | Discount received |
| Rounding Loss | 4960 | Tax/rounding differences |
| Rounding Profit | 4950 | Tax/rounding differences |

## Tax Structure
- `btw_21` — Dutch standard rate VAT (21%)
- `btw_21_buy` — Purchase VAT counterpart

Tax report: BTW aangifte (VAT declaration) via `account_tax_report_data.xml`.

## Fiscal Positions
Dutch fiscal positions defined via standard country-based mapping in `l10n_nl` data.

## EDI/Fiscal Reporting
Standard. No dedicated EDI module.

## Installation
`auto_install: ['account']` — installs automatically with account.

Post-init hook: `_preserve_tag_on_taxes` — preserves existing tags on tax accounts (standard chart template pattern).

## Historical Notes

**Odoo 17 → 18 changes:**
- Version 3.4 (was ~3.3 in older versions)
- Rounding difference accounts (`l10n_nl_rounding_difference_*`) introduced in recent versions for better Dutch GAAP compliance
- `account_tag_25` auto-tagging for liquidity accounts is a newer addition ensuring correct XBRL output
- `_post_load_data` hook for post-install tagging is a newer pattern

**Performance Notes:**
- Liquidity account auto-tagging runs only once per company, on chart install
- Dutch tag set is small; minimal performance impact