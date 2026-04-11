---
Module: l10n_id
Version: 18.0
Type: l10n/indonesia
Tags: #odoo18 #l10n #accounting #indonesia
---

# l10n_id — Indonesian Accounting

## Overview
Indonesian accounting localization providing chart of accounts based on Indonesian Accounting Standards (Sak) and tax structure including PPN (Indonesian VAT / Pajak Pertambahan Nilai), PPnBM (Luxury Goods Sales Tax), and QRIS payment integration. Indonesia uses a multi-rate VAT system with a non-luxury goods variant.

Maintained by vitraining.com.

## Country
Indonesia

## Dependencies
- account
- base_iban
- base_vat

## Key Models

### `AccountMove` (`account.move`)
- `_inherit = 'account.move'`
- Adds `l10n_id_qris_transaction_ids` Many2many to `l10n_id.qris.transaction`
- Overrides `_generate_qr_code()` to pass QRIS model context for linking QR codes to invoices
- `_l10n_id_cron_update_payment_status()` — scheduled action (ir.cron) to poll QRIS payment status on unpaid invoices
- `_l10n_id_update_payment_status()` — fetches QR statuses and registers payments for paid invoices
- Overrides `_compute_tax_totals()` for non-luxury goods tax base adjustment effective January 2025: tax base displayed as 11/12 of original while tax amount increases from 11% to 12% (maintaining effective 11% tax amount)

### `QRISTransaction` (`l10n_id.qris.transaction`)
- `_name = 'l10n_id.qris.transaction'`
- Standalone model (not inheriting another) storing QRIS payment transaction details
- Fields: `model` (Char), `model_id` (Char), `qris_invoice_id`, `qris_amount` (Integer), `qris_content`, `qris_creation_datetime`, `bank_id` (Many2one res.partner.bank), `paid` (Boolean)
- `_get_supported_models()` — returns `['account.move']`
- `_constraint_model()` — validates model is in supported list
- `_get_record()` — resolves linked `account.move` from model/model_id
- `_get_latest_transaction(model, model_id)` — searches latest transaction
- `_l10n_id_get_qris_qr_statuses()` — polls bank API for payment status; returns paid/unpaid status
- `_gc_remove_pointless_qris_transactions()` — `@api.autovacuum` removes unpaid transactions older than 35 minutes

### `ResBank` (`res.partner.bank`)
- `_inherit = 'res.partner.bank'`
- Indonesian bank extensions for QRIS

### `AccountChartTemplate` (AbstractModel)
- `_inherit = 'account.chart.template'`
- 8-digit account codes (Indonesian chart uses longer codes)
- Property accounts: receivable (`l10n_id_11210010`), payable (`l10n_id_21100010`), expense (`l10n_id_51000010`), income (`l10n_id_41000010`), stock input/output (`l10n_id_29000000`), stock valuation (`l10n_id_11300180`)
- Company defaults: `anglo_saxon_accounting = True`, fiscal country `base.id`, bank prefix `1112`, cash prefix `1111`, transfer prefix `1999999`, POS receivable `l10n_id_11210011`, currency exchange accounts

## Data Files
- `security/ir.model.access.csv` — Access control for QRIS transaction model
- `data/account_tax_template_data.xml` — Indonesian tax templates (PPN 11%, PPnBM)
- `data/ir_cron.xml` — Scheduled action: `l10n_id.cron_update_qris_payment` for polling QRIS payments
- `views/account_move_views.xml` — QRIS button and payment status on invoices
- `views/res_bank.xml` — Bank form view for QRIS config
- `demo/demo_company.xml`

## Chart of Accounts
8-digit codes in Indonesian format. Account structure aligned with SAK (Standar Akuntansi Keuangan / Financial Accounting Standards issued by the Indonesian Institute of Accountants).

- 1xxx: Assets (l10n_id_11210010 Receivables, l10n_id_11300180 Inventory)
- 2xxx: Liabilities
- 4xxx: Revenue
- 5xxx: Expenses

## Tax Structure
- **PPN (Pajak Pertambahan Nilai) 11%** — Standard VAT rate (increased from 10% effective April 2022)
- **PPnBM (Pajak Penjualan Barang Mewah)** — Luxury goods tax, additional layer on top of PPN
- **Non-Luxury Goods Special Rule (effective Jan 2025)**: Effective rate remains 11% (tax base 11/12 of amount, tax amount at 12% = original 11%)
- Tax rounding adjustments handled in `_compute_tax_totals()`

## Fiscal Positions
Standard Indonesian fiscal positions for inter-region transactions.

## QRIS Payment Integration
QRIS (QR Code Indonesian Standard) — national QR payment standard. Odoo:
1. Generates QRIS code on invoices via `_generate_qr_code()`
2. Records transaction via `l10n_id.qris.transaction`
3. Cron polls bank API every few minutes for payment status
4. Auto-registers payment when QRIS is scanned/paid

## Installation
Auto-installs with `account`. QRIS cron runs automatically. Requires bank configured with QRIS credentials.

## Historical Notes
Version 1.2 in Odoo 18. Major addition in this version: QRIS payment integration with automatic payment registration. Non-luxury goods tax base calculation adjusted for 2025 rate change. Prior versions (Odoo 14-17) had basic PPN accounting only. Author: vitraining.com.