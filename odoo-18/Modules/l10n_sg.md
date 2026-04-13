---
Module: l10n_sg
Version: 18.0
Type: l10n/singapore
Tags: #odoo18 #l10n #accounting #qr-codes
---

# l10n_sg

## Overview
Singapore accounting localization providing the Singapore Chart of Accounts, GST structure, and PayNow QR code generation. Authored by Tech Receptives. Singapore uses 6-digit account codes and 9% GST (as of 2024). The module adds UEN fields to company/partner for IRAS compliance and includes a custom invoice report with permit number fields.

## Country
Singapore

## Dependencies
- [Core/BaseModel](core/basemodel.md) (account)
- `account_qr_code_emv` — EMV QR code generation for PayNow QR

## Key Models

### AccountChartTemplate (`account.chart.template`, classic extension)
- `_get_sg_template_data()` — sets 6-digit account codes: receivable `account_account_735`, payable `account_account_777`, expense `account_account_819`, income `account_account_803`
- `_get_sg_res_company()` — fiscal country `base.sg`, bank prefix `10141`, cash prefix `10140`, transfer prefix `101100`, POS receivable `account_account_737`, sale tax `sg_sale_tax_sr_9`, purchase tax `sg_purchase_tax_tx8_9`, early pay discount loss `account_account_800`, gain `account_account_856`
- `_preserve_tag_on_taxes()` — post-init hook that preserves tax tags on existing taxes

### AccountMove (`account.move`, classic extension)
- `l10n_sg_permit_number` — Char field: Permit Number for customs/trade invoices
- `l10n_sg_permit_number_date` — Date field: Date of permit number

### ResCompany (`res.company`, classic extension)
- `l10n_sg_unique_entity_number` — related field to partner's UEN; `_get_view()` overrides VAT label dynamically using `company_vat_label`

### ResPartner (`res.partner`, classic extension)
- `l10n_sg_unique_entity_number` — **UEN (Unique Entity Number)** field; `_deduce_country_code()` returns `'SG'` if UEN is set; `_peppol_eas_endpoint_depends()` includes UEN for Peppol endpoint resolution

### ResPartnerBank (`res.partner.bank`, classic extension)
Extends for **PayNow QR**:
- `proxy_type` selection adds `mobile` (Mobile Number) and `uen` (UEN)
- `_check_sg_proxy()` — validates proxy type for SG banks
- `_compute_display_qr_setting()` — enables QR display always for SG banks
- `_get_merchant_account_info()` — returns GIRO tag 26 with SG.PAYNOW GUID, proxy type (0=mobile, 2=UEN), proxy value, editable flag
- `_get_additional_data_field()` — serializes QR comment
- `_get_error_messages_for_qr()` — validates currency is SGD only
- `_check_for_qr_code_errors()` — enforces mobile or UEN proxy type

## Data Files
- `data/l10n_sg_chart_data.xml` — account data and SG menu item `account_reports_sg_statements_menu`
- `data/account_tax_report_data.xml` — **Singapore GST Return** report: Boxes 1–9 (Supplies, Purchases, Taxes) and Import Deferment Scheme (Boxes 18–21)
- `data/template/account.account-sg.csv` — chart of accounts
- `data/template/account.tax-sg.csv` — tax definitions with GST categories
- `data/template/account.tax.group-sg.csv` — tax groups
- `views/account_invoice_view.xml` — invoice form with permit number fields
- `views/res_bank_views.xml` — bank form with PayNow proxy type
- `views/res_company_view.xml` — company form with UEN
- `migrations/2.1/end-migrate_update_tax.py`, `migrations/2.2/end-migrate_update_taxes.py` — tax migrations
- `tests/test_l10n_sg_emv_qr.py` — QR code test suite
- `demo/demo_company.xml` — demo company data

## Chart of Accounts
6-digit account codes:
- `101xxx` — Bank (`10141` prefix), Cash (`10140`), Transfer (`101100`)
- `account_account_735/737` — Receivables
- `account_account_777` — Payables
- `account_account_803` — Income
- `account_account_819` — Expenses/COGS
- `account_account_800` — Early pay discount loss
- `account_account_853` — Currency exchange gain/loss
- `account_account_856` — Early pay discount gain
- `account_account_791` — GST tax account

## Tax Structure
Singapore GST (Goods and Services Tax):
- Default: 9% (increased from 8% on 1 Jan 2024, from 7% on 1 Jan 2023)
- `sg_sale_tax_sr_9` — 9% Standard-Rated supply (default, active)
- `sg_sale_tax_sr_8` — 8% (inactive, prior rate)
- `sg_purchase_tax_tx8_9` — 9% purchase tax (default, active)
- Tax groups: `tax_group_8`, `tax_group_9`, `tax_group_7`, `tax_group_deemed`, `tax_group_exempt`, `tax_group_0`, `tax_group_oos`
- Tax categories (mapped to GST report boxes): SR (Standard-Rated), ZR (Zero-Rated), ES33 (Regulation 33 Exempt), DS (Deemed), OS (Out-of-Scope), NG (Not Registered), NA (Not Applicable)

GST Return Box structure:
- Box 1: Standard-rated supplies; Box 2: Zero-rated; Box 3: Exempt; Box 4: Total
- Box 5: Taxable purchases; Box 6: Output tax due; Box 7: Input tax/refund; Box 8: Net GST to IRAS
- Boxes 9–12: Special schemes (Tourist Refund, Reverse Charge, Pre-registration); Boxes 13–17: Revenue
- Boxes 18–21: Import GST Deferment Scheme

## Fiscal Positions
None explicitly defined in this module.

## EDI/Fiscal Reporting
- IRAS GST Return report (9-box format, extended with import deferment)
- PayNow QR codes (SGD only, via mobile number or UEN proxy)
- UEN on partners enables Peppol endpoint resolution
- Companion module [Modules/l10n_sg_ubl_pint](modules/l10n_sg_ubl_pint.md) for Peppol PINT SG e-invoicing

## Installation
Install via Apps or during company setup by selecting Singapore as country. Post-init hook preserves tax tags on existing taxes. Auto-installs with `account`.

## Historical Notes
- Version 2.2: Latest Odoo 18 version; version history shows progression from 2.0 through 2.2.
- Singapore GST rate has been increasing: 7% (until 2022) → 8% (2023) → 9% (2024). The module includes both active (9%) and inactive (8%) tax rates.
- PayNow is Singapore's national peer-to-peer payment service, enabling QR-based payments linked to NRIC/UEN or mobile number.
- UEN (Unique Entity Number) is mandatory for all Singapore entities — it replaces TIN for business-to-government transactions.
- Post-init hook `_preserve_tag_on_taxes` ensures existing taxes retain proper IRAS mapping tags during upgrade.
