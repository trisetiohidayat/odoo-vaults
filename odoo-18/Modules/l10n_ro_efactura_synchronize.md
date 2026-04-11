---
Module: l10n_ro_efactura_synchronize
Version: 18.0
Type: l10n/ro
Tags: #odoo18 #l10n #accounting #edi
---

# l10n_ro_efactura_synchronize

## Overview
Romania E-Factura SPV (Sistemul de Facturare Electronică) synchronization module. Extends `l10n_ro_edi` (CIUS-RO EDI) to automatically fetch invoice status from ANAF (Autoritatea Națională de Administrare Fiscală) and import received vendor bills. Runs as a daily CRON job. B2G mandatory as of 2024.

## Country
[[Modules/Account|Romania]] 🇷🇴

## Dependencies
- [[Modules/l10n_ro|l10n_ro]] (via `l10n_ro_edi`)

## Key Models

### L10nRoEdiDocument (extends l10n_ro_edi.document)
`models/ciusro_document.py` — extends `l10n_ro_edi.document`
- `_request_ciusro_send_invoice()` — override: catches `requests.Timeout` and returns `{'key_loading': False}` to avoid duplicate sends; invoice waits for sync recovery
- `_request_ciusro_fetch_status()` — override: if `key_loading` is falsy, returns `{}` (skip status check for non-indexed invoices waiting for sync)
- `_request_ciusro_synchronize_invoices()` — main sync method: calls ANAF `listaMesajeFactura` endpoint, parses JSON response, categorizes messages into:
  - `sent_invoices_accepted_messages` — invoices accepted by SPV (FACTURA TRIMISA)
  - `sent_invoices_refused_messages` — refused invoices (ERORI FACTURA)
  - `received_bills_messages` — vendor bills received via SPV (FACTURA PRIMITA)
  - Downloads invoice data and signatures via `_request_ciusro_download_answer` (called twice: once for data, once for signature)
  - Returns structured dict with all three message lists

### AccountMove
`models/account_move.py` — extends `account.move`
- `_compute_show_reset_to_draft_button()` — override: for Romanian invoices with SPV index (`l10n_ro_edi_index`), keeps `show_reset_to_draft_button = True` even when normally hidden for sent invoices (allows recovery from certain error states)
- `_l10n_ro_edi_fetch_invoices()` — calls document model sync method, processes results
- `_l10n_ro_edi_process_invoice_accepted_messages()` — handles accepted invoice messages: matches by SPV index first, then by invoice name for non-indexed invoices (edge case for server timeouts during send); creates `document_invoice_validated` records with key loading, signature, certificate, attachment
- `_l10n_ro_edi_process_invoice_refused_messages()` — processes refusals: creates `document_invoice_sending_failed` records with error message; cannot recover index — user must duplicate invoice
- `_l10n_ro_edi_process_bill_messages()` — imports received vendor bills from SPV: creates new `in_invoice` records if not found by SPV index or by (seller VAT + amount + date) matching; sets SPV index, creates validated document, creates attachment, posts message
- `action_l10n_ro_edi_fetch_invoices()` — action button to trigger manual sync
- `_l10n_ro_edi_fetch_invoices()` — also expires non-indexed invoices held >3 days without index (probable refusal without proper error received)

### ResCompany
`models/res_company.py` — extends `res.company`
- `l10n_ro_edi_anaf_imported_inv_journal_id` (Many2one `account.journal`) — purchase journal for SPV-imported bills; computed auto-assignment for RO companies
- `_cron_l10n_ro_edi_synchronize_invoices()` — daily CRON method: finds all RO companies with ANAF credentials (`l10n_ro_edi_refresh_token`, `client_id`, `client_secret`), calls `_l10n_ro_edi_fetch_invoices()` per company; logs errors via `_l10n_ro_edi_log_message`

### ResConfigSettings
`models/res_config_settings.py` — extends `res.config.settings`
- `l10n_ro_edi_anaf_imported_inv_journal_id` — related field for settings UI

## Data Files
- `data/ir_cron.xml` — CRON: runs `_cron_l10n_ro_edi_synchronize_invoices` daily at 22:00
- `views/account_move_views.xml` — action button on invoice form
- `views/res_config_settings.xml` — settings view for imported journal

## Chart of Accounts
Inherits from [[Modules/l10n_ro|l10n_ro]].

## Tax Structure
Inherits from [[Modules/l10n_ro|l10n_ro]].

## Fiscal Positions
Inherits from [[Modules/l10n_ro|l10n_ro]].

## EDI/Fiscal Reporting
Romanian e-Factura / SPV mandatory B2G invoice exchange with ANAF.
- Extends CIUS-RO UBL-BIS3 from `l10n_ro_edi`
- Handles timeout recovery (no duplicate sends)
- 3-day holding period before expiring non-indexed invoices
- Invoice acceptance/refusal lifecycle fully managed

## Installation
Installs as standalone module on top of `l10n_ro_edi`. No demo data. `installable: True`.

Post-init hook: none (CRON handles sync).

## Historical Notes

**Odoo 17 → 18 changes:**
- New module for Odoo 18+ — Romania mandated e-Factura for B2G from 2024, making this module essential
- Relies on ANAF API credentials (`l10n_ro_edi_refresh_token`, `l10n_ro_edi_client_id`, `l10n_ro_edi_client_secret`) configured in company settings (via `l10n_ro_edi`)
- Timeout recovery pattern prevents double-send when ANAF server timeout occurs during indexing
- Bill import from SPV is a major new capability for vendor bill management

**Performance Notes:**
- CRON runs once daily per company; lightweight API calls
- Processing logic handles large message batches efficiently