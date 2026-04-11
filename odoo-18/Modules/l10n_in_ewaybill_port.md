---
Module: l10n_in_ewaybill_port
Version: 18.0
Type: l10n/india-edi
Tags: #odoo18 #l10n #edi #ewaybill #india #shipping
---

# l10n_in_ewaybill_port — Indian E-waybill Shipping Ports

## Overview
Introduces port code support for Air and Sea transport modes in the Indian e-waybill system. Extends `l10n_in_edi_ewaybill` with the ability to record shipping port codes on e-waybill invoices. Required when the transport mode is Air (`1`) or Sea (`2`).

## Country
India

## Dependencies
- l10n_in_edi_ewaybill

## Key Models

### `AccountMove` (`account.move`) — account_move.py
- `_inherit = 'account.move'`
- Adds port code field for Air/Sea e-waybills

### `AccountEdiFormat` (`account.edi.format`) — account_edi_format.py
- `_inherit = 'account.edi.format'`
- Extends e-waybill JSON generation to include port codes for Air/Sea shipments

## Data Files
- `views/account_move_views.xml`

## Installation
Installable. Requires `l10n_in_edi_ewaybill`.

## Historical Notes
New in Odoo 18. Indian e-waybill requires different address fields for different transport modes: Road uses standard address, Air/Sea require shipping port codes (location code + port name). This module bridges that gap.