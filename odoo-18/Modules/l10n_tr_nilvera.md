---
Module: l10n_tr_nilvera
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #turkey #nilvera
---

# l10n_tr_nilvera

## Overview
Core base module for Turkish Nilvera EDI integration. Provides API credentials management, partner customer status checking against Nilvera's server, and alias (e-archive/e-invoice receiver designation) management. Nilvera is a Turkish government-accredited EDI service provider.

## EDI Format / Standard
Not an EDI format itself; provides the API client and partner resolution for Nilvera's e-invoice, e-archive, and e-dispatch flows. Downstream modules produce UBL 1.2/TR and XML dispatch documents.

## Dependencies
- `l10n_tr` -- Turkish localization base

## Key Models

### `l10n_tr.nilvera.alias` (`l10n_tr_nilvera.l10n_tr_nilvera_alias`)
Stands alone: no `_inherit`.

- `name` -- Char: the alias name on Nilvera
- `partner_id` -- Many2one to `res.partner`

Represents a customer's registered alias (receiver designation) on the Nilvera portal.

### `res.partner` (`l10n_tr_nilvera.res_partner`)
Extends: `res.partner`

- `invoice_edi_format` -- Selection add: `ubl_tr` (UBL Turkey 1.2)
- `l10n_tr_nilvera_customer_status` -- Selection: `not_checked | earchive | einvoice`; computed from Nilvera API
- `l10n_tr_nilvera_customer_alias_id` -- Many2one to alias; selected from synced aliases
- `l10n_tr_nilvera_customer_alias_ids` -- One2many to aliases (technical, for sync)

Methods:
- `check_nilvera_customer()` -- Calls Nilvera API `GET /general/GlobalCompany/Check/TaxNumber/{vat}`; if response is empty → `earchive` status; if results found → `einvoice` + syncs aliases; on error silently continues
- `_get_edi_builder()` -- Returns `account.edi.xml.ubl.tr` when `invoice_edi_format == 'ubl_tr'`
- `_get_ubl_cii_formats_info()` -- Registers `'ubl_tr'` for country `TR`

### `res.company` (`l10n_tr_nilvera.res_company`)
Extends: `res.company`

- `l10n_tr_nilvera_api_key` -- Char (system: only visible to admin)
- `l10n_tr_nilvera_environment` -- Selection: `sandbox | production`
- `l10n_tr_nilvera_purchase_journal_id` -- Many2one to `account.journal`; auto-assigns `is_nilvera_journal = True`

### `account.journal` (`l10n_tr_nilvera.account_journal`)
Extends: `account.journal`

- `l10n_tr_nilvera_api_key` -- Related to company
- `is_nilvera_journal` -- Boolean; marks journal used for Nilvera e-invoice receipt

### `uom.uom` / `res.config.settings`
Minimal extensions for UoM and settings compatibility.

## Data Files
- `data/uom_data.xml` -- Unit of measure data for Turkey
- `security/ir.model.access.csv` -- ACL entries
- `views/res_config_settings_views.xml`, `views/res_partner_views.xml` -- UI

## How It Works
1. When a partner's VAT is set and `invoice_edi_format` is `ubl_tr`, `_compute_nilvera_customer_status_and_alias_id()` triggers `check_nilvera_customer()`
2. Nilvera API returns whether the partner is registered as e-archive or e-invoice capable
3. Aliases are synced from Nilvera to local `l10n_tr.nilvera.alias` records
4. Downstream modules (`l10n_tr_nilvera_einvoice`) use `l10n_tr_nilvera_customer_status` to determine which UBL profile to use (`TEMELFATURA` vs `EARSIVFATURA`)

## Installation
Install after `l10n_tr`. Sets up API credentials and partner scanning. Auto-installs downstream Nilvera modules.

## Historical Notes
Nilvera is one of several Turkish EDI service providers (alongside马尔科技, Combil, etc.). Odoo 18 introduced Nilvera as a new EDI provider for Turkey. The customer status API check avoids sending to the wrong endpoint (e-archive vs e-invoice), which would cause rejections.
