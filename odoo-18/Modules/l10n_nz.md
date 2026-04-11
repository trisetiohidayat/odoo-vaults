---
Module: l10n_nz
Version: 18.0
Type: l10n/new-zealand
Tags: #odoo18 #l10n #accounting
---

# l10n_nz

## Overview
New Zealand accounting localization providing the NZ chart of accounts, GST structure, and IRD-compliant GST return reporting. Includes a custom invoice report layout, partner NZBN label, and supplier payment receipt naming.

## Country
New Zealand

## Dependencies
- [[Core/BaseModel]] (account)
- `account` — core accounting module

## Key Models

### AccountChartTemplate (`account.chart.template`, classic extension)
- `_get_nz_template_data()` — sets 5-digit account codes: receivable `nz_11200`, payable `nz_21200`, expense `nz_51110`, income `nz_41110`, stock input `nz_21210`, stock output `nz_11340`, stock valuation `nz_11330`, production cost `nz_11350`
- `_get_nz_res_company()` — enables `anglo_saxon_accounting`, fiscal country `base.nz`, bank prefix `1111`, cash prefix `1113`, transfer prefix `11170`, sale tax `nz_tax_sale_15`, purchase tax `nz_tax_purchase_15`; fiscal year ends March 31 (`fiscalyear_last_month: '3'`, `fiscalyear_last_day: 31`)

### AccountMove (`account.move`, classic extension)
- `_get_name_invoice_report()` — returns `l10n_nz.report_invoice_document` for NZ companies (custom invoice layout)

### AccountPayment (`account.payment`, classic extension)
- `_compute_payment_receipt_title()` — for NZ + supplier payment, overrides receipt title to `Remittance Advice`

### ResPartner (`res.partner`, classic extension)
- `_get_company_registry_labels()` — for NZ partners, displays label as `NZBN` (New Zealand Business Number)

## Data Files
- `data/account_tax_report_data.xml` — **GST Return** report (IRD standard layout). Two main sections: Sales and Income (BOX 5–10) and Purchases and Expenses (BOX 11–15). BOX 10 = GST collected, BOX 14 = GST credit, BOX 15 = Net GST (BOX 10 − BOX 14)
- `data/res_currency_data.xml` — activates regional currencies
- `data/res_company_views.xml` — company form views
- `data/res_partner_views.xml` — partner form views with NZBN
- `views/report_invoice.xml` — custom invoice report for NZ
- `migrations/1.2/pre-migrate.py` and `post-migrate.py` — v1.2 migration hooks
- `demo/demo_company.xml` — demo company data

## Chart of Accounts
5-digit account codes:
- `112xx` — Current Assets (receivable `11200`, POS receivable `11220`, stock output `11340`, stock valuation `11330`)
- `212xx` — Current Liabilities (payable `21200`, stock input `21210`)
- `411xx` — Revenue (`41110`)
- `511xx` — Expenses (`51110`)
- `616xx` — Other expenses/income (currency exchange `61630`, early pay discount loss `61610`, gain `61620`)

## Tax Structure
**GST (Goods and Services Tax) at 15%:**
- `nz_tax_sale_15` — 15% sale GST (default sale tax)
- `nz_tax_purchase_15` — 15% purchase GST (default purchase tax)
- Tax groups and tags map to IRD BOX system for GST return filing

GST Return BOX system:
- BOX 5: Total sales including GST; BOX 6: Zero-rated supplies; BOX 7: Taxable supplies (BOX5−BOX6); BOX 8: GST collected (BOX7×3/23)
- BOX 11: Total purchases with tax invoices; BOX 12: GST credit (BOX11×3/23); BOX 13: Adjustments
- BOX 15: Net GST = BOX 10 − BOX 14

## Fiscal Positions
None explicitly defined.

## EDI/Fiscal Reporting
- IRD-compliant GST Return report using the BOX system
- Custom invoice report layout for New Zealand
- NZBN (New Zealand Business Number) displayed on partner form

## Installation
Install via Apps or during company setup by selecting New Zealand as country. Auto-installs with `account`. Version 1.2 migration hooks handle v1.1 → v1.2 upgrade.

## Historical Notes
- Version 1.2: Includes pre/post migration scripts for v1.2.
- New Zealand uses 15% GST (introduced 1989, increased from 12.5% in 2010).
- Fiscal year typically April–March (matches standard Odoo setting here).
- Remittance Advice naming for supplier payments (NZ convention).
- Anglo-Saxon accounting enabled for inventory costing.
