---
Module: l10n_sk
Version: 18.0
Type: l10n/sk
Tags: #odoo18 #l10n #accounting
---

# l10n_sk

## Overview
Slovakia accounting localization. Provides Slovak chart of accounts (2020), tax structure, and company-specific fields (trade registry, income tax ID). Uses Storno accounting and 6-digit codes. Slovak module version 1.0, authored by 26HOUSE.

## Country
[[Modules/Account|Slovakia]] 🇸🇰

## Dependencies
- base_iban
- base_vat
- [[Core/BaseModel|account]]

## Key Models

### AccountChartTemplate
`models/template_sk.py`
- `_get_sk_template_data()` — code_digits=6, Storno accounting enabled, maps to Slovak codes: receivable `chart_sk_311000`, payable `chart_sk_321000`, income `chart_sk_604000`, expense `chart_sk_504000`, stock accounts
- `_get_sk_res_company()` — sets fiscal country Slovakia, bank prefix 221, cash 211, transfer 261, suspense `chart_sk_261000`, currency exchange accounts, cash difference accounts, early-pay discount accounts, default VAT (`vy_tuz_23`, `vs_tuz_23`)

### ResCompany
`models/res_company.py` — extends `res.company`
- `trade_registry` (Char) — Slovak trade registry number (Obchodný register)
- `income_tax_id` (Char) — Slovak income tax ID (Daňové identifikačné číslo)

### BaseDocumentLayout
`models/res_company.py` — extends `base.document.layout`
- `account_fiscal_country_id`, `company_registry`, `income_tax_id` — related fields to surface Slovak company identifiers in document layout/printing

### AccountMove
`models/account_move.py` — extends `account.move`
- Adds no new fields — inherits standard [[Core/BaseModel|account.move]] with Slovak fiscal country enabled

## Data Files
- `data/template/` — Slovak chart of accounts CSV
- `views/res_partner_views.xml`, `views/res_company_views.xml`, `views/report_invoice.xml`, `views/account_move_views.xml`, `views/report_template.xml`
- `demo/demo_company.xml`

## Chart of Accounts
6-digit Slovak accounting plan (2020). Storno accounting enabled.

| Account | Code | Purpose |
|---|---|---|
| Receivable | chart_sk_311000 | Customer AR |
| Payable | chart_sk_321000 | Supplier AP |
| Income | chart_sk_604000 | Sales revenue |
| Expense | chart_sk_504000 | COGS |
| Stock Input | chart_sk_131000 | Materials |
| Stock Output | chart_sk_504000 | Finished goods |
| Stock Valuation | chart_sk_132000 | Inventory valuation |
| Bank | prefix 221 | Bank accounts |
| Cash | prefix 211 | Cash accounts |
| Transfer | 261 | Internal transfers |
| FX Gain | chart_sk_663000 | Currency gains |
| FX Loss | chart_sk_563000 | Currency losses |
| Cash Diff. | chart_sk_668000 / chart_sk_568000 | Rounding |
| Early Pay Loss | chart_sk_546000 | Supplier discounts |
| Early Pay Gain | chart_sk_646000 | Customer discounts |
| Suspense | chart_sk_261000 | Journal suspense |

## Tax Structure
- `vy_tuz_23` — Slovak domestic sales VAT 23%
- `vs_tuz_23` — purchase VAT counterpart

Tax report: Slovak DPH (VAT) return via standard engine. Slovak SAF-T format supported.

## Fiscal Positions
Standard EU fiscal positions for Slovakia — B2B intra-community, B2C, export/import.

## EDI/Fiscal Reporting
Slovak SAF-T (xml export) via standard Odoo tax report engine.

## Installation
`auto_install: ['account']`

## Historical Notes

**Odoo 17 → 18 changes:**
- Version 1.0; chart template structured for 2020 Slovak accounting plan
- Storno accounting is standard for Slovak compliance
- Trade registry and income tax ID fields are helpful for Slovak invoice layout
- Company document layout integration (BaseDocumentLayout) is a newer pattern

**Performance Notes:**
- 6-digit chart is moderate size
- No post-init hooks; standard template loading