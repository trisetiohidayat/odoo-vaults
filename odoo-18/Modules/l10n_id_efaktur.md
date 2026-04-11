---
Module: l10n_id_efaktur
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #indonesia #efaktur
---

# l10n_id_efaktur

## Overview
Generates and manages Indonesian e-Faktur (electronic tax invoice) CSV exports for customer invoices. Assigns tax numbers from configured ranges, generates the FK/LT/OF CSV format required by DJP (Direktorat Jenderal Pajak), and manages replacement invoices and resets. Works with `l10n_id`.

## EDI Format / Standard
Indonesian e-Faktur CSV (pre-Coretax, legacy format). Format code: `010.000-16.00000001`
- 2 digits: Kode Transaksi (transaction code)
- 1 digit: Kode Status (FG_PENGGANTI: 0=normal, 1=replacement)
- 3 digits: Kode Cabang (branch code)
- 2 digits: tahun Penerbitan (year)
- 8 digits: Nomor Urut (sequential number)

## Dependencies
- `l10n_id` -- Indonesian localization base

## Key Models

### `account.move` (`l10n_id_efaktur.account_move`)
Extends: `account.move`

Fields:
- `l10n_id_tax_number` -- Char (16-digit tax number, copyable)
- `l10n_id_replace_invoice_id` -- Many2one to replaced invoice
- `l10n_id_efaktur_document` -- Many2one to `l10n_id_efaktur.document`
- `l10n_id_kode_transaksi` -- Selection `01`–`09` (computed from partner, stored); determines first 2 digits of tax number
- `l10n_id_efaktur_range` -- Many2one to `l10n_id_efaktur.efaktur.range`
- `l10n_id_need_kode_transaksi` / `l10n_id_available_range_count` / `l10n_id_show_kode_transaksi` -- Computed visibility fields

Key methods:
- `_post()` -- After validation, if partner is PKP and has kode_transaksi, assigns tax number from range; handles replacement numbering
- `_constrains_l10n_id_tax_number()` -- Validates: 16 digits, valid kode_transaksi prefix, FG_PENGGANTI digit (0 or 1)
- `reset_efaktur()` -- Returns tax number to the range pool; clears document link
- `download_csv()` / `download_efaktur()` -- Creates `l10n_id_efaktur.document` and triggers generation
- `_prepare_etax()` -- Returns empty ETax dict (overridden by coretax for XML)
- `button_draft()` -- Unlinks from e-faktur document when reset to draft

### `l10n_id_efaktur.document` (`l10n_id_efaktur.efaktur_document`)
Stands alone: no `_inherit`.

Inherits `mail.thread` and `mail.activity.mixin`.

Fields:
- `name` -- Computed from invoice names (auto-set at creation)
- `company_id`, `active` -- Standard
- `invoice_ids` -- One2many to `account.move`
- `attachment_id` -- Many2one to `ir.attachment` (generated CSV)

Key methods:
- `_generate_csv()` -- Builds CSV with FK, LT, OF sections; handles downpayment lines, free products, rounding adjustments
- `_generate_efaktur_invoice()` -- Returns CSV string; called by `_generate_csv()`
- `action_download()` -- Triggers generation if needed; returns attachment download URL
- `action_regenerate()` -- Re-generates CSV and attachment

### `res.partner` (`l10n_id_efaktur.res_partner`)
Extends: `res.partner`

Fields (from parent `l10n_id`): `l10n_id_nik`, `l10n_id_pkp`, `l10n_id_kode_transaksi`.

## Data Files
- `security/ir.model.access.csv`, `security/ir_rule.xml` -- ACL and record rules
- `views/account_move_views.xml`, `views/efaktur_document_views.xml`, `views/efaktur_views.xml`, `views/res_partner_views.xml`, `views/res_config_settings_views.xml` -- UI

## How It Works
1. Customer invoice posted with PKP partner that has a Kode Transaksi
2. `_post()` auto-assigns a 16-digit tax number from the available range pool
3. User clicks "Download e-Faktur" action
4. Documents are grouped into a `l10n_id_efaktur.document` (one document per batch)
5. `_generate_efaktur_invoice()` builds FK (header), LT (seller), OF (lines) CSV rows
6. CSV is exported and uploaded to DJP portal

## Installation
Install after `l10n_id`. Auto-installs. Requires e-Faktur number ranges to be configured via Accounting > e-Faktur menu.

## Historical Notes
The e-Faktur CSV format was the standard from 2015–2024. As of January 1, 2025, Indonesia transitioned to the CoreTax XML system. The `l10n_id_efaktur` module handles the legacy CSV flow; `l10n_id_efaktur_coretax` handles the new XML flow (Odoo 18). The two can coexist during the transition period.
