---
Module: l10n_es_pos
Version: 18.0
Type: l10n/spain/pos
Tags: #odoo18 #l10n #spain #pos #point-of-sale
---

# l10n_es_pos

## Overview
Spanish localization for the Point of Sale (POS) application. Provides the localization-specific frontend assets (labels, translations, UI strings) and back-end model extensions required for Spanish fiscal receipting and VAT-compliant POS operations. Does not include EDI/fiscal invoice certification (that is `l10n_es_edi_tbai_pos` for TicketBAI / `l10n_es_edi_verifactu_pos` for VeriFactu).

## Country
Spain

## Dependencies
- `point_of_sale`
- `l10n_es` (Spanish accounting base)

## Key Models

### `PosOrder` (`pos.order`)
Inherits: `pos.order`
Adds Spanish-specific behavior to POS orders (tax types, exemption codes passed through to invoices).

### `PosConfig` (`pos.config`)
Inherits: `pos.config`
Spanish POS configuration settings (e.g., receipt footer text, ticket numbering).

### `ResCompany` (`res.company`)
Inherits: `res.company`
Company-level settings for Spanish POS: simplified invoice series, fiscal sequence.

### `ResConfigSettings` (`res.config.settings`)
Inherits: `res.config.settings`
Settings view extension for Spanish POS parameters.

### `AccountMove` (`account.move`)
Inherits: `account.move`
Invoice creation from POS orders uses Spanish tax types (`l10n_es_type`, `l10n_es_exempt_reason`) defined in `l10n_es`.

## Data Files
No XML data files. All data is loaded via Python hooks in `l10n_es`.

## Installation
Install after both `point_of_sale` and `l10n_es` are installed. Auto-installs with POS when Spanish country is detected.

## EDI / Fiscal Positions
This module handles POS receipt layout and Spanish tax application. Fiscal invoice compliance (TicketBAI, VeriFactu) is handled by:
- `l10n_es_edi_tbai_pos` -- TicketBAI for POS (Basque Country)
- `l10n_es_edi_verifactu_pos` -- VeriFactu for POS (rest of Spain)

## Historical Notes
- Odoo 18: Separated into its own installable module from the main l10n_es chart
- Prior: Spanish POS support was embedded in `l10n_es`
