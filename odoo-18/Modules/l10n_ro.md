---
Module: l10n_ro
Version: 18.0
Type: l10n/ro
Tags: #odoo18 #l10n #accounting
---

# l10n_ro

## Overview
Romania accounting localization. Provides Romanian chart of accounts (PCG — Planul de Conturi General), tax structure, fiscal positions, bank data, and partner NRC registration. Uses Storno accounting and 6-digit PCG codes. Includes JPK (SAF-T) support. Authored by Fekete Mihai (NextERP Romania) and Odoo SA.

## Country
Romania

## Dependencies
- account
- base_vat

## Key Models

### ResPartner
`models/res_partner.py` — extends `res.partner`
- `nrc` (Char) — Registration Number at the Registry of Commerce (Numărul de Registru Comerțului)
- `_commercial_fields()` — extends to include `nrc` in commercial field propagation to contacts
- `_compute_company_registry()` — override: for Romanian partners (country_code `RO`) with valid VAT, sets `company_registry` to the VAT number (CUI — Codul Unic de Înregistrare), handling both standard RO VAT format and numeric-only old-format

### AccountChartTemplate
`models/template_ro.py`
- `_get_ro_template_data()` — code_digits=6, Storno accounting, receivable `ro_pcg_recv`, payable `pcg_4011`, income `ro_pcg_sale`, expense `ro_pcg_expense`
- `_get_ro_res_company()` — sets fiscal country Romania, bank prefix `5121`, cash `5311`, transfer `581`, suspense `pcg_5125`, FX accounts, early-pay discount accounts, default VAT (`tvac_21`, `tvad_21`)
- `_get_ro_reconcile_model()` — creates default bank reconciliation templates (supplier advance, customer advance, bank commission, interest, internal transfer, wages, pending settlements)

### ResCompany (in l10n_ro_efactura_synchronize)
`models/res_company.py`
- `l10n_ro_edi_anaf_imported_inv_journal_id` (Many2one `account.journal`) — purchase journal used for SPV-imported vendor bills
- `_compute_l10n_ro_edi_anaf_imported_inv_journal()` — auto-selects purchase journal for RO companies

## Data Files
- `data/account_tax_report_data.xml` — Romanian VAT/CIF tax report (D390 / Declarația 390)
- `data/res.bank.csv` — Romanian bank registry
- `data/template/` — PCG chart of accounts CSV
- `views/res_partner_view.xml` — partner view with NRC field
- `demo/demo_company.xml`

## Chart of Accounts
6-digit Romanian PCG (Planul de Conturi General) codes. Storno accounting enabled.

| Account | Code | Purpose |
|---|---|---|
| Receivable | ro_pcg_recv | Customer AR |
| Payable | pcg_4011 | Supplier AP |
| Income | ro_pcg_sale | Sales revenue |
| Expense | ro_pcg_expense | COGS |
| Bank | prefix 5121 | Bank accounts |
| Cash | prefix 5311 | Cash accounts |
| Transfer | 581 | Internal transfers |
| Suspense | 5125 | Journal suspense |
| FX Gain | 7651 | Currency gains |
| FX Loss | 6651 | Currency losses |
| Bank Commission | 627 | Bank fees |
| Advances Supplier | 4094 | Supplier prepayments |
| Advances Customer | 419 | Customer prepayments |

## Tax Structure
- `tvac_21` — Romanian standard VAT 19% (inverted to 21% in code name)
- `tvad_21` — purchase VAT counterpart

Tax report: D390 (VAT Summary) via `account_tax_report_data.xml`, also JPK (SAF-T Romania).

## Fiscal Positions
Standard EU fiscal positions for Romania — intra-community B2B, export, import.

## EDI/Fiscal Reporting
Romania uses CIUS-RO (B2G) and e-Factura SPV for public procurement.
See `l10n_ro_edi` and `l10n_ro_efactura_synchronize`.

## Installation
`auto_install: ['account']`

## Historical Notes
**Odoo 17 → 18 changes:**
- Version 1.0; Romania localization significantly enhanced in recent versions
- Storno accounting explicitly enabled (required for Romanian legal compliance)
- JPK support expanded; D390 declaration linked to tax report engine
- NRC field on partner important for Romanian B2G invoicing

**Performance Notes:**
- PCG 6-digit chart is moderate size; Storno doubles journal entry storage
- No post-init hooks; template loading is standard
