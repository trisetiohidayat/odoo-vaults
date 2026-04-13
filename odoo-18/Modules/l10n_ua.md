---
Module: l10n_ua
Version: 18.0
Type: l10n/ukraine
Tags: #odoo18 #l10n #accounting #vat #psbo #ukraine
---

# l10n_ua — Ukraine Accounting

## Overview
The Ukraine localization module provides an IFRS-aligned chart of accounts (the PSBO — П(С)БО, Ukrainian abbreviation for National Accounting Standards / IFRS-adapted), supports Ukrainian as the display language for amounts-in-words, enables **Storno accounting** (credit-note reversal by negative debit rather than debit-credit swap), and sets up VAT at the standard 20% rate. The module is community-authored by ERP Ukraine.

## Country
Ukraine (`UA`)

## Dependencies
- [account](odoo-18/Modules/account.md)

## Key Models

### template_ua_psbo.py
```python
class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ua_psbo')
    def _get_ua_psbo_template_data(self): ...

    @template('ua_psbo', 'res.company')
    def _get_ua_psbo_res_company(self): ...
```
`ua_psbo` chart template (IFRS-aligned Ukrainian chart):

**`_get_ua_psbo_template_data`**:
| Property | Account Code |
|---|---|
| Receivable | `ua_psbp_361` (POS: `ua_psbp_366`) |
| Payable | `ua_psbp_631` |
| Expense | `ua_psbp_901` |
| Income | `ua_psbp_701` |
| Stock input | `ua_psbp_2812` |
| Stock output | `ua_psbp_2811` |
| Stock valuation | `ua_psbp_281` |

- `name`: `IFRS Chart of Accounts`
- `code_digits`: 6
- `use_storno_accounting`: **True** (key Ukraine-specific feature)
- `display_invoice_amount_total_words`: **True** (amounts in words in Ukrainian)

**`_get_ua_psbo_res_company`**:
- `anglo_saxon_accounting`: True
- `account_fiscal_country_id`: `base.ua`
- Bank prefix: `311` | Cash: `301` | Transfer: `333`
- Default sales tax: `sale_tax_template_vat20_psbo`
- Default purchase tax: `purchase_tax_template_vat20_psbo`
- Currency exchange gain: `ua_psbp_711` | loss: `ua_psbp_942`

## Data Files
- `data/account_account_tag_data.xml` — Single account tag: `acc_tag_vat` (applicability: `accounts`, name: "VAT"). This tag can be applied to accounts used for VAT reporting.
- `demo/demo_company.xml` — Demo company "UA Company" in Kyiv (`Мечникова вулиця`, Kyiv, zip 01133), loads `ua_psbo` chart template.

## Chart of Accounts
The PSBO (П(С)БО) chart uses a 6-digit coding scheme. The module uses account codes prefixed with `ua_psbp_` to avoid collisions with other country charts. The structure follows the Ukrainian accounting plan:
- 1xx — Non-current assets (including 101–109 for cash/bank accounts, 12x for inventories)
- 2xx — Current assets (receivables, inventory, cash equivalents)
- 3xx — Liabilities (payables, accruals)
- 4xx — Equity
- 6xx/7xx — Expenses/Income
- 9xx — Off-balance sheet

## Tax Structure
**Ukrainian VAT (ПДВ / Podatok na dobanu vartist):** Standard rate **20%**. A 14% reduced rate exists for certain agricultural goods. The module defines `sale_tax_template_vat20_psbo` and `purchase_tax_template_vat20_psbo` as the default tax templates. Fiscal positions determine VAT exemption for exports (0% rate) and other special cases.

## Storno Accounting
`use_storno_accounting: True` is a critical Ukraine-specific setting. In Storno accounting, credit memos (refunds) are recorded by posting a negative amount to the same account that was originally debited — rather than swapping the debit/credit sides. This matches Ukrainian accounting regulations (П(С)БО) and tax authority requirements for how credit notes are processed. When enabled, Odoo generates credit notes with negative line amounts rather than mirrored debit/credit entries.

## Installation
Auto-installs with `account`. Standard installation.

## Historical Notes
- **Odoo 17 → 18:** Version bumped from 1.3 to 1.4. The PSBO chart was updated for Odoo 18's account model changes. Storno accounting was retained as a key local requirement.
- The IFRS Chart of Accounts name reflects the Ukrainian government's push to align national standards with IFRS since 2012.
- Author: ERP Ukraine (https://erp.co.ua) — a local Ukrainian Odoo partner.
