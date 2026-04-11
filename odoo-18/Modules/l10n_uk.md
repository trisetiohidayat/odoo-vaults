---
Module: l10n_uk
Version: 18.0
Type: l10n/uk
Tags: #odoo18 #l10n #accounting
---

# l10n_uk

## Overview
United Kingdom accounting localization. Provides UK chart of accounts (CT600-ready), VAT structure (VAT100), UK county data, and Northern Ireland-specific fiscal positions activated on install based on company state. Authored by SmartMode LTD.

## Country
[[Modules/Account|United Kingdom]] 🇬🇧 (non-EU post-Brexit)

## Dependencies
- [[Core/BaseModel|account]]
- base_iban
- base_vat

## Key Models

### AccountChartTemplate
`models/template_uk.py`
- `_get_uk_template_data()` — 6-digit codes, receivable `1100`, payable `2100`, income `4000`, expense `5000`
- `_get_uk_res_company()` — sets `anglo_saxon_accounting=True`, fiscal country UK, bank prefix `1200`, cash `1210`, transfer `1220`, POS receivable `1104`, FX accounts, deferred expense/revenue accounts, default VAT (`ST11` standard, `PT_20_G` purchase)
- `_post_load_data('uk', company)` — post-install hook: checks if company state is in Northern Ireland (states uk18-uk24), and if so, activates:
  - `PT8` / `ST4` — reduced-rate Northern Ireland VAT taxes
  - `PT7` — zero-rate NI VAT
  - `account_fiscal_position_ni_to_eu_b2b` — fiscal position for Northern Ireland B2B EU transactions (post-Brexit special rules)

## Data Files
- `data/l10n_uk_chart_data.xml` — UK-specific chart of accounts data
- `data/account_tax_report_data.xml` — UK VAT100 / VAT return structure
- `data/template/` — chart of accounts CSV
- `demo/l10n_uk_demo.xml` — UK-specific demo data
- `demo/demo_company.xml`

## Chart of Accounts
6-digit UK account codes for CT600 (corporation tax) filing.

| Account | Code | Purpose |
|---|---|---|
| Receivable | 1100 | Customer AR |
| Payable | 2100 | Supplier AP |
| Income | 4000 | Sales revenue |
| Expense | 5000 | COGS |
| Bank | prefix 1200 | Bank accounts |
| Cash | prefix 1210 | Cash accounts |
| Transfer | 1220 | Internal transfers |
| FX | 7700 | Currency exchange |
| Deferred Expense | 1103 | Prepayments |
| Deferred Revenue | 2109 | Deferred income |

## Tax Structure
- `ST11` — UK standard rate VAT (20%)
- `PT_20_G` — purchase VAT (20%)
- Northern Ireland: `PT8` (reduced 5%), `ST4` (reduced 5%), `PT7` (zero rate for EU goods)

UK VAT return: VAT100 via `account_tax_report_data.xml`.

## Fiscal Positions
Standard UK fiscal positions. Northern Ireland has special EU intra-community trade rules post-Brexit:
- `account_fiscal_position_ni_to_eu_b2b` — activates automatically for NI companies on chart install

## EDI/Fiscal Reporting
UK Making Tax Digital (MTD) compatible via standard Odoo reporting.
Peppol supported for e-invoicing.

## Installation
`auto_install: ['account']`

## Historical Notes

**Odoo 17 → 18 changes:**
- Version 1.1; UK localization restructured for post-Brexit requirements
- Northern Ireland fiscal positions (PT8, ST4, PT7, NI B2B fiscal position) are a significant post-Brexit addition
- `_post_load_data` hook for auto-activating NI-specific taxes and fiscal positions based on company state is a newer pattern
- CT600-ready chart format ensures compatibility with UK corporation tax reporting

**Performance Notes:**
- NI state detection uses external IDs — fast, no database overhead
- Chart is compact; fast installation