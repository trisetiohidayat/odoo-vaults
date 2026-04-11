---
Module: l10n_sa
Version: 2.0
Type: l10n/saudi
Tags: #odoo18 #l10n #accounting #saudi #gcc
---

# l10n_sa

## Overview
Saudi Arabia full accounting localization — chart of accounts, 15% VAT tax structure, VAT filing report, withholding tax report, fiscal positions, and ZATCA-compliant e-invoice QR code generation. This is the core Saudi localization module required for any Saudi company using Odoo accounting.

See also: [[Modules/l10n_sa_pos]] (POS), [[Modules/l10n_gcc_invoice]] (bilingual invoice)

## Country
Kingdom of Saudi Arabia (KSA) — country code `sa`

## Dependencies
- l10n_gcc_invoice
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'sa'`.

Sets standard receivable (`sa_account_102011`), payable (`sa_account_201002`), expense (`sa_account_400001`), income (`sa_account_500001`), `code_digits: 6`.

`_get_sa_res_company()` sets fiscal country to SA, bank/cash/transfer prefixes, default sale tax at 15% (`sa_sales_tax_15`), purchase tax at 15%, deferred expense and deferred revenue accounts.

`_get_sa_account_journal()` adds three special journals: `TA` (Tax Adjustments), `IFRS` (IFRS 16 Right of Use Asset), and `ZAKAT` (Zakat journal).

### `AccountMove` (`account.move`)
Inherits `account.move`. Adds:
- `l10n_sa_qr_code_str` — `Char`, ZATCA-compliant base64-encoded QR code for POSIX-compliant QR generation (see ZATCA specification page 23)
- `l10n_sa_confirmation_datetime` — `Datetime`, set when invoice is posted; represents the date invoice becomes a legal final document

`_compute_show_delivery_date()` — extends account module: forces `show_delivery_date = True` for Saudi sale documents.

`_compute_qr_code_str()` — generates ZATCA QR code using seller name (tag 1), VAT number (tag 2), timestamp in Asia/Riyadh timezone (tag 3), invoice total (tag 4), VAT total (tag 5). Uses TLV encoding with 1-byte tag + 1-byte length + value.

`_post()` — sets `l10n_sa_confirmation_datetime` and `delivery_date` on first post for Saudi sale documents.

`get_l10n_sa_confirmation_datetime_sa_tz()` — formats confirmation datetime in Riyadh timezone.

`_l10n_sa_reset_confirmation_datetime()` — clears confirmation datetime (called on `button_draft`).

`_l10n_sa_is_legal()` — returns True if company is SA, move is posted, and QR code is set (legal invoice check).

`_get_l10n_sa_totals()` — returns `total_amount` and `total_tax` from signed amounts.

### `IrAttachment` (`ir.attachment`)
Inherits `ir.attachment`. Overrides `_unlink_except_posted_pdf_invoices()` — prevents deletion of PDF reports linked to posted Saudi invoices (ZATCA compliance requirement).

## Data Files
- `data/account_data.xml` — chart of accounts data
- `data/account_tax_report_data.xml` — VAT filing report with lines for standard rated 15%, special sales, zero-rated, exports, exempt, reverse charge, and import bases and taxes
- `data/report_paperformat_data.xml` — report paper format customizations
- `views/report_invoice.xml` — invoice report view extensions
- `views/report_templates_views.xml` — report template customizations
- `demo/demo_company.xml` — Saudi demo company

## Chart of Accounts
6-digit chart with `sa_account_` prefix. Similar structure to UAE. Includes dedicated deferred expense (`sa_account_104020`) and deferred revenue (`sa_account_201018`) accounts for IFRS 16 lease accounting.

## Tax Structure
VAT at 15% standard rate (effective 1 July 2020). Standard, special (reduced), zero-rated, exempt, and export categories. Withholding tax report for specific service categories.

## Fiscal Positions
Defined in tax report data.

## EDI/Fiscal Reporting
No EDI submission module (unlike Egypt). ZATCA Phase 2 compliance handled via QR code on invoice PDF. QR code contains: seller name, VAT number, timestamp, invoice total, VAT total. ZATCA API submission (Phase 2) would require a separate EDI module not yet in core.

## Installation
`auto_install: ['account']` — automatically installed with account when Saudi Arabia is selected.

## Historical Notes
- Version 2.0 in Odoo 18 (co-authored with DVIT.ME)
- ZATCA QR code implementation follows spec: `https://zatca.gov.sa/ar/E-Invoicing/SystemsDevelopers/Documents/20210528_ZATCA_Electronic_Invoice_Security_Features_Implementation_Standards_vShared.pdf`
- 15% VAT rate (increased from 5% in July 2020)
- Confirmation datetime tracks when invoice becomes a legal document — important for ZATCA's "secure timestamps" requirement
