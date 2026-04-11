---
Module: l10n_id_efaktur_coretax
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #indonesia #efaktur #coretax
---

# l10n_id_efaktur_coretax

## Overview
Generates Indonesian e-Faktur in the new CoreTax XML format (mandatory from January 1, 2025, replacing the legacy CSV). Produces XML-structured e-Faktur documents for customer invoices, with support for transaction codes 07 and 08 that require additional facility and exemption information. Supercedes `l10n_id_efaktur` for new invoices.

## EDI Format / Standard
Indonesian CoreTax e-Faktur XML (DJP/Fiscal Administration). Format includes: Invoice, Seller, Buyer, Tax (DPP+PPN), and line items with product/UoM codes.

## Dependencies
- `l10n_id` -- Indonesian localization base
- `l10n_id_efaktur` -- Provides partner PKP fields and ranges (for coexistence)

## Key Models

### `account.move` (`l10n_id_efaktur_coretax.account_move`)
Extends: `account.move`

Fields (extensions/overrides):
- `l10n_id_kode_transaksi` -- Selection add: `10` (Other deliveries)
- `l10n_id_coretax_document` -- Many2one to `l10n_id_efaktur_coretax.document`
- `l10n_id_coretax_add_info_07` / `_08` -- Selection of TD.00501–TD.00527 codes for kode 07 (facility/additional info)
- `l10n_id_coretax_facility_info_07` / `_08` -- Selection of TD.01101–TD.01127 codes (facility stamps)
- `l10n_id_coretax_custom_doc` -- Char for additional documentation (kode 07/08)
- `l10n_id_coretax_efaktur_available` -- Computed: shows when partner is PKP + Indonesian + invoice + has taxes

Key methods:
- `_compute_l10n_id_coretax_efaktur_available()` -- Overrides legacy need_kode_transaksi
- `_compute_l10n_id_coretax_add_info()` / `_compute_l10n_id_coretax_facility_info()` -- Bidirectional linking between add_info and facility_info selections (they share the last 2 digits)
- `download_efaktur()` -- Overrides legacy; creates `l10n_id_efaktur_coretax.document` and triggers XML generation
- `download_xml()` -- Wrapper: returns document download action
- `prepare_efaktur_vals()` -- Builds invoice data dict for XML template; calls `_l10n_id_coretax_build_invoice_vals()` and line methods
- `_l10n_id_coretax_build_invoice_vals()` -- Maps company/partner to XML fields: TIN, dates, trx_code, add_info, facility_stamp, buyer TIN/DocumentType/DocumentNumber, IDTKU

### `l10n_id_efaktur_coretax.document` (`l10n_id_efaktur_coretax.efaktur_document`)
Stands alone: no `_inherit`.

Inherits `mail.thread.main.attachment` and `mail.activity.mixin`.

Fields:
- `name` -- Computed: `YYYYMMDD - Efaktur (...)` from invoice names
- `company_id`, `active`, `invoice_ids`, `attachment_id`

Key methods:
- `_generate_xml()` -- Renders QWeb template with efaktur data; creates `ir.attachment`
- `_generate_efaktur_invoice()` -- Collects invoice vals via `prepare_efaktur_vals()` and renders XML template
- `action_download()` -- Triggers XML generation if needed; returns download URL
- `action_regenerate()` -- Re-generates XML

### `account.move.line` / `product.code` / `product.template` / `res.partner` / `uom.code` / `uom.uom`
Extensions for UoM and product code mapping needed for CoreTax XML line items.

## Data Files
- `data/l10n_id_efaktur_coretax.product.code.csv` -- Product classification codes
- `data/l10n_id_efaktur_coretax.uom.code.csv` -- UoM codes (mapped to Indonesia's standard UoM list)
- `data/uom.uom.csv` -- CoreTax-specific UoM definitions
- `data/efaktur_templates.xml` -- QWeb XML templates for e-Faktur rendering
- `security/ir.model.access.csv`, `views/*.xml` -- ACL and UI

## How It Works
1. Invoice posted with PKP partner; user selects Kode Transaksi (01–10)
2. For kode 07/08, additional info and facility stamp codes are mandatory
3. User clicks "Download e-Faktur" (Coretax flow); creates `document` record
4. `prepare_efaktur_vals()` iterates lines; `_l10n_id_coretax_build_invoice_line_vals()` maps each line to XML
5. QWeb template renders XML; attachment is created
6. Attachment is downloaded for upload to DJP CoreTax portal

## Installation
Auto-installs with `l10n_id_efaktur`. Requires CoreTax-enabled Indonesian company settings and product/UoM code mappings.

## Historical Notes
CoreTax became mandatory January 1, 2025, replacing the CSV e-Faktur with XML. A notable change is the tax base calculation: for standard e-Faktur, TaxBase (DPP) is multiplied by `11/12` and taxed at `12%` to yield an effective `11%` rate, as mandated by recent tax regulation changes. The module distinguishes between the legacy CSV flow (`l10n_id_efaktur`) and the new XML flow (`l10n_id_efaktur_coretax`) via `l10n_id_need_kode_transaksi` override.
