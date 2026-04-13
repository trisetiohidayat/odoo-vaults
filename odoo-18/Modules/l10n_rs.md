---
Module: l10n_rs
Version: 18.0
Type: l10n/rs
Tags: #odoo18 #l10n #accounting
---

# l10n_rs

## Overview
Serbia accounting localization. Provides Serbian chart of accounts based on the official "Pravilnik o kontnom okviru" (Official Gazette RS 89/2020), tax structure, fiscal positions, and turnover date field. Uses Storno accounting and 4-digit codes. Authored by Modoolar and Odoo SA.

## Country
[Serbia](modules/account.md) 🇷🇸

## Dependencies
- [account](core/basemodel.md)
- base_vat

## Key Models

### AccountMove
`models/account_move.py` — extends `account.move`
- `l10n_rs_turnover_date` (Date) — separate turnover date field: Serbian VAT law distinguishes the tax point (when supply occurs) from the invoice date; this date is used for JIS (SAF-T) reporting

### AccountChartTemplate
`models/template_rs.py`
- `_get_rs_template_data()` — code_digits=4, Storno accounting, maps to Serbian account codes (rs_204, rs_435, rs_604, rs_501)
- `_get_rs_res_company()` — sets `anglo_saxon_accounting=True`, fiscal country Serbia, bank prefix 241, cash 243, transfer 250, currency exchange accounts, cash difference accounts, default VAT taxes (`rs_sale_vat_20`, `rs_purchase_vat_20`)

## Data Files
- `data/account_tax_report_data.xml` — Serbian VAT report structure
- `data/menuitem_data.xml` — menu entries
- `data/template/` — chart of accounts CSV
- `demo/demo_company.xml`

## Chart of Accounts
4-digit Serbian chart based on RS 89/2020.

| Account | Code | Purpose |
|---|---|---|
| Receivable | rs_204 | Customer AR |
| Payable | rs_435 | Supplier AP |
| Income | rs_604 | Sales revenue |
| Expense | rs_501 | COGS |
| Bank | prefix 241 | Bank accounts |
| Cash | prefix 243 | Cash accounts |
| Transfer | 250 | Internal transfers |
| FX Gain | rs_663 | Currency gains |
| FX Loss | rs_563 | Currency losses |
| Cash Diff. | rs_6791 / rs_5791 | Rounding differences |

## Tax Structure
- `rs_sale_vat_20` — Serbian standard VAT (20%)
- `rs_purchase_vat_20` — purchase VAT counterpart

Tax report: VAT return via `account_tax_report_data.xml`, JIS (Serbian SAF-T) format.

## Fiscal Positions
Standard EU-style fiscal positions adapted for Serbian trade (B2C, B2B EU, export/import).

## EDI/Fiscal Reporting
Serbian SAF-T (JIS — Jedinstveni Informacioni Sistem) format. Turnover date field enables correct VAT period assignment in SAF-T exports. See also [l10n_rs_edi](modules/l10n_rs_edi.md) for e-invoice (eFaktura) support.

## Installation
`auto_install: ['account']`

## Historical Notes

**Odoo 17 → 18 changes:**
- Version 1.0; relatively new module — Serbia localization was less developed in older Odoo versions
- Based on official RS 89/2020 chart of accounts (replaces older 2015/2016 charts)
- Storno accounting enabled (Serbian companies can use either method)
- Turnover date field is a key addition for SAF-T compliance

**Performance Notes:**
- 4-digit chart is compact; fast install
- No post-init hooks