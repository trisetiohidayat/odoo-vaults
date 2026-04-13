---
Module: l10n_tr
Version: 18.0
Type: l10n/turkiye
Tags: #odoo18 #l10n #accounting
---

# l10n_tr

## Overview
Türkiye (Turkey) accounting localization providing the Turkish chart of accounts, VAT structure, and sales return account automation. Contributed by Drysharks Consulting. Turkey uses 6-digit account codes aligned with the Turkish Uniform Chart of Accounts (TÜRMOB). Includes country-specific journal and product sales return account defaults.

## Country
Türkiye (Turkey)

## Dependencies
- [Core/BaseModel](odoo-18/Core/BaseModel.md) (account)
- `account` — core accounting module

## Key Models

### AccountChartTemplate (`account.chart.template`, classic extension)
- `_get_tr_template_data()` — sets 6-digit account codes: receivable `tr120`, payable `tr320`, expense `tr150`, income `tr600`
- `_get_tr_res_company()` — fiscal country `base.tr`, bank prefix `102`, cash prefix `100`, transfer prefix `103`, suspense `tr102999`, sale tax `tr_s_20`, purchase tax `tr_p_20`, currency exchange gain `tr646`, loss `tr656`

### AccountJournal (`account.journal`, classic extension)
- `l10n_tr_default_sales_return_account_id` — Many2one to `account.account`; computed for Turkish sale journals; defaults to `tr610` (Sales Returns account)
- `_compute_l10n_tr_default_sales_return_account_id()` — for `type='sale'` + `country_code='TR'`, looks up `tr610` via chart template

### AccountMoveLine (`account.move.line`, classic extension)
- `_compute_account_id()` — OVERRIDE: for Turkish companies with `move_type='out_refund'` and `display_type='product'`, routes to `product.l10n_tr_default_sales_return_account_id` if set, else `journal.l10n_tr_default_sales_return_account_id`; this overrides the default income account on sales returns

### ProductTemplate (`product.template`, classic extension)
- `l10n_tr_default_sales_return_account_id` — company-dependent Many2one; set on product creation for Turkish companies via `tr610`
- `create()` — overrides to auto-set `l10n_tr_default_sales_return_account_id` to `tr610` for new products created under a Turkish company

## Data Files
- `data/account_tax_report_data.xml` — **Türkiye Tax Report**: sections for Purchases VAT (base + tax columns) and Sales VAT; uses Turkish tax tag names; auto-sequence enabled
- `migrations/1.1/end-migrate_update_taxes.py` — tax updates from v1.0 to v1.1
- `migrations/1.3/end-migrate_update_taxes.py` — tax updates from v1.2 to v1.3
- `migrations/1.2/end-migrate_update_package.py` — package rename migration (Türkiye renamed from Turkey)
- `demo/demo_company.xml` — demo company data

## Chart of Accounts
6-digit account codes (Turkish Uniform Chart):
- `tr120` — Receivables (Trade Receivables)
- `tr320` — Payables (Trade Payables)
- `tr150` — Inventory/Purchases
- `tr600` — Sales Revenue
- `tr610` — Sales Returns and Allowances (mapped by default for out_refund)
- `tr102xxx` — Bank accounts (suspense: `tr102999`)
- `tr100` — Cash
- `tr103` — Transfer accounts
- `tr646` — Currency exchange gain
- `tr656` — Currency exchange loss

## Tax Structure
Turkey uses **VAT (Katma Değer Vergisi — KDV)**:
- Default sale tax: `tr_s_20` (20% — standard rate)
- Default purchase tax: `tr_p_20` (20% — standard rate)
- Reduced rates exist (1%, 8%) for specific goods/services
- Tax report structured by purchases and sales sections with base and tax amount columns

## Fiscal Positions
None explicitly defined in the template module.

## EDI/Fiscal Reporting
- Türkiye Tax Report via `account_tax_report_data.xml`
- No dedicated EDI module for Turkey in Odoo 18 (Peppol network participation varies)

## Installation
Install via Apps or during company setup by selecting Turkey/Türkiye as country. Auto-installs with `account`. Three migration scripts handle tax updates across v1.0, v1.1, v1.2, and v1.3.

## Historical Notes
- Version 1.3: Latest Odoo 18 version.
- Package renamed from `l10n_tr` in v1.2 migration (`end-migrate_update_package`) to reflect official country name change from "Turkey" to "Türkiye" (UN + ISO adopted 2022).
- Turkish VAT rates: 20% standard, 10% reduced (food, books, etc.), 8% reduced (some goods), 1% (newspapers, medical items).
- Sales return accounts (`tr610`) are separate from revenue accounts — the `_compute_account_id` override routes `out_refund` lines to return accounts automatically.
- The product-level `l10n_tr_default_sales_return_account_id` allows per-product return account customization.
- Turkey is not on the Peppol network as of Odoo 18 (e-invoicing is via separate channels: Gib (Turkish e-Invoice Network)).
