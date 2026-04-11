---
Module: l10n_si
Version: 18.0
Type: l10n/si
Tags: #odoo18 #l10n #accounting
---

# l10n_si

## Overview
Slovenian accounting localization. Provides Slovenia chart of accounts (SURS/GDPS taxonomy), tax structure, and SI01 structured payment reference model (UJP system). Uses Storno accounting. 6-digit account codes.

## Country
[[Modules/Account|Slovenia]] 🇸🇮

## Dependencies
- [[Core/BaseModel|account]]
- base_vat

## Key Models

### AccountChartTemplate
`models/template_si.py`
- `_get_si_template_data()` — code_digits=6, Storno accounting, maps to Slovenian GDPS codes: receivable `gd_acc_120000`, payable `gd_acc_220000`, income `gd_acc_762000`, expense `gd_acc_702000`
- `_get_si_res_company()` — sets fiscal country Slovenia, bank prefix 110, cash 100, transfer 109, POS receivable `gd_acc_125000`, currency exchange accounts, default VAT (`gd_taxr_3`, `gd_taxp_3`)

### AccountMove
`models/account_move.py` — extends `account.move`
- `_get_invoice_reference_si_partner()` — generates SI01 structured reference: `SI01 P1-P2-P3K` where P1=journal ID, P2=invoice year (last 2 digits), P3=partner ID, K=check digit
- `_get_invoice_reference_si_invoice()` — same format with P3=invoice sequence number (trailing digits from name)
- `_build_invoice_reference(p3)` — shared builder: computes reference_base = `P1-P2-P3`, calculates check digit (weighted sum mod 11, 0 if 10 or 11), returns `SI01 {reference_base}{check_digit}`

### AccountJournal
`models/account_journal.py` — extends `account.journal`
- `invoice_reference_model` selection_add: `('si', 'Slovenian 01 (SI01 25-1235-8403)')` — enables SI01 structured reference per journal

## Data Files
- `data/account_tax_report_data.xml` — Slovenian VAT (DDV) report
- `data/account_tax_report_ir_data.xml` — reverse charge VAT report
- `data/account_tax_report_pd_data.xml` — periodicity declaration
- `data/account_tax_report_pr_data.xml` — profit report
- `data/account_account_tag.xml` — Slovenian account classification tags
- `data/template/` — chart of accounts CSV
- `demo/demo_company.xml`

## Chart of Accounts
6-digit Slovenian GDPS (Gross Domestic Product Statistics) / SURS taxonomy account codes. Storno accounting enabled.

| Account | Code | Purpose |
|---|---|---|
| Receivable | gd_acc_120000 | Customer AR |
| Payable | gd_acc_220000 | Supplier AP |
| Income | gd_acc_762000 | Sales revenue |
| Expense | gd_acc_702000 | COGS |
| Bank | prefix 110 | Bank accounts |
| Cash | prefix 100 | Cash accounts |
| Transfer | 109 | Internal transfers |
| FX Gain | gd_acc_777000 | Currency gains |
| FX Loss | gd_acc_484000 | Currency losses |

## Tax Structure
- `gd_taxr_3` — Slovenian standard VAT 22% (reduced from 20%)
- `gd_taxp_3` — purchase VAT counterpart

Additional rates (9.5%, 0%) defined in template data.

Tax report: DDV (VAT) return via `account_tax_report_data.xml`. Periodicity declaration (PD) and profit report (PR) via separate report definitions.

## Fiscal Positions
Standard EU fiscal positions adapted for Slovenia — intra-community B2B, export.

## EDI/Fiscal Reporting
SI01 structured payment reference for bank transfers (UJP system). Slovenian e-invoicing follows EU standard.

## Installation
`auto_install: ['account']`

## Historical Notes

**Odoo 17 → 18 changes:**
- Version 1.1; Slovenian localization has been stable
- SI01 reference model with custom check digit algorithm has existed since earlier versions
- Multiple tax report definitions (VAT, reverse charge, PD, PR) are comprehensive
- Storno accounting explicitly enabled for Slovenian compliance

**Performance Notes:**
- SI01 check digit uses weighted sum (no external library) — very lightweight
- 6-digit chart is moderate size; standard install time