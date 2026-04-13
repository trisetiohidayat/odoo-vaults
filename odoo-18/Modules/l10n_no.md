---
Module: l10n_no
Version: 18.0
Type: l10n/no
Tags: #odoo18 #l10n #accounting
---

# l10n_no

## Overview
Norway accounting localization. Provides chart of accounts, Norwegian VAT tax report, and KID payment reference model for Norwegian invoices. Authored by Rolv Råen, updated by Bringsvor Consulting.

## Country
[Norway](account.md) 🇳🇴 (non-EU, EFTA)

## Dependencies
- base_iban
- base_vat
- [account](BaseModel.md)

## Key Models

### AccountChartTemplate
`models/template_no.py`
- `_get_no_template_data()` — code_digits=4, maps to Norwegian account codes (chart1500, chart2400, chart4000, chart3000)
- `_get_no_res_company()` — sets fiscal country Norway, bank prefix 1920, cash 1900, transfer 1940, FX accounts, early-pay discount accounts, default VAT taxes (`tax3`, `tax2`)

### ResCompany
`models/res_company.py` — extends `res.company`
- `l10n_no_bronnoysund_number` (Char) — related field synced from partner. Used to store Brønnøysund Register Center number (REORGNR / 9-digit org number)

### ResPartner
`models/res_partner.py` — extends `res.partner`
- `l10n_no_bronnoysund_number` (Char, size=9) — Register of Legal Entities number, used for B2G Peppol identification
- `_deduce_country_code()` — override: if `l10n_no_bronnoysund_number` is set, returns `'NO'` even without VAT
- `_peppol_eas_endpoint_depends()` — extends Peppol endpoint field dependencies to include `l10n_no_bronnoysund_number`

### AccountMove
`models/account_move.py` — extends `account.move`
- `_get_invoice_reference_no_invoice()` — uses `_get_kid_number()` with 7-char invoice number + partner ID
- `_get_invoice_reference_no_partner()` — same format via partner ID
- `_get_kid_number()` — generates KID (KundeId) reference: 7-digit invoice padded + 7-digit partner ID suffix, with Luhn check digit appended

### AccountJournal
`models/account_journal.py` — extends `account.journal`
- `invoice_reference_model` selection_add: `('no', 'Norway')` — enables Norwegian KID reference model per journal

## Data Files
- `data/account_tax_report_data.xml` — Norwegian VAT/mva report structure
- `data/template/` — chart of accounts CSV
- `demo/demo_company.xml` — demo company

## Chart of Accounts
4-digit Norwegian account codes.

| Account | Code | Purpose |
|---|---|---|
| Receivable | chart1500 | Customer AR |
| Payable | chart2400 | Supplier AP |
| Income | chart3000 | Sales revenue |
| Expense | chart4000 | COGS |
| Bank | 1920 | Bank accounts |
| Cash | 1900 | Cash |
| Transfer | 1940 | Internal transfer |
| FX Gain | chart8060 | Currency gains |
| FX Loss | chart8160 | Currency losses |
| Early Pay Discount Loss | chart4372 | Supplier discounts |
| Early Pay Discount Gain | chart3082 | Customer discounts |

## Tax Structure
- `tax3` — sales VAT (25% standard)
- `tax2` — purchase VAT

Tax report: Norwegian VAT return (MVA-melding) via `account_tax_report_data.xml`.

## Fiscal Positions
Standard country-based fiscal positions in template data.

## EDI/Fiscal Reporting
Peppol/e-invoicing: Norwegian org number from Brønnøysund used as Peppol endpoint via `_peppol_eas_endpoint_depends()`.

## Installation
`auto_install: ['account']`

Post-init hook: `_preserve_tag_on_taxes`

## Historical Notes

**Odoo 17 → 18 changes:**
- Version 2.1; relatively stable across Odoo versions
- Brønnøysund number added for Peppol compatibility in newer versions
- KID reference model is a long-established Norwegian pattern

**Performance Notes:**
- KID generation uses `stdnum.luhn` for check digit; lightweight
- Small chart (4-digit), fast install