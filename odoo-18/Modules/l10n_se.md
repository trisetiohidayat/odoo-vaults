---
Module: l10n_se
Version: 18.0
Type: l10n/se
Tags: #odoo18 #l10n #accounting
---

# l10n_se

## Overview
Sweden accounting localization. Provides Swedish BAS chart of accounts (single K1, extended K2, full K3), OCR invoice reference handling with Luhn check digit, vendor OCR validation, and organization number field. Supports three Swedish BAS complexity levels. Authored by XCLUDE and Odoo SA.

## Country
[Sweden](Modules/account.md) 🇸🇪

## Dependencies
- [account](Core/BaseModel.md)
- base_vat

## Key Models

### AccountChartTemplate (base)
`models/template_se.py`
- `_get_se_template_data()` — 4-digit codes, BAS accounts: receivable `a1510`, payable `a2440`, income `a3001`, expense `a4000`, stock accounts, stock valuation
- `_get_se_res_company()` — sets fiscal country Sweden, bank prefix 193, cash 191, transfer 194, POS receivable `a1910`, FX accounts, early-pay discount accounts, default VAT (`sale_tax_25_goods`, `purchase_tax_25_goods`)

### AccountChartTemplate (K2 extended)
`models/template_se_K2.py`
- `_get_se_K2_template_data()` — name "Swedish BAS Chart of Account complete K2", parent=`se`, code_digits=4
- `_get_se_K2_res_company()` — same country/bank/cash/transfer prefix configuration

### AccountChartTemplate (K3 full)
`models/template_se_K3.py`
- `_get_se_K3_template_data()` — name "Swedish BAS Chart of Account complete K3", parent=`se_K2`, code_digits=4
- `_get_se_K3_res_company()` — same configuration

### ResCompany
`models/res_company.py` — extends `res.company`
- `org_number` (Char, computed) — extracted from VAT number: removes all non-digits, strips last 2, formats as `XXXXXX-XXXX`

### ResPartner
`models/res_partner.py` — extends `res.partner`
- `l10n_se_check_vendor_ocr` (Boolean) — marks vendor as requiring OCR number on bills
- `l10n_se_default_vendor_payment_ref` (Char) — fixed default OCR for this vendor; onchange validates via Luhn
- `onchange_l10n_se_default_vendor_payment_ref()` — validates OCR via Luhn check; warns if invalid

### AccountMove
`models/account_move.py` — extends `account.move`
- `_get_invoice_reference_se_ocr2()` — Level 2: base reference + Luhn check digit
- `_get_invoice_reference_se_ocr3()` — Level 3: base reference + length digit (len+2) + Luhn
- `_get_invoice_reference_se_ocr4()` — Level 4: zero-padded to `l10n_se_invoice_ocr_length` + Luhn; raises `UserError` if too long
- `_get_invoice_reference_se_ocr2/3/4_invoice()` — uses `str(self.id)` as reference
- `_get_invoice_reference_se_ocr2/3/4_partner()` — uses `partner.id` or `partner.ref` as reference
- `_onchange_partner_id()` — auto-populates `payment_reference` for vendor bills if partner has default vendor payment ref set
- `_l10n_se_check_payment_reference()` — `@api.constrains`: validates Luhn on vendor bills from partners with `l10n_se_check_vendor_ocr=True`; fires if reference is set or invoice is posted

### AccountJournal
`models/account_journal.py` — extends `account.journal`
- `invoice_reference_model` selection_add: `('se_ocr2', 'Sweden OCR Level 1 & 2')`, `('se_ocr3', 'Sweden OCR Level 3')`, `('se_ocr4', 'Sweden OCR Level 4')`
- `l10n_se_invoice_ocr_length` (Integer) — configurable total OCR length for Level 4 (default=6)
- `_check_l10n_se_invoice_ocr_length()` — `@api.constrains`: minimum length must be > 5

## Data Files
- `data/account.account.tag.csv` — Swedish account classification tags
- `data/account_tax_report_data.xml` — Swedish VAT (moms) report
- `data/res_country_data.xml` — Swedish county data
- `data/template/` — chart of accounts CSV for se, se_K2, se_K3
- `views/partner_view.xml` — partner form with OCR settings
- `views/account_journal_view.xml` — journal form with OCR model/length
- `demo/demo_company.xml`

## Chart of Accounts
4-digit Swedish BAS codes. Three levels:

| Level | Scope | Accounts |
|---|---|---|
| K1 | Minimal | Single-file simplified |
| K2 | Extended | Full BAS subset |
| K3 | Complete | Full Swedish BAS |

Core accounts: 1xxx Assets, 2xxx Equity/Liabilities, 3xxx Income, 4xxx Cost of sales, 5xxx-8xxx Expenses, 9xxx Other.

## Tax Structure
- `sale_tax_25_goods` — Swedish 25% VAT on goods
- Other rates (12%, 6%) defined in template data

Tax report: Swedish moms (VAT) return via `account_tax_report_data.xml`.

## Fiscal Positions
Swedish fiscal positions for EU intra-community trade.

## EDI/Fiscal Reporting
Standard. Peppol supported for e-invoicing.

## Installation
`auto_install: ['account']`

## Historical Notes

**Odoo 17 → 18 changes:**
- Version 1.1; three-tier chart structure (K1/K2/K3) has existed since Odoo 13+
- OCR Level 4 with configurable length is a newer feature
- Organization number computation from VAT is newer
- Vendor OCR validation with Luhn constraint added more recently

**Performance Notes:**
- Luhn validation is O(1) — negligible overhead
- Three-level charts: K1 is smallest, K3 is full BAS