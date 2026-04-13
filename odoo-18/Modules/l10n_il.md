---
Module: l10n_il
Version: 18.0
Type: l10n/israel
Tags: #odoo18 #l10n #accounting #vat #israel
---

# l10n_il — Israel Accounting

## Overview
The Israel localization module provides a generic Israeli chart of accounts, VAT (Mas Revach) taxes, a VAT tax report conforming to Israeli Income Tax Authority (ITA) requirements, and account tags for withholding taxes. Israel does not have a country-specific Peppol node; e-invoicing in Israel follows a different regulatory framework.

## Country
Israel (`IL`)

## Dependencies
- [account](Modules/account.md)

## Key Models

### template_il.py
```python
class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('il')
    def _get_il_template_data(self): ...

    @template('il', 'res.company')
    def _get_il_res_company(self): ...
```
`il` chart template. Key account mappings:

| Property | Account Code |
|---|---|
| Receivable | `il_account_101200` (POS: `il_account_101201`) |
| Payable | `il_account_111100` |
| Expense | `il_account_212200` |
| Income | `il_account_200000` |
| Stock input | `il_account_101120` |
| Stock output | `il_account_101130` |
| Stock valuation | `il_account_101110` |
| Currency exchange gain | `il_account_201000` |
| Currency exchange loss | `il_account_202100` |

- `code_digits`: 6
- Default sales tax: `il_vat_sales_18` (18% VAT)
- Default purchase tax: `il_vat_inputs_18` (18% input VAT)
- `bank_account_code_prefix`: `1014` | `cash_account_code_prefix`: `1015` | `transfer_account_code_prefix`: `1017`

## Data Files
- `data/account_account_tag.xml` — Five account tags for Israeli tax reporting:
  - `account_tag_retention_tax_vendor_account` — "Withholding Vendor Tax Account"
  - `account_tag_dividend_account` — "Dividend Account"
  - `account_tag_retention_tax_dividend_account` — "Withholding Dividend Tax Account"
  - `account_tag_retention_tax_employees_account` — "Withholding Employees Tax Account"
  - `account_tag_retention_tax_customers_account` — "Withholding Customers Tax Account"
- `data/account_tax_report_data.xml` — **VAT Report (PCN874)**, rooted at `account.generic_tax_report`, country `base.il`. Contains lines for:
  - VAT SALES (BASE) — `ILTAX_OUT_BASE`
  - VAT SALES (TAX) — `ILTAX_OUT_BALANCE` (includes `ILTAX_OUT_BALANCE_00` and `ILTAX_OUT_BALANCE_PA`)
  - VAT Exempt Sales (BASE) — `ILTAX_OUT_BASE_exempt`
  - VAT INPUTS (TAX) — `ILTAX_IN_BALANCE` with breakdowns at 17%, 18%, 2/3%, 1/4%, PA 16%
  - VAT INPUTS (fixed assets) — `ILTAX_VAT_IN_FA`
  - VAT DUE — computed as `(out_balance) - (in_balance) - (fixed_assets)`
- `demo/demo_company.xml` — Demo company "IL Company" in Tel Aviv (`תל אביב-יפו`), loads `il` chart template.

## Chart of Accounts
The Israeli chart uses 6-digit account codes structured around the Israeli accounting standard. The accounts map to the Israeli Income Tax Authority's classification: 1xxx = assets, 2xxx = liabilities/equity, 4xxx = income, 5xxx = expenses, 6xxx/7xxx = other income/expenses.

## Tax Structure
Israel's VAT (Ma'am / מס ערך מוסף) is the primary consumption tax. The standard rate is 18% (as of the Odoo 18 module). The system tracks:
- Output VAT (sales) at different rates
- Input VAT (purchases) claimable against output VAT
- VAT on fixed asset acquisitions (separate tracking)
- Exempt supplies (no VAT — tracked separately for financial reporting)

The VAT DUE line computes: `(VAT Sales Tax) - (VAT Input Tax) - (VAT on Fixed Assets)`.

## Fiscal Positions
The manifest description notes "Multiple Fiscal positions" — however, fiscal positions are not hardcoded in data files. They should be created manually per the Israeli tax rules (export vs. domestic vs. exempt supplies).

## Installation
Standard installation, auto-installs with `account`. Demo data is optional (controlled by the `demo` key in the manifest).

## Historical Notes
- **Odoo 17 → 18:** Version bump from 1.0 to 1.1. The tax report structure was updated to reflect current ITA requirements. Account tags for withholding taxes were added.
- Author: community/local partners (not a named external author in the manifest).
- Israel requires electronic invoice submission to the ITA (gtax / גט"ס) — this module provides the foundational chart but not the live e-invoicing API integration.
