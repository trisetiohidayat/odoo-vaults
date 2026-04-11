---
Module: l10n_vn
Version: 18.0
Type: l10n/vietnam
Tags: #odoo18 #l10n #accounting #qr-codes
---

# l10n_vn

## Overview
Vietnam accounting localization providing the Vietnamese chart of accounts based on Circular No. 200/2014/TT-BTC, VAT structure, VietQR payment code generation, and e-invoice number tracking. Contributed by General Solutions and Trobz. Vietnam uses 4-digit account codes under VAS (Vietnamese Accounting Standards) and supports VietQR for payment.

## Country
Vietnam

## Dependencies
- [[Core/BaseModel]] (account)
- `account` — core accounting module
- `account_qr_code_emv` — EMV QR code generation for VietQR
- `base_iban` — IBAN/bank account support

## Key Models

### AccountChartTemplate (`account.chart.template`, classic extension)
- `_get_vn_template_data()` — sets 4-digit account codes: receivable `chart1311`, payable `chart3311`, expense `chart1561`, income `chart5111`, stock valuation `chart1551`; enables `display_invoice_amount_total_words`
- `_get_vn_res_company()` — enables `anglo_saxon_accounting`, fiscal country `base.vn`, bank prefix `112`, cash prefix `111`, transfer prefix `113`, transfer account `chart1131`, sale tax `tax_sale_vat10`, purchase tax `tax_purchase_vat10`, currency exchange gain `chart515`, loss `chart635`, deferred expense `chart2421`, deferred revenue `chart33871`, production WIP `chart1542`, cash diff income `chart711`, expense `chart811`

### AccountMove (`account.move`, classic extension)
- `l10n_vn_e_invoice_number` — Char field: stores Vietnam e-invoice number (electronic invoicing number from VN e-invoice portal); `copy=False`

### ResPartnerBank (`res.partner.bank`, classic extension)
Extends for **VietQR** (Vietnamese QR payment standard):
- `proxy_type` selection adds `merchant_id` (Merchant ID), `payment_service` (Payment Service), `atm_card` (ATM Card Number), `bank_acc` (Bank Account)
- `_check_vn_proxy()` — validates proxy type for VN banks
- `_compute_display_qr_setting()` — enables QR display always for VN banks
- `_get_merchant_account_info()` — returns GIRO tag 38 with VietQR GUID `A000000727`, payment network (bank BIC + proxy value), and proxy type (`QRPUSH` for merchant_id/payment_service, `QRIBFTTC` for atm_card, `QRIBFTTA` for bank_acc)
- `_get_additional_data_field()` — sanitizes comment for VietQR (removes invalid characters)
- `_get_qr_code_vals_list()` — overrides tag 60 to merchant city (up to 15 chars, no accents)
- `_get_error_messages_for_qr()` — validates: currency is VND; `bank_bic` is configured; city or state is set on partner
- `_check_for_qr_code_errors()` — validates merchant city/state, proxy type, proxy value, and merchant account info

## Data Files
- `data/account_tax_report_data.xml` — **Vietnam Tax Report**: two main sections — (1) Sales of Goods and Services (VAT 0/5/8/10%, exempt), (2) Purchase of Goods and Services (including imports). Uses both balance and amount_untaxed columns
- `data/template/account.account-vn.csv` — chart of accounts based on Circular 200
- `data/template/account.tax-vn.csv` — tax definitions including VAT 0/5/8/10%, exempt, and import taxes
- `data/template/account.tax.group-vn.csv` — tax groups
- `views/account_move_views.xml` — invoice form with e-invoice number field
- `views/res_bank_views.xml` — bank form with VietQR proxy fields
- `tests/test_l10n_vn_emv_qr.py` — QR code test suite
- `migrations/17.0.2.0.2/post-migration.py`, `14.0.2.0.1/post-migration.py`, `2.0.3/end-migrate_update_taxes.py` — migration scripts
- `demo/demo_company.xml` — demo company data

## Chart of Accounts
4-digit account codes based on **Circular No. 200/2014/TT-BTC**:
- `111` — Cash (cash `1111`, bank `1112`, transfer `1113`)
- `112` — Cash equivalents / Bank (`112`, `1131` transfer)
- `131` / `chart1311` — Accounts Receivable
- `133` — Input VAT (`1331` recoverable)
- `155` / `chart1551` — Inventory
- `156` / `chart1561` — Cost of Goods Sold
- `242` / `chart2421` — Prepaid Expenses (deferred expense)
- `333` — VAT payable (`33311`)
- `338` / `chart33871` — Deferred Revenue
- `511` / `chart5111` — Sales Revenue
- `515` / `chart515` — Financial income (currency gain)
- `635` / `chart635` — Financial expenses (currency loss)
- `711` / `chart711` — Cash difference income
- `811` / `chart811` — Cash difference expense

## Tax Structure
Vietnam uses **VAT (Value Added Tax — Thuế Giá Trị Gia Tăng)**:
| Tax ID | Rate | Type |
|--------|------|------|
| `tax_sale_vat10` | 10% | sale |
| `tax_purchase_vat10` | 10% | purchase |
| `tax_sale_vat8` | 8% | sale |
| `tax_purchase_vat8` | 8% | purchase |
| `tax_sale_vat5` | 5% | sale |
| `tax_purchase_vat5` | 5% | purchase |
| `tax_sale_vat0` | 0% | sale (zero-rated) |
| `tax_purchase_vat0` | 0% | purchase |
| `tax_sale_vat_exemption` | 0% | sale (exempt) |
| `tax_purchase_vat_exemption` | 0% | purchase (exempt) |
| `tax_purchase_import_10/8/5/0` | 10/8/5/0% | purchase (imported goods) |

Standard rate: **10%** (previously 10% standard, 5% reduced, 0% zero-rated/exempt)

## Fiscal Positions
None explicitly defined in the template module.

## EDI/Fiscal Reporting
- Vietnam Tax Report via `account_tax_report_data.xml` with tax by rate categories and import taxes
- VietQR code generation for domestic QR payments (VND currency)
- `l10n_vn_e_invoice_number` field on `account.move` tracks the government e-invoice number
- No dedicated Peppol EDI module for Vietnam in Odoo 18

## Installation
Install via Apps or during company setup by selecting Vietnam as country. Auto-installs with `account`. Multiple migrations handle upgrades from Odoo 14 and 17.

## Historical Notes
- Version 2.0.3: Latest Odoo 18 version.
- Vietnamese Accounting Standards (VAS) per Circular 200/2014/TT-BTC — the chart of accounts is structured accordingly.
- VietQR is Vietnam's national QR payment standard launched 2020 by the State Bank of Vietnam (SBV).
- VietQR supports multiple proxy types: Merchant ID, ATM card, Bank Account, E-wallet.
- The `l10n_vn_e_invoice_number` field tracks Vietnam's electronic invoice numbers from the VN e-invoice portal (e-invoicing is mandatory for large taxpayers).
- Credit for VietQR: Jean Nguyen — The Bean Family (https://github.com/anhjean/vietqr).
- Currency must be VND for VietQR generation; bank BIC code is required.
