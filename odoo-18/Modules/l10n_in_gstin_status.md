---
Module: l10n_in_gstin_status
Version: 18.0
Type: l10n/india
Tags: #odoo18 #l10n #accounting #india #gst
---

# l10n_in_gstin_status — Indian GSTIN Status Verification

## Overview
Extension module for [Modules/l10n_in](Modules/l10n_in.md) that adds the ability to check and verify a partner's GSTIN (Goods and Services Tax Identification Number) status against the official GST Network (GSTN). Displays the verification date and active/inactive status on partner forms and invoices.

## Country
India

## Dependencies
- l10n_in

## Key Models

### `ResPartner` (`res.partner`) — res_partner.py
- `_inherit = 'res.partner'`
- `l10n_in_gstin_verified_status` — Boolean, tracking=True. Set to True if GSTN returns "Active".
- `l10n_in_gstin_verified_date` — Date, tracking=True. The date when the status was last verified.
- `_onchange_l10n_in_gst_status()` — `@api.onchange('vat')` — resets verification status and date when GSTIN changes
- `action_l10n_in_verify_gstin_status()` — Action method that:
  - Calls IAP service `iap.account._l10n_in_connect_to_server()` with `'/iap/l10n_in_reports/1/public/search'`
  - Checks production vs test environment via `l10n_in_edi_production_env`
  - Parses GST status from response: `sts` field (e.g., "Active", "Active?" — case-insensitive)
  - Posts message on partner with status and effective date
  - Writes `l10n_in_gstin_verified_status` and `l10n_in_gstin_verified_date`
  - Handles no-credit error by sending IAP notification
  - Handles invalid GSTIN (code SWEB_9035) with ValidationError

### `AccountMove` (`account.move`) — account_move.py
- `_inherit = "account.move"`
- `l10n_in_partner_gstin_status` — Boolean (compute), shows partner's verified GST status
- `l10n_in_show_gstin_status` — Boolean (compute), visible only on Indian posted invoices that are not paid/reversed and have taxable GST treatment (regular, composition, SEZ, deemed_export, uin_holders)
- `l10n_in_gstin_verified_date` — Date (compute), partner's verification date
- `_compute_l10n_in_show_gstin_status()` — filters to relevant Indian invoices
- `_compute_l10n_in_partner_gstin_status_and_date()` — pulls from partner
- `l10n_in_verify_partner_gstin_status()` — action to trigger verification from invoice view

## Data Files
- `views/account_move_views.xml` — Shows GST status badge/button on invoices
- `views/res_partner_views.xml` — "Verify GST Status" button on partner form

## Verification Flow
1. User clicks "Verify GSTIN Status" on partner or invoice
2. IAP service queries GSTN API via `l10n_in_reports` endpoint
3. Status returned (Active/Active?/Inactive/Suspended)
4. Partner record updated with status and date
5. Invoice shows live status indicator if partner has verified GSTIN

## Installation
Installable on top of `l10n_in`. Auto-install not set.

## Historical Notes
Version 1.0 in Odoo 18. New module in Odoo 18. GSTN API connectivity provided via IAP (In-App Purchase) credits system.