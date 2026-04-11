---
Module: l10n_pt
Version: 18.0
Type: l10n/pt
Tags: #odoo18 #l10n #accounting
---

# l10n_pt

## Overview
Portugal accounting localization. Provides Portuguese chart of accounts (Sistema de Normalização Contabilística — SNC), tax structure, and fiscal positions. Uses 3-digit account codes. Authored by Odoo SA.

## Country
Portugal

## Dependencies
- base
- account
- base_vat

## Key Models

### AccountAccount
`models/account_account.py` — extends `account.account`
- `l10n_pt_taxonomy_code` (Integer) — Portuguese account taxonomy code (used in official SAF-T export mapping)

### AccountChartTemplate
`models/template_pt.py`
- `_get_pt_template_data()` — sets Portuguese receivable `chart_2111`, payable `chart_2211`, income `chart_711`, expense `chart_311`
- `_get_pt_res_company()` — sets fiscal country Portugal, bank prefix `12`, cash `11`, transfer `1431`, POS receivable `chart_2117`, currency exchange accounts, early-pay discount accounts, default VAT taxes (`iva_pt_sale_normal`, `iva_pt_purchase_normal`)
- `_get_account_journal()` — override: assigns default cash account `chart_11` to cash journals, `chart_12` to bank journals (Portuguese accounting preference)

## Data Files
- `data/account_tax_report.xml` — Portuguese IRC/IVA tax report structure
- `data/template/` — SNC chart of accounts CSV
- `demo/demo_company.xml`

## Chart of Accounts
3-digit Portuguese SNC (Sistema de Normalização Contabilística) codes.

| Account | Code | Purpose |
|---|---|---|
| Receivable | chart_2111 | Customer AR |
| Payable | chart_2211 | Supplier AP |
| Income | chart_711 | Sales revenue |
| Expense | chart_311 | COGS |
| Bank | prefix 12 | Bank accounts |
| Cash | prefix 11 | Cash accounts |
| Transfer | 1431 | Internal transfers |
| FX Gain | chart_7861 | Currency gains |
| FX Loss | chart_6863 | Currency losses |
| Early Pay Discount Loss | chart_682 | Supplier discounts |
| Early Pay Discount Gain | chart_728 | Customer discounts |

## Tax Structure
- `iva_pt_sale_normal` — Portuguese standard rate IVA (23%)
- `iva_pt_purchase_normal` — purchase IVA counterpart

Tax report: IVA (VAT) declaration via SAF-T format defined in `account_tax_report.xml`.

## Fiscal Positions
Standard: B2C national, B2B EU intra-community, export. Portuguese fiscal positions use SAFT-Taxonomy codes for compliance.

## EDI/Fiscal Reporting
SAF-T (PT) standard for e-filing. `l10n_pt_taxonomy_code` on accounts enables proper mapping.

## Installation
`auto_install: ['account']` — auto-installed with account.

## Historical Notes
**Odoo 17 → 18 changes:**
- Version 1.0; relatively unchanged
- Portuguese chart follows SNC 2005/2009 taxonomy; stable across Odoo versions
- Journal default accounts assignment (`_get_account_journal`) is a helpful simplification for Portuguese users

**Performance Notes:**
- 3-digit codes → compact, fast install
- No post-init hooks; straightforward template loading
