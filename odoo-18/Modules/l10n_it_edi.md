---
Module: l10n_it_edi
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #italy #fattura
---

# l10n_it_edi

## Overview
Core Italian e-invoicing module. Generates, sends, receives, and processes FatturaPA XML invoices via the SDI (Sistema di Interscambio) using the Account EDI Proxy Client. Handles the full lifecycle: generation → signature → sending → SDI processing → acceptance/rejection → incoming invoice import. This is the foundational module for all Italian EDI extensions.

## EDI Format / Standard
FatturaPA XML (Italian国家标准). Based on Fattura Elettronica format defined by DM 55/2013. XML signature via XAdES. Submission via SDI web service (via `account_edi_proxy_client`). SDI states: `being_sent | processing | rejected | forwarded | forward_failed | forward_attempt | accepted_by_pa_partner | rejected_by_pa_partner | accepted_by_pa_partner_after_expiry`.

## Dependencies
- `l10n_it` -- Italian localization base
- `account_edi_proxy_client` -- EDI proxy framework for SDI communication

## Key Models

### `account.move` (`l10n_it_edi.account_move`)
Extends: `account.move`

Fields:
- `l10n_it_edi_state` -- Selection (SDI state machine)
- `l10n_it_edi_header` -- Html (user-facing state hints)
- `l10n_it_edi_transaction` -- Char (SDI transaction ID)
- `l10n_it_edi_attachment_file` / `_id` -- Binary + Many2one (signed XML attachment)
- `l10n_it_edi_attachement_id` -- Many2one to `ir.attachment` (duplicate field, legacy alias)
- `l10n_it_edi_date` -- Date (SDI transmission date)

Also defines PDF report data and PDF attachment fields (line truncated in source).

Key methods:
- `_l10n_it_edi_get_values()` -- Builds template context for FatturaPA XML rendering (base_lines, taxes, DDT references, discounts, rounding)
- `_l10n_it_edi_send()` -- Entry point: checks, creates attachment, calls proxy
- `_l10n_it_edi_send_to_partner()` -- Attempts to forward accepted invoice to partner email
- `_l10n_it_edi_confirm()` -- Called by proxy on receipt of SDI state change
- SDI state transition methods: `l10n_it_edi_reprocess()`, `l10n_it_edi_send`, `l10n_it_edi_cancel`
- Import: `_l10n_it_edi_import_invoice()`, `_l10n_it_edi_import_as_reversed()`, `_l10n_it_edi_get_extra_info()`

### `account.edi.proxy.user` (`l10n_it_edi.account_edi_proxy_user`)
Extends: `account.edi.proxy.user` (from `account_edi_proxy_client`)

- Configures SDI endpoint, proxy credentials, and forward email
- Implements `l10n_it_edi` as an EDI format

### `account.move.send` (`l10n_it_edi.account_move_send`)
Extends: `account.move.send`

- `_get_edi_sender()` -- Returns `l10n_it_edi` as sender

### `ir.attachment` / `res.company` / `res.config.settings` / `res.partner` / `ddt`
Extensions for SDI configuration, company settings, and DDT (transport document) integration.

## Data Files
- `data/invoice_it_template.xml` -- FatturaPA XML template (QWeb)
- `data/invoice_it_simplified_template.xml` -- Simplified invoice template (for B2C up to 100 EUR)
- `data/ir_cron.xml` -- Cron jobs for SDI polling
- `data/account.account.tag.csv` -- Account tags for tax breakdown
- `views/res_config_settings_views.xml`, `views/l10n_it_view.xml`, `views/report_invoice.xml` -- UI
- `security/ir.model.access.csv` -- ACL

## How It Works
1. Customer invoice posted; user clicks "Send" (via `account.move.send`)
2. `_l10n_it_edi_get_values()` builds XML template context from lines/taxes
3. `_l10n_it_edi_send()` creates `l10n_it_edi.attachment` (signed XML) and submits via proxy
4. Proxy submits to SDI; state → `being_sent` → `processing`
5. SDI responds: `accepted` → forwarded to buyer; `rejected` → state → `rejected` with error
6. Cron job polls SDI for status updates; state transitions accordingly
7. Vendor invoices received via email or SDI push; `_l10n_it_edi_import_invoice()` parses and creates move

## Installation
Auto-installs with `l10n_it`. Requires SDI proxy credentials from the Italian tax authority (Ag Entrate). Demo data provided for testing.

## Historical Notes
The Italian SDI e-invoicing mandate has been phased in: B2B since January 2017, PA since 2015, motor vehicle fuel (B2B fuel) since July 2018. The `l10n_it_edi` module was significantly refactored in Odoo 16 to use the `account_edi_proxy_client` instead of direct API calls, providing a cleaner separation between Odoo and the SDI endpoint. Odoo 18 adds simplified invoice support (B2C receipts up to 100 EUR, using a separate lightweight XML template).
