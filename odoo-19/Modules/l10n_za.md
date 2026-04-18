---
type: module
module: l10n_za
tags: [odoo, odoo19, localization, south-africa]
created: 2026-04-06
---

# South Africa - South African Accounting

## Overview
| Property | Value |
|----------|-------|
| **Name** | South Africa - Accounting |
| **Technical** | `l10n_za` |
| **Category** | Localization |
| **Country** | South Africa |

## Description
South African localization providing a generic chart of accounts and SARS (South African Revenue Service) VAT-ready structure for SMEs operating in South Africa.

## Dependencies
- `account`
- `base_vat`

## Key Models

### `account.chart.template` (template_za.py)
Extends `account.chart.template` with South African template data.

**Template data** (`_get_za_template_data`):
- `property_account_receivable_id`: `110010`
- `property_account_payable_id`: `220010`
- `property_stock_valuation_account_id`: `100020`
- `code_digits`: `6`

**Company defaults** (`_get_za_res_company`):
- `anglo_saxon_accounting`: True
- `account_fiscal_country_id`: `base.za`
- `bank_account_code_prefix`: `1200`
- `cash_account_code_prefix`: `1250`
- `transfer_account_code_prefix`: `1010`
- `account_default_pos_receivable_account_id`: `110030`
- `income_currency_exchange_account_id`: `500100`
- `expense_currency_exchange_account_id`: `610340`
- `account_sale_tax_id`: `ST1` (standard VAT 15%)
- `account_purchase_tax_id`: `PT15`
- `income_account_id`: `500010`
- `expense_account_id`: `600010`

## Account Charts
- Chart of Accounts: South African generic chart (6-digit codes)
- Tax Templates: SARS VAT structure (standard rate ST1, purchase PT15)
- Reports: SARS VAT Return structure

## Related
- [Modules/account](Modules/Account.md)
