---
Module: l10n_jp
Version: 18.0
Type: l10n/japan
Tags: #odoo18 #l10n #accounting
---

# l10n_jp

## Overview
Japan accounting localization module providing the official Japanese chart of accounts and consumption tax (VAT/GST) structure. Maintained by Quartile Limited. The module provides 6-digit account codes aligned with Japanese accounting standards and supports tax-included pricing with `tax_included` rounding.

## Country
Japan

## Dependencies
- [Core/BaseModel](Core/BaseModel.md) (account)
- `account` — core accounting module

## Key Models

### AccountChartTemplate (`account.chart.template`, classic extension)
- `_get_jp_template_data()` — returns account field mappings (receivable `l10n_jp_126000`, payable `l10n_jp_220000`, expense `l10n_jp_510000`, income `l10n_jp_410000`, stock valuation `l10n_jp_121100`)
- `_get_jp_res_company()` — sets fiscal country to `base.jp`, cash rounding `round_globally`, bank prefix `1202`, sale tax `l10n_jp_tax_sale_exc_10`

## Data Files
- `data/account_tax_report_data.xml` — Japan Tax Report (Consumption Tax Report) with two sections: Tax Amount (GST Sale/Purchase at 8%/10%, Tax Exempt, Zero-rated) and Taxable Amount
- `data/template/account.account-jp.csv` — chart of accounts (6-digit codes)
- `data/template/account.tax-jp.csv` — tax definitions
- `data/template/account.fiscal.position-jp.csv` — fiscal positions
- `data/template/account.tax.group-jp.csv` — tax groups
- `demo/demo_company.xml` — demo company data

## Chart of Accounts
6-digit account codes. Key accounts include:
- Receivable: `l10n_jp_126000`
- Payable: `l10n_jp_220000`
- Bank: `1202xx`, Cash: `1201xx`, Transfer: `1236xx`
- Inventory/Stock: `l10n_jp_121100` (valuation), `121200` (input), `121300` (output)
- Default POS receivable: `l10n_jp_126200`
- Anglo-Saxon accounting supported

## Tax Structure
Japan uses **Consumption Tax** (not called VAT). Tax is always price-excluded (rounded globally):

| Tax ID | Rate | Type | Notes |
|--------|------|------|-------|
| `l10n_jp_tax_sale_exc_8` | 8% | sale | Default sale tax; 8% reduced rate |
| `l10n_jp_tax_sale_exc_10` | 10% | sale | Default sale tax; standard rate (Oct 2019) |
| `l10n_jp_tax_sale_exempt` | 0% | sale | Exempt (輸出免税) |
| `l10n_jp_tax_sale_non_vat` | 0% | sale | Non-VAT/Outside scope (対象外売上) |
| `l10n_jp_tax_purchase_exc_8` | 8% | purchase | |
| `l10n_jp_tax_purchase_exc_10` | 10% | purchase | Default purchase tax |
| `l10n_jp_tax_purchase_imp` | 0% | purchase | Oversea Purchase / Imported |

Tax groups: `l10n_jp_tax_group_8`, `l10n_jp_tax_group_10`, `l10n_jp_tax_group_exempt`

## Fiscal Positions
The module includes fiscal positions `内税` (included-tax) and `外税` (excluded-tax) primarily for POS implementations. These handle special consumption tax treatment where the tax amount is embedded in the sale price.

## EDI/Fiscal Reporting
The companion module [Modules/l10n_jp_ubl_pint](Modules/l10n_jp_ubl_pint.md) provides Peppol PINT JP e-invoicing. The tax report is named **Consumption Tax Report** (消費税申告書) with two main groupings: Tax Amount and Taxable Amount sections.

## Installation
Install via Apps or during company setup by selecting Japan as country. Auto-installs with `account`. Version 2.3 from Odoo 17 to 18 introduced the Japan tax report improvements.

## Historical Notes
- Version 2.3: Updated tax report structure in Odoo 18.0, maintains compatibility with Odoo 17.
- The 8% rate was the previous reduced rate (2014–2019); 10% is current standard rate.
- Japan tax is price-excluded by default (`account_price_include` not set in template, relies on rounding method `round_globally`).
- `tax_calculation_rounding_method: round_globally` is explicitly set for Japan to comply with consumption tax rounding rules.
