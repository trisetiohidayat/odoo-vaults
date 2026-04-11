---
Module: l10n_cn
Version: 18.0
Type: l10n/china
Tags: #odoo18 #l10n #accounting #china
---

# l10n_cn — China Accounting

## Overview
Comprehensive Chinese accounting localization with support for two chart of accounts: **Accounting Standards for Small Business Enterprises** (ASBSE / Small Enterprise Standard) and **Large Enterprise Standard** (BIS). Includes Fapiao (electronic invoice) number support, Chinese amount-in-words conversion via `cn2an` library, storno (negative posting) accounting, and province/state data.

Maintained by the Chinese Odoo community (openerp-china / jeffery9).

## Country
China

## Dependencies
- base
- account

## Key Models

### `AccountMove` (`account.move`)
- `_inherit = 'account.move'`
- `fapiao` Char field (size 8, copy=False, tracked) — stores the 8-digit Fapiao invoice number
- `_check_fapiao()` constrains: Fapiao must be exactly 8 decimal digits
- `check_cn2an()` — checks if `cn2an` library is installed (pip install cn2an)
- `_convert_to_amount_in_word(number)` — converts numbers to Chinese RMB amount in words (calls `an2cn(number, 'rmb')`)
- `_count_attachments()` — overrides to count attachments on the move and related payments/statements

### `AccountChartTemplate` — three variants (all inherit `account.chart.template`)

**`_get_cn_common_template_data`** (via `template_cn_common.py`):
- Template key: `cn_common` (parent/base template)
- `visible: 0` — not shown in UI, only serves as parent
- 6-digit code digits, storno accounting enabled (`use_storno_accounting: True`)
- Receivable: `l10n_cn_common_account_1122`, Payable: `l10n_cn_common_account_2202`
- Stock valuation: `l10n_cn_common_account_1405`, Production cost: `l10n_cn_common_account_1411`
- Company defaults: fiscal country `base.cn`, bank prefix `1002`, cash prefix `1001`, deferred expense `1801`, deferred revenue `2401`, POS receivable `112201`
- Creates Cash and Bank journals with default accounts `1001` and `1002`

**`_get_cn_template_data`** (template `cn` — Small Business):
- Name: "Accounting Standards for Small Business Enterprises"
- `parent: 'cn_common'` — inherits from cn_common
- Expense: `l10n_cn_account_5401`, Income: `l10n_cn_account_5001`, Stock input: `140201`, Stock output: `140202`
- Company: fiscal country `base.cn`, transfer account `1012`, WIP accounts, currency exchange accounts, cash difference accounts, default sale tax `l10n_cn_sales_excluded_13`, purchase tax `l10n_cn_purchase_excluded_13`

**`_get_cn_large_bis_template_data`** (template `cn_large_bis` — Large Enterprise):
- Full large enterprise chart of accounts
- Additional cost/revenue accounts for larger organizations

## Data Files
- `views/account_move_view.xml` — Fapiao field on journal entries
- `views/account_report.xml` — Chinese financial report layouts
- `views/report_voucher.xml` — Payment voucher report supporting amount-in-words
- `demo/demo_company.xml` — Demo company using small business chart
- `demo/demo_company_asbe.xml` — Demo company using ASBE standard

## Chart of Accounts
Two tiers:

**Small Business (cn / ASBSE)** — 6-digit codes organized as:
- 1xxx: Assets (1001 Cash, 1002 Bank, 1122 Receivables, 1402 Inventory, 1411 WIP)
- 2xxx: Liabilities (2202 Payables)
- 5xxx: Expenses (5401 Operating expenses)
- 4xxx: Revenue (5001 Sales revenue)

**Large Enterprise (cn_large_bis)** — extended account structure with more granular sub-accounts.

All templates use **storno accounting** (negative posting allowed for journal entries).

## Tax Structure
- **VAT (Value Added Tax /增值税)** — Chinese VAT system with multiple rates
- Tax templates set for excluded (zero-rated) sales/purchases at 13%
- Tax tags for VAT output/input classification

## Fiscal Positions
Standard Chinese fiscal positions for inter-province transactions.

## EDI/Fiscal Reporting
- **Fapiao support** — Fapiao numbers are tracked on `account.move` and validated as 8-digit numbers
- **Amount-in-words** — Chinese RMB characters (壹贰叁肆伍陆柒捌玖拾佰仟万) generated via `cn2an` library; report voucher prints amounts in Chinese characters
- Province data imported via `l10n_cn_city` dependency

## Installation
Auto-installs with `account`. Requires `cn2an` Python package for Chinese amount conversion. China chart (small business) is the default; large enterprise is available as an alternative.

## Historical Notes
Version 1.8 in Odoo 18. Maintained by openerp-china community (jeffery9). Changes vs Odoo 17: updated to Odoo 16+ ORM patterns, storno accounting enabled by default, improved voucher printing with cn2an integration.