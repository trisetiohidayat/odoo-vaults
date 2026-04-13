---
Module: l10n_hr_kuna
Version: 18.0
Type: l10n/hr
Tags: #odoo18 #l10n #accounting
---

# l10n_hr_kuna

## Overview
Croatian accounting localization using the Kuna (HRK) currency — pre-Euro Croatian chart of accounts based on RRIF 2012 standards. Since Croatia adopted the Euro on 1 January 2023, this module is historical but still relevant for companies transitioning from HRK records or running dual-currency ledgers. Uses Storno accounting and 6-digit codes.

## Country
[Croatia](modules/account.md) 🇭🇷 (Euro zone since 2023)

## Dependencies
- [account](core/basemodel.md)

## Key Models

### AccountChartTemplate
`models/template_hr_kuna.py`
- `_get_hr_kuna_template_data()` — name "RRIF-ov računski plan za poduzetnike", code_digits=6, Storno accounting, maps to RRIF account codes: receivable `kp_rrif1200`, payable `kp_rrif2200`, income `kp_rrif7500`, expense `kp_rrif4199`
- `_get_hr_kuna_res_company()` — sets fiscal country Croatia, bank prefix 101, cash 102, transfer 1009, POS receivable `kp_rrif1213`, currency exchange accounts

## Data Files
- `data/account_tax_report_data.xml` — Croatian tax report structure
- `data/template/` — RRIF chart of accounts CSV
- `demo/demo_company.xml`

## Chart of Accounts
6-digit Croatian RRIF (Računovodski i Financijski Institut — Croatian Accounting Institute) account codes. Storno accounting enabled.

| Account | Code | Purpose |
|---|---|---|
| Receivable | kp_rrif1200 | Customer AR |
| Payable | kp_rrif2200 | Supplier AP |
| Income | kp_rrif7500 | Sales revenue |
| Expense | kp_rrif4199 | COGS |
| Bank | prefix 101 | Bank accounts |
| Cash | prefix 102 | Cash accounts |
| Transfer | 1009 | Internal transfers |
| FX Gain | kp_rrif1050 | Currency gains |
| FX Loss | kp_rrif4754 | Currency losses |

## Tax Structure
Croatian VAT (PDV) rates pre-Euro: 25% standard, 13% reduced, 5% special. Post-Euro adoption, standard EU VAT rules apply.

Tax report: Croatian PDV (VAT) return via `account_tax_report_data.xml`.

## Fiscal Positions
Standard EU fiscal positions adapted for Croatian trade.

## EDI/Fiscal Reporting
Post-Euro: Croatian e-invoicing follows EU standard (Peppol EN 16931). RRIF chart remains the accounting structure.

## Installation
`auto_install: ['account']`

## Historical Notes

**Odoo 17 → 18 changes:**
- Version 13.0 (reflects legacy versioning from older Odoo series; still present in Odoo 18)
- Croatian Kuna (HRK) module preserved in Odoo 18 for historical record keeping and HRK-era data
- Croatia adopted Euro on 1 January 2023 — l10n_hr (Euro) is the primary module; l10n_hr_kuna is for transition/historical use
- RRIF 2012 chart is comprehensive and well-structured; many Croatian companies still reference it

**Performance Notes:**
- 6-digit chart; moderate size
- Storno accounting doubles write operations
- No post-init hooks; standard template loading