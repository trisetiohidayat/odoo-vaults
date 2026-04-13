---
type: module
module: l10n_cn
tags: [odoo, odoo19, localization, china]
created: 2026-04-06
---

# China - Chinese Accounting

## Overview
| Property | Value |
|----------|-------|
| **Name** | China - Accounting |
| **Technical** | `l10n_cn` |
| **Category** | Localization |
| **Country** | China |

## Description
Chinese accounting localization providing both small business (SME) and large enterprise chart of accounts, Chinese province data, account types (科目类型), and VAT support. Supports printing vouchers with amount-in-words in Chinese characters when the `cn2an` library is installed.

## Dependencies
- `base`
- `account`

## Key Models

### `account.chart.template` (template_cn.py)
Extends `account.chart.template` with Chinese template data.

**Template data** (`_get_cn_template_data`):
- `name`: Accounting Standards for Small Business Enterprises
- `parent`: `cn_common` (inherits from common Chinese chart)
- `property_account_expense_categ_id`: `l10n_cn_account_5401`
- `property_account_income_categ_id`: `l10n_cn_account_5001`

**Company defaults** (`_get_cn_res_company`):
- `account_fiscal_country_id`: `base.cn`
- `transfer_account_code_prefix`: `1012`
- `account_sale_tax_id`: `l10n_cn_sales_excluded_13`
- `account_purchase_tax_id`: `l10n_cn_purchase_excluded_13`
- `tax_calculation_rounding_method`: `round_per_line`
- `account_stock_journal_id`: `inventory_valuation`
- `account_stock_valuation_id`: `l10n_cn_common_account_1403`
- Supports Chinese voucher printing with amount-in-words (cn2an library)

### `account.chart.template` (template_cn_common.py)
Common base chart used by both SME and large enterprise charts. Contains shared account definitions.

### `account.chart.template` (template_cn_large_bis.py)
Large business enterprise chart template with extended account structure.

## Account Charts
- Chart of Accounts: Small Business Enterprises (小企业会计科目表), Large Enterprise (大企业会计科目表)
- Tax Templates: Chinese VAT (13%, 9%, 6%, etc. — excluded from price)

## Related
- [Modules/account](Modules/account.md)
