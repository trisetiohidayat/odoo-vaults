---
Module: l10n_kh
Version: 18.0
Type: l10n/cambodia
Tags: #odoo18 #l10n #accounting #withholding
---

# l10n_kh

## Overview
Cambodia accounting localization providing the Cambodian chart of accounts, VAT/sales tax, and withholding tax reporting. Depends on `account_qr_code_emv` for QR payments and `l10n_account_withholding_tax` for withholding tax support.

## Country
Cambodia

## Dependencies
- `account` — core accounting
- `account_qr_code_emv` — EMV QR code generation
- `l10n_account_withholding_tax` — withholding tax framework

## Key Models

### AccountChartTemplate (`account.chart.template`, classic extension)
- `_get_kh_template_data()` — sets 5-digit account codes: receivable `l10n_kh_account_10500`, payable `l10n_kh_account_20300`, expense `l10n_kh_account_50100`, income `l10n_kh_account_40100`, stock valuation `l10n_kh_account_10200`
- `_get_kh_res_company()` — sets fiscal country `base.kh`, bank prefix `1090`, cash prefix `1080`, transfer prefix `1100`, sale tax `l10n_kh_tax_sale_10_m_t`, purchase tax `l10n_kh_tax_purchase_10_m`
- `_get_kh_account_journal()` — bank journal default `l10n_kh_account_10900`, cash journal default `l10n_kh_account_10800`

### ResPartnerBank (`res.partner.bank`, classic extension)
Extends payment QR code generation for **KHQR** (Cambodia QR standard):
- `proxy_type` selection adds `bakong_id_solo` (Bakong Solo Merchant), `bakong_id_merchant` (Bakong Corporate Merchant)
- `l10n_kh_merchant_id` — Merchant ID field for Bakong corporate
- `_check_kh_proxy()` — validates Bakong ID format: must match `^[a-zA-Z0-9_].*@[a-zA-Z0-9_].*$`, max 32 chars
- `_get_qr_code_vals_list()` — adds KHQR timestamp and expiry tags
- `_get_merchant_account_info()` — returns GIRO tag 29 (solo) or tag 30 (merchant) with Bakong account data
- `_get_merchant_category_code()` — returns `0001`
- `_get_error_messages_for_qr()` — validates currency is KHR or USD only
- `_check_for_qr_code_errors()` — enforces Bakong Account ID as only valid proxy type

## Data Files
- `data/form_t7001.xml` — **Form T7001** (VAT Declaration): country-level tax report with Balance and Tax Amount columns. Sections include VAT and other tax categories with tax tag references
- `data/form_wt003.xml` — **Form WT003** (Withholding Tax Report): two sections — Withholding Tax on Resident (6 categories: service/royalty, interest from non-bank, interest from fixed deposit, interest from savings, rental/legal person, rental/physical person) and Withholding Tax on Non-Resident (5 categories: interest, royalty/rental, management/technical services, dividend, service)
- `data/res_bank_views.xml` — bank form view extensions for Bakong fields
- `demo/demo_company.xml` — demo company data

## Chart of Accounts
5-digit account codes. Key prefixes:
- `10xxx` — Current Assets (bank `1090xx`, cash `108xx`, stock `102xx`)
- `20xxx` — Current Liabilities (payable `203xx`)
- `40xxx` — Revenue/Income (`401xx`)
- `50xxx` — Expenses (`501xx`)

## Tax Structure
The default taxes are 10% sale and purchase:
- `l10n_kh_tax_sale_10_m_t` — 10% sale (tax-included mode, multi行)
- `l10n_kh_tax_purchase_10_m` — 10% purchase
- Withholding taxes via `l10n_account_withholding_tax` framework with Form WT003 report

## Fiscal Positions
None defined in this module.

## EDI/Fiscal Reporting
- Form T7001: VAT Declaration report
- Form WT003: Withholding Tax Report for both resident and non-resident payments
- KHQR code generation for payment via Bakong (Cambodia's interbank QR payment system)

## Installation
Install via Apps. Creates bank account QR codes compatible with Bakong/KHQR. The KHQR proxy type supports both individual (solo) and corporate merchant modes.

## Historical Notes
- Version 1.0 — initial Odoo 18 release.
- Bakong is Cambodia's national QR payment infrastructure operated by the National Bank of Cambodia.
- Supports KHR and USD currencies for QR payments (both widely used in Cambodia).
